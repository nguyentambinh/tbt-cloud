# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AuditLog, Instance, NodeOSTemplate, OSImage, Plan, Transaction, User
from app.security import decrypt_secret, encrypt_secret
from app.services.billing import as_utc, get_wallet
from app.services.instances import default_name
from app.services.proxmox_client import ProxmoxError


@pytest.fixture
def managed(db, instance, instance_payload, mock_proxmox, monkeypatch):
    instance.cloud_user = "ubuntu"
    instance.ssh_public_key = instance_payload["ssh_public_key"]
    instance.template_id = 9000
    instance.password_encrypted = encrypt_secret("InitialPassword123")
    instance.ssh_port = 22000
    instance.ip = "10.10.0.2"
    instance.paid_until = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()
    factory, proxmox = mock_proxmox
    monkeypatch.setattr("app.routers.instances.ProxmoxClient", factory)
    proxmox.get_template_name.return_value = "Ubuntu 24.04 LTS"
    proxmox.get_stats.return_value = [{"time": 1, "cpu": 25, "mem_used": 100, "mem_total": 512, "netin": 0, "netout": 2, "diskread": None, "diskwrite": 0}]
    proxmox.get_status_now.return_value = {"cpu": 25, "mem": 100, "uptime": 3600}
    return instance, proxmox


def test_creation_password_encrypted_and_cloud_config_saved(client, db, headers, instance_payload, mock_proxmox):
    mock_proxmox[1].get_ip.return_value = "10.0.0.44"
    result = client.post("/api/v1/instances", headers=headers["user"], json=instance_payload)
    assert result.status_code == 201
    instance = db.get(Instance, result.json()["id"])
    password = decrypt_secret(instance.password_encrypted)
    assert len(password) == 8 and any(c.isupper() for c in password) and any(c.islower() for c in password) and any(c.isdigit() for c in password) and any(c in "!@%*-_+=?" for c in password)
    assert instance.password_encrypted != password and password not in result.text
    assert instance.cloud_user == "ubuntu" and instance.ssh_public_key == instance_payload["ssh_public_key"]
    assert instance.template_id == 9000 and result.json()["ip"] == "10.0.0.44"
    assert mock_proxmox[1].configure_cloud_init.call_args.kwargs["password"] == password
    assert mock_proxmox[1].configure_cloud_init.call_args.kwargs["vendor"] == "local:snippets/tbt-vendor.yaml"


def test_creation_defaults_name_root_and_optional_key(client, db, headers, instance_payload, mock_proxmox):
    body = {"plan_id": instance_payload["plan_id"], "loai": "vm"}
    first = client.post("/api/v1/instances", headers=headers["user"], json=body)
    assert first.status_code == 201, first.text
    instance = db.get(Instance, first.json()["id"])
    assert first.json()["ten"] == "owner-1" and default_name(db, db.get(User, instance.user_id)) == "owner-2"
    assert instance.cloud_user == "root" and instance.ssh_public_key is None
    password = decrypt_secret(instance.password_encrypted)
    assert len(password) == 8 and any(c.isupper() for c in password) and any(c.islower() for c in password) and any(c.isdigit() for c in password) and any(c in "!@%*-_+=?" for c in password)
    args = mock_proxmox[1].configure_cloud_init.call_args
    assert args.args[3:5] == ("root", None) and args.kwargs["vendor"] == "local:snippets/tbt-vendor.yaml"
    credentials = client.get(f"/api/v1/instances/{instance.id}/credentials", headers=headers["user"]).json()
    assert credentials["username"] == "root" and credentials["password"] == password


def test_lxc_still_requires_key(client, headers, instance_payload):
    body = {"plan_id": instance_payload["plan_id"], "loai": "lxc"}
    assert client.post("/api/v1/instances", headers=headers["user"], json=body).status_code == 422


@pytest.mark.parametrize("role", ["user", "admin"])
def test_credentials_owner_admin_and_no_cache(client, headers, managed, role):
    instance, proxmox = managed
    result = client.get(f"/api/v1/instances/{instance.id}/credentials", headers=headers[role])
    assert result.status_code == 200
    assert result.json() == {"username": "ubuntu", "password": "InitialPassword123", "ssh_host": "localhost", "ipv6": None, "ssh_port": 22000, "ket_noi": "ssh", "host": "localhost", "port": 22000, "dia_chi": "localhost:22000"}
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("body", [{}, {"password": "Replacement123456"}, None])
def test_password_changes_cloudinit_and_reboots(client, db, headers, managed, body):
    instance, proxmox = managed
    result = client.post(f"/api/v1/instances/{instance.id}/password", headers=headers["user"], json=body)
    assert result.status_code == 200, result.text
    password = result.json()["password"]
    assert password == decrypt_secret(instance.password_encrypted)
    if body and "password" in body:
        assert password == body["password"]
    else:
        assert len(password) == 8 and any(c.isupper() for c in password) and any(c.islower() for c in password) and any(c.isdigit() for c in password) and any(c in "!@%*-_+=?" for c in password)
    proxmox.set_password.assert_called_once_with(instance.vmid, "ubuntu", password)
    proxmox.reboot.assert_called_once_with(instance.vmid, "vm")
    assert result.headers["cache-control"] == "no-store"
    assert password not in str(list(db.scalars(select(AuditLog.detail))))


@pytest.mark.parametrize("password", ["short", "A" * 129, "HasNewline123\n", "HasNull123\x00"])
def test_invalid_password_never_reaches_node(client, headers, managed, password):
    instance, proxmox = managed
    assert client.post(f"/api/v1/instances/{instance.id}/password", headers=headers["user"], json={"password": password}).status_code == 422
    proxmox.set_password.assert_not_called()


def test_lxc_credentials_and_password_not_supported(client, db, headers, managed):
    instance, proxmox = managed
    instance.loai, instance.cloud_user, instance.password_encrypted = "lxc", "root", None
    db.commit()
    assert client.get(f"/api/v1/instances/{instance.id}/credentials", headers=headers["user"]).json()["password"] is None
    result = client.post(f"/api/v1/instances/{instance.id}/password", headers=headers["user"])
    assert result.status_code == 400 and "chưa được hỗ trợ" in result.json()["detail"]
    proxmox.set_password.assert_not_called()


def test_detail_actual_status_template_and_total_cost(client, db, headers, managed, seed):
    instance, proxmox = managed
    wallet = get_wallet(db, instance.user_id)
    db.add_all([Transaction(wallet_id=wallet.id, instance_id=instance.id, amount=-10, kind="usage", idempotency_key="detail-1", description="Giờ 1"), Transaction(wallet_id=wallet.id, instance_id=instance.id, amount=-20, kind="usage", idempotency_key="detail-2", description="Giờ 2"), Transaction(wallet_id=wallet.id, amount=100, kind="topup", idempotency_key="detail-topup", description="Nạp ví")])
    db.commit()
    proxmox.get_status.return_value = "stopped"
    result = client.get(f"/api/v1/instances/{instance.id}/detail", headers=headers["user"])
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["ten_he_dieu_hanh"] == "Ubuntu 24.04 LTS" and value["node_ten"] == seed["node"].ten
    assert Decimal(value["tong_chi_phi"]) == 30 and value["ngay_tao"] == value["created_at"]
    assert value["trang_thai"] == "stopped" and instance.trang_thai == "running"
    assert "password_encrypted" not in value


@pytest.mark.parametrize("timeframe", ["hour", "day", "week"])
def test_stats_and_status_now(client, headers, managed, timeframe):
    instance, proxmox = managed
    result = client.get(f"/api/v1/instances/{instance.id}/stats?timeframe={timeframe}", headers=headers["user"])
    assert result.status_code == 200 and result.json()[0]["cpu"] == 25
    proxmox.get_stats.assert_called_once_with(instance.vmid, "vm", timeframe)
    assert client.get(f"/api/v1/instances/{instance.id}/status-now", headers=headers["user"]).json() == {"cpu": 25, "mem": 100, "uptime": 3600}


def test_stats_invalid_timeframe(client, headers, managed):
    instance, proxmox = managed
    assert client.get(f"/api/v1/instances/{instance.id}/stats?timeframe=year", headers=headers["user"]).status_code == 422
    proxmox.get_stats.assert_not_called()


@pytest.mark.parametrize("loai, role", [("vm", "user"), ("lxc", "admin")])
def test_reinstall_keeps_vmid_port_snapshot_and_credentials(client, db, headers, managed, seed, loai, role):
    instance, proxmox = managed
    instance.loai = loai
    instance.cloud_user = "root" if loai == "lxc" else "ubuntu"
    instance.template_id = 9001 if loai == "lxc" else 9000
    instance.ip_cidr, instance.gateway = "10.10.0.2/24", "10.10.0.1"
    seed["plan"].vcpu = 4
    db.commit()
    proxmox.get_ip.return_value = "10.10.0.55"
    before = (instance.id, instance.vmid, instance.ssh_port, as_utc(instance.paid_until), get_wallet(db, instance.user_id).balance)
    result = client.post(f"/api/v1/instances/{instance.id}/reinstall", headers=headers[role])
    assert result.status_code == 200, result.text
    assert (instance.id, instance.vmid, instance.ssh_port, as_utc(instance.paid_until), get_wallet(db, instance.user_id).balance) == before
    assert instance.ip == "10.10.0.55" and instance.trang_thai == "running" and instance.vcpu == 1
    proxmox.stop.assert_called_once_with(instance.vmid, loai)
    proxmox.delete.assert_called_once_with(instance.vmid, loai)
    proxmox.clone_template.assert_called_once_with(instance.template_id, instance.vmid, instance.ten, loai)
    args = proxmox.configure_cloud_init.call_args.args
    assert args[2].vcpu == 1 and args[3:7] == (instance.cloud_user, instance.ssh_public_key, instance.ip_cidr, instance.gateway)
    password = proxmox.configure_cloud_init.call_args.kwargs["password"]
    assert (password is None) if loai == "lxc" else (decrypt_secret(instance.password_encrypted) == password and password != "InitialPassword123")
    assert db.scalar(select(AuditLog).where(AuditLog.action == "instance.reinstall")) is not None


@pytest.mark.parametrize("action, failed_method", [("reinstall", "clone_template"), ("reinstall", "start"), ("password", "set_password"), ("password", "reboot")])
def test_maintenance_failure_keeps_reservation_and_audits(client, db, headers, managed, action, failed_method):
    instance, proxmox = managed
    getattr(proxmox, failed_method).side_effect = ProxmoxError()
    result = client.post(f"/api/v1/instances/{instance.id}/{action}", headers=headers["user"])
    assert result.status_code == 502
    assert instance.trang_thai == "error" and instance.vmid == 101 and instance.ssh_port == 22000
    assert db.scalar(select(AuditLog).where(AuditLog.action == f"instance.{action}_failed")) is not None


@pytest.mark.parametrize("state", ["suspended", "provisioning", "error"])
@pytest.mark.parametrize("action", ["reinstall", "password"])
def test_maintenance_rejects_unavailable_states(client, db, headers, managed, state, action):
    instance, proxmox = managed
    instance.trang_thai = state
    db.commit()
    assert client.post(f"/api/v1/instances/{instance.id}/{action}", headers=headers["user"]).status_code == 409
    proxmox.delete.assert_not_called()
    proxmox.set_password.assert_not_called()


def test_legacy_reinstall_rejected_before_delete(client, db, headers, managed):
    instance, proxmox = managed
    instance.ssh_public_key = None
    instance.password_encrypted = None
    db.commit()
    assert client.post(f"/api/v1/instances/{instance.id}/reinstall", headers=headers["user"]).status_code == 409
    proxmox.delete.assert_not_called()


def test_reinstall_insufficient_funds_never_deletes(client, db, headers, managed):
    instance, proxmox = managed
    instance.paid_until = datetime.now(timezone.utc) - timedelta(hours=1)
    get_wallet(db, instance.user_id).balance = Decimal("0.00")
    db.commit()
    assert client.post(f"/api/v1/instances/{instance.id}/reinstall", headers=headers["user"]).status_code == 402
    proxmox.delete.assert_not_called()


@pytest.mark.parametrize("action", ["password", "reinstall"])
def test_maintenance_stopped_guest_charges_owner_and_starts(client, db, headers, managed, action):
    instance, proxmox = managed
    instance.trang_thai = "stopped"
    instance.paid_until = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    proxmox.get_status.return_value = "stopped"
    assert client.post(f"/api/v1/instances/{instance.id}/{action}", headers=headers["admin"]).status_code == 200
    proxmox.start.assert_called_once_with(instance.vmid, "vm")
    proxmox.reboot.assert_not_called()
    assert get_wallet(db, instance.user_id).balance == Decimal("90.00")


def test_logs_scoped_sorted_and_paginated(client, db, headers, managed):
    instance, proxmox = managed
    now = datetime.now(timezone.utc)
    db.add_all([AuditLog(user_id=instance.user_id, action="instance.start", resource=f"instance:{instance.id}", created_at=now), AuditLog(action="instance.stop", resource=f"instance:{instance.id}", created_at=now + timedelta(seconds=1)), AuditLog(action="instance.delete", resource="instance:999")])
    db.commit()
    result = client.get(f"/api/v1/instances/{instance.id}/logs?offset=0&limit=1", headers=headers["user"])
    assert result.status_code == 200 and result.json()[0]["action"] == "instance.stop"
    assert client.get(f"/api/v1/instances/{instance.id}/logs?offset=1&limit=1", headers=headers["admin"]).json()[0]["action"] == "instance.start"
    assert client.get(f"/api/v1/instances/{instance.id}/logs?limit=201", headers=headers["user"]).status_code == 422


@pytest.mark.parametrize("method, suffix", [("get", "credentials"), ("get", "detail"), ("get", "stats"), ("get", "status-now"), ("get", "logs"), ("post", "password"), ("post", "reinstall")])
def test_management_routes_enforce_ownership(client, headers, managed, method, suffix):
    instance, proxmox = managed
    assert getattr(client, method)(f"/api/v1/instances/{instance.id}/{suffix}", headers=headers["other"]).status_code == 404
    assert proxmox.mock_calls == []


def test_custom_password_min_length(client, headers, managed):
    instance, proxmox = managed
    assert client.post(f"/api/v1/instances/{instance.id}/password", headers=headers["user"], json={"password": "1234567"}).status_code == 422
    result = client.post(f"/api/v1/instances/{instance.id}/password", headers=headers["user"], json={"password": "24681357"})
    assert result.status_code == 200 and result.json()["password"] == "24681357"


def test_reinstall_switches_os_and_plan_with_new_price(client, db, headers, managed, seed):
    instance, proxmox = managed
    node = seed["node"]
    node.total_vcpu, node.total_ram_mb, node.total_disk_gb = 16, 32768, 500
    windows = OSImage(ma="windows11", ten="Windows 11", ho="windows", min_ram_mb=4096, min_disk_gb=64, ket_noi="rdp", thu_tu=2)
    big = Plan(ten="Windows", vcpu=2, ram_mb=4096, disk_gb=64, gia_theo_gio=Decimal("25.00"))
    db.add_all([windows, big])
    node.os_templates.append(NodeOSTemplate(os_image=windows, template_id=9020))
    db.commit()
    used = (node.used_vcpu, node.used_ram_mb, node.used_disk_gb)
    options = client.get(f"/api/v1/instances/{instance.id}/reinstall-options", headers=headers["user"]).json()
    assert {os["ma"] for os in options["os"]} == {"debian13", "windows11"} and {plan["id"] for plan in options["plans"]} == {seed["plan"].id, big.id}
    assert client.post(f"/api/v1/instances/{instance.id}/reinstall", headers=headers["user"], json={"os_ma": "windows11"}).status_code == 422
    result = client.post(f"/api/v1/instances/{instance.id}/reinstall", headers=headers["user"], json={"os_ma": "windows11", "plan_id": big.id})
    assert result.status_code == 200, result.text
    db.refresh(instance); db.refresh(node)
    assert instance.gia_theo_gio == Decimal("25.00") and instance.plan_id == big.id and instance.template_id == 9020
    assert instance.cloud_user == "tbtadmin" and instance.ssh_public_key is None and instance.ket_noi == "rdp"
    assert (node.used_vcpu, node.used_ram_mb, node.used_disk_gb) == (used[0] + 1, used[1] + 3584, used[2] + 54)
    proxmox.clone_template.assert_called_once_with(9020, instance.vmid, instance.ten, "vm")
    assert proxmox.configure_cloud_init.call_args.kwargs["vendor"] is None


def test_reinstall_rejects_os_missing_on_node(client, headers, managed):
    instance, proxmox = managed
    assert client.post(f"/api/v1/instances/{instance.id}/reinstall", headers=headers["user"], json={"os_ma": "kali"}).status_code == 422
    proxmox.delete.assert_not_called()


def test_creation_assigns_public_ipv6_from_node_prefix(client, db, headers, instance_payload, mock_proxmox, seed):
    seed["node"].ipv6_prefix = "2402:800:639e:f77c::/64"
    db.commit()
    result = client.post("/api/v1/instances", headers=headers["user"], json={"plan_id": instance_payload["plan_id"], "loai": "vm"})
    assert result.status_code == 201, result.text
    instance = db.get(Instance, result.json()["id"])
    assert instance.ipv6 == "2402:800:639e:f77c::102" and result.json()["ipv6"] == instance.ipv6
    assert client.get(f"/api/v1/instances/{instance.id}/credentials", headers=headers["user"]).json()["ipv6"] == instance.ipv6
