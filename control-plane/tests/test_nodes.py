# Nguyễn Tâm Bình - 2324801030003
from unittest.mock import MagicMock

from app.services.node_sync import sync_node
from app.services.proxmox_client import ProxmoxError


def test_node_response_never_returns_tokens(client, headers):
    payload = {"ten": "node-new", "api_url": "https://100.64.0.2:8006", "token_id": "cloud@pve!control", "token_secret": "private-token-secret", "mesh_ip": "100.64.0.2", "proxmox_node": "pve"}
    response = client.post("/api/v1/nodes", json=payload, headers=headers["admin"])
    assert response.status_code == 201, response.text
    assert "private-token-secret" not in response.text
    assert "token_secret" not in response.json()
    assert "token_id" not in response.json()


def test_sync_preserves_reserved_resources(db, seed, instance):
    instance.trang_thai = "error"
    proxmox = MagicMock()
    proxmox.get_status.return_value = "stopped"
    proxmox.get_ip.return_value = None
    proxmox.get_node_resources.return_value = {"total_vcpu": 8, "total_ram_mb": 16384, "total_disk_gb": 200, "used_vcpu": 0, "used_ram_mb": 0, "used_disk_gb": 0}
    assert sync_node(db, seed["node"], lambda node: proxmox)
    assert seed["node"].used_vcpu == instance.vcpu
    assert seed["node"].used_ram_mb == instance.ram_mb


def test_sync_marks_node_offline(db, seed):
    proxmox = MagicMock()
    proxmox.get_node_resources.side_effect = ProxmoxError()
    assert not sync_node(db, seed["node"], lambda node: proxmox)
    assert seed["node"].trang_thai == "offline"


def test_suspended_and_error_instances_are_stopped_on_reconnect(db, seed, instance):
    instance.trang_thai = "suspended"
    proxmox = MagicMock()
    proxmox.get_status.return_value = "running"
    proxmox.get_ip.return_value = None
    proxmox.get_node_resources.return_value = {"total_vcpu": 8, "total_ram_mb": 16384, "total_disk_gb": 200, "used_vcpu": 1, "used_ram_mb": 512, "used_disk_gb": 10}
    sync_node(db, seed["node"], lambda node: proxmox)
    assert instance.trang_thai == "suspended"
    proxmox.stop.assert_called_once_with(instance.vmid, instance.loai)
