# Nguyễn Tâm Bình - 2324801030003
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AuditLog, Instance, NodeGPU, NodeOSTemplate, OSImage, Plan
from app.services.proxmox_client import ProxmoxClient

GPU = {"pci_id": "0000:01:00", "ten": "NVIDIA GeForce RTX 5060", "vram_mb": 8192}


@pytest.fixture
def ai(db, seed):
    image = OSImage(ma="ubuntu2404ai", ten="Ubuntu 24.04 + CUDA + PyTorch", ho="linux", min_ram_mb=8192, min_disk_gb=30, ket_noi="ssh", thu_tu=8, chi_gpu=True)
    plan = Plan(ten="AI Tiêu chuẩn", dich_vu="vps", vcpu=2, ram_mb=8192, disk_gb=30, gia_theo_gio=Decimal("10.00"), gpu=1)
    seed["node"].os_templates.append(NodeOSTemplate(os_image=image, template_id=9030))
    seed["node"].gpus.append(NodeGPU(**GPU))
    db.add_all([image, plan])
    db.commit()
    return {"image": image, "plan": plan}


def body(instance_payload, plan, ten="ai-1", os_ma="ubuntu2404ai"):
    return {**instance_payload, "ten": ten, "plan_id": plan.id, "dich_vu": "vps", "loai": "vm", "os_ma": os_ma}


def test_public_gpu_summary_hides_pci(client, ai):
    result = client.get("/api/v1/public/gpu")
    assert result.status_code == 200
    assert result.json() == {"tong": 1, "ranh": 1, "loai": ["NVIDIA GeForce RTX 5060 8 GB"]}
    assert "0000:01:00" not in result.text


def test_admin_declares_gpus_and_audits(client, db, headers, seed):
    path = f"/api/v1/admin/nodes/{seed['node'].id}/gpus"
    assert client.put(path, headers=headers["user"], json=[GPU]).status_code == 403
    assert client.put(path, headers=headers["admin"], json=[GPU, GPU]).status_code == 422
    assert client.put(path, headers=headers["admin"], json=[{**GPU, "pci_id": "01:00"}]).status_code == 422
    assert client.put(path, headers=headers["admin"], json=[{**GPU, "pci_id": "Bad Name"}]).status_code == 422
    result = client.put(path, headers=headers["admin"], json=[GPU])
    assert result.status_code == 200 and result.json()[0]["dang_dung"] is False
    assert client.get(path, headers=headers["admin"]).json()[0]["ten"] == GPU["ten"]
    assert db.scalar(select(AuditLog).where(AuditLog.action == "node.gpus")) is not None


def test_create_ai_reserves_gpu_and_passes_hostpci(client, db, headers, ai, mock_proxmox, instance_payload):
    result = client.post("/api/v1/instances", headers=headers["user"], json=body(instance_payload, ai["plan"]))
    assert result.status_code == 201, result.text
    instance = db.get(Instance, result.json()["id"])
    assert instance.gpu.pci_id == "0000:01:00" and instance.template_id == 9030
    assert mock_proxmox[1].configure_cloud_init.call_args.kwargs["gpu_pci"] == "0000:01:00"
    assert client.get("/api/v1/public/gpu").json()["ranh"] == 0
    detail = client.get(f"/api/v1/instances/{instance.id}/detail", headers=headers["user"])
    assert detail.json()["gpu"] == "NVIDIA GeForce RTX 5060 8 GB"


def test_second_ai_gets_409_until_first_deleted(client, db, headers, seed, ai, mock_proxmox, instance_payload):
    first = client.post("/api/v1/instances", headers=headers["user"], json=body(instance_payload, ai["plan"]))
    assert first.status_code == 201, first.text
    mock_proxmox[1].find_free_vmid.return_value = 103
    second = client.post("/api/v1/instances", headers=headers["user"], json=body(instance_payload, ai["plan"], ten="ai-2"))
    assert second.status_code == 409 and "GPU đang được dùng hết" in second.json()["detail"]
    assert client.delete(f"/api/v1/instances/{first.json()['id']}", headers=headers["user"]).status_code == 200
    assert client.get("/api/v1/public/gpu").json()["ranh"] == 1
    third = client.post("/api/v1/instances", headers=headers["user"], json=body(instance_payload, ai["plan"], ten="ai-3"))
    assert third.status_code == 201, third.text


def test_gpu_plan_and_ai_os_must_match(client, db, headers, seed, ai, mock_proxmox, instance_payload):
    wrong_os = client.post("/api/v1/instances", headers=headers["user"], json=body(instance_payload, ai["plan"], os_ma="debian13"))
    assert wrong_os.status_code == 422 and "CUDA" in wrong_os.json()["detail"]
    big = Plan(ten="Big", vcpu=2, ram_mb=8192, disk_gb=30, gia_theo_gio=Decimal("10.00"))
    db.add(big)
    db.commit()
    wrong_plan = client.post("/api/v1/instances", headers=headers["user"], json=body(instance_payload, big))
    assert wrong_plan.status_code == 422 and "máy chủ AI" in wrong_plan.json()["detail"]


def test_busy_gpu_cannot_be_removed(client, db, headers, seed, ai, mock_proxmox, instance_payload):
    assert client.post("/api/v1/instances", headers=headers["user"], json=body(instance_payload, ai["plan"])).status_code == 201
    result = client.put(f"/api/v1/admin/nodes/{seed['node'].id}/gpus", headers=headers["admin"], json=[])
    assert result.status_code == 409


def test_proxmox_client_sets_hostpci(monkeypatch):
    client = object.__new__(ProxmoxClient)
    client.node = type("N", (), {"vm_disk": "scsi0", "bridge": "vpsnet0"})()
    guest = type("G", (), {})()
    calls = {}
    guest.config = type("C", (), {"get": staticmethod(lambda: {"scsi0": "local:9030/base.raw,size=30G"}), "put": staticmethod(lambda **kw: calls.update(kw))})()
    guest.resize = type("R", (), {"put": staticmethod(lambda **kw: None)})()
    monkeypatch.setattr(client, "_guest", lambda vmid, loai: guest)
    plan = type("P", (), {"vcpu": 2, "ram_mb": 8192, "disk_gb": 30})()
    client.configure_cloud_init(105, "vm", plan, "binh", None, gpu_pci="0000:01:00")
    assert calls["hostpci0"] == "0000:01:00,pcie=1"
    client.configure_cloud_init(105, "vm", plan, "binh", None, gpu_pci="rtx5060")
    assert calls["hostpci0"] == "mapping=rtx5060,pcie=1"
