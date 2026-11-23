# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Instance, Node
from app.services.billing import get_wallet
from app.services.proxmox_client import ProxmoxError


def test_create_configures_guest_reserves_and_charges(client, db, seed, headers, instance_payload, mock_proxmox):
    factory, proxmox = mock_proxmox
    response = client.post("/api/v1/instances", json=instance_payload, headers=headers["user"])
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["trang_thai"] == "running"
    assert 22000 <= value["ssh_port"] <= 22999
    assert get_wallet(db, seed["user"].id).balance == Decimal("90.00")
    assert db.get(Node, seed["node"].id).used_vcpu == 1
    proxmox.clone_template.assert_called_once_with(9000, 102, "server-new", "vm")
    proxmox.configure_cloud_init.assert_called_once()
    proxmox.start.assert_called_once_with(102, "vm")


@pytest.mark.parametrize("method, suffix", [("get", ""), ("post", "/start"), ("post", "/stop"), ("post", "/reboot"), ("delete", "")])
def test_other_owner_cannot_access_or_mutate(client, instance, headers, mock_proxmox, method, suffix):
    response = getattr(client, method)(f"/api/v1/instances/{instance.id}{suffix}", headers=headers["other"])
    assert response.status_code == 404
    mock_proxmox[0].assert_not_called()


def test_list_scoped_to_owner_and_admin(client, instance, headers):
    assert client.get("/api/v1/instances", headers=headers["other"]).json() == []
    assert len(client.get("/api/v1/instances", headers=headers["user"]).json()) == 1
    assert len(client.get("/api/v1/instances", headers=headers["admin"]).json()) == 1


def test_owner_and_admin_lifecycle(client, instance, headers, mock_proxmox, db):
    instance.paid_until = datetime.now(timezone.utc) + timedelta(hours=1)
    instance.ssh_port = 22000
    db.commit()
    for action in ("reboot", "stop", "start"):
        response = client.post(f"/api/v1/instances/{instance.id}/{action}", headers=headers["user"])
        assert response.status_code == 200, response.text
    response = client.delete(f"/api/v1/instances/{instance.id}", headers=headers["admin"])
    assert response.status_code == 200
    assert response.json()["trang_thai"] == "deleted"
    assert response.json()["ssh_port"] is None
    mock_proxmox[1].delete.assert_called_once_with(instance.vmid, "vm")


def test_clone_failure_retains_reservation_and_no_charge(client, db, seed, headers, instance_payload, mock_proxmox):
    mock_proxmox[1].clone_template.side_effect = ProxmoxError()
    response = client.post("/api/v1/instances", json=instance_payload, headers=headers["user"])
    assert response.status_code == 502
    value = db.scalar(select(Instance))
    assert value.trang_thai == "error"
    assert value.ssh_port is not None
    assert db.get(Node, seed["node"].id).used_vcpu == 1
    assert get_wallet(db, seed["user"].id).balance == Decimal("100.00")


def test_start_failure_rolls_back_charge(client, db, seed, headers, instance_payload, mock_proxmox):
    mock_proxmox[1].start.side_effect = ProxmoxError()
    response = client.post("/api/v1/instances", json=instance_payload, headers=headers["user"])
    assert response.status_code == 502
    assert get_wallet(db, seed["user"].id).balance == Decimal("100.00")
    assert db.scalar(select(Instance)).trang_thai == "error"


def test_insufficient_funds_never_calls_node(client, db, seed, headers, instance_payload, mock_proxmox):
    get_wallet(db, seed["user"].id).balance = Decimal("0.00")
    db.commit()
    assert client.post("/api/v1/instances", json=instance_payload, headers=headers["user"]).status_code == 402
    mock_proxmox[0].assert_not_called()


def test_stale_node_not_scheduled(client, db, seed, headers, instance_payload, mock_proxmox):
    seed["node"].last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()
    assert client.post("/api/v1/instances", json=instance_payload, headers=headers["user"]).status_code == 503
    mock_proxmox[0].assert_not_called()


@pytest.mark.parametrize("method, suffix", [("post", "/stop"), ("delete", "")])
def test_stop_or_delete_settles_overdue_runtime(client, db, instance, headers, mock_proxmox, method, suffix):
    response = getattr(client, method)(f"/api/v1/instances/{instance.id}{suffix}", headers=headers["user"])
    assert response.status_code == 200, response.text
    assert get_wallet(db, instance.user_id).balance == Decimal("90.00")
