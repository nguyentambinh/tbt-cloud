# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

from app.config import get_settings
from app.models import AuditLog, Instance, NodeOSTemplate, OSImage
from app.security import decrypt_secret
from app.services.proxmox_client import ProxmoxClient
from app.services.scheduler import select_node

IMAGES = import_module("migrations.versions.0006_os_images").IMAGES


@pytest.fixture
def images(db, seed):
    result = {image.ma: image for image in db.scalars(select(OSImage))}
    for ma, ten, ho, ram, disk, connection, order in IMAGES:
        if ma not in result:
            result[ma] = OSImage(ma=ma, ten=ten, ho=ho, min_ram_mb=ram, min_disk_gb=disk, ket_noi=connection, thu_tu=order)
            db.add(result[ma])
    db.commit()
    return result


def test_os_catalog_public_and_freshness(client, db, seed, images):
    node = seed["node"]
    node.os_templates.append(NodeOSTemplate(os_image=images["ubuntu2404"], template_id=9010))
    db.commit()
    result = client.get("/api/v1/os")
    assert result.status_code == 200
    rows = result.json()
    assert [row["ma"] for row in rows] == [row[0] for row in IMAGES]
    assert [row["ma"] for row in rows if row["san_sang"]] == ["debian13", "ubuntu2404"]
    assert rows[0]["so_node"] == 1 and rows[-1]["so_node"] == 0
    assert rows[-1]["ket_noi"] == "rdp" and rows[-1]["min_disk_gb"] == 64
    assert not any(key in result.text for key in ("token_secret", "api_url", "mesh_ip"))
    node.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=121)
    db.commit()
    assert not any(row["san_sang"] for row in client.get("/api/v1/os").json())
    node.last_seen_at = datetime.now(timezone.utc)
    node.trang_thai = "offline"
    db.commit()
    assert not any(row["san_sang"] for row in client.get("/api/v1/os").json())


def test_admin_replaces_mappings_atomically_and_audits(client, db, headers, seed, images):
    path = f"/api/v1/admin/nodes/{seed['node'].id}/os-templates"
    body = [{"os_ma": "ubuntu2404", "template_id": 9010}, {"os_ma": "kali", "template_id": 9013}]
    assert client.put(path, headers=headers["admin"], json=body).json() == body
    assert client.get(path, headers=headers["admin"]).json() == body
    assert client.get("/api/v1/nodes", headers=headers["admin"]).json()[0]["os_templates"] == body
    log = db.scalar(select(AuditLog).where(AuditLog.action == "node.os_templates"))
    assert log.user_id == seed["admin"].id and log.resource == f"node:{seed['node'].id}"
    assert client.put(path, headers=headers["admin"], json=[body[0], body[0]]).status_code == 422
    assert client.put(path, headers=headers["admin"], json=[{"os_ma": "unknown", "template_id": 9010}]).status_code == 422
    assert client.get(path, headers=headers["admin"]).json() == body
    assert client.put(path, headers=headers["admin"], json=[]).json() == []
    assert not any(row["san_sang"] for row in client.get("/api/v1/os").json())


@pytest.mark.parametrize("role,code", [(None, 401), ("user", 403), ("other", 403)])
def test_mapping_requires_admin(client, headers, seed, images, role, code):
    path = f"/api/v1/admin/nodes/{seed['node'].id}/os-templates"
    auth = headers[role] if role else {}
    assert client.get(path, headers=auth).status_code == code
    assert client.put(path, headers=auth, json=[]).status_code == code


@pytest.mark.parametrize("template", [99, 1000000000, True, "9010"])
def test_mapping_validates_template(client, headers, seed, images, template):
    result = client.put(f"/api/v1/admin/nodes/{seed['node'].id}/os-templates", headers=headers["admin"], json=[{"os_ma": "ubuntu2404", "template_id": template}])
    assert result.status_code == 422


@pytest.mark.parametrize("service,kind", [("vps", "lxc"), ("postgres", "vm"), ("webapp", "vm")])
def test_os_only_allowed_for_vm_vps(client, headers, instance_payload, mock_proxmox, service, kind):
    result = client.post("/api/v1/instances", headers=headers["user"], json={**instance_payload, "dich_vu": service, "loai": kind, "os_ma": "debian13"})
    assert result.status_code == 422 and "Chỉ chọn hệ điều hành" in result.json()["detail"]
    mock_proxmox[0].assert_not_called()


@pytest.mark.parametrize("ma,ram,disk,reason", [("windows11", 1024, 64, "cần tối thiểu 4 GB"), ("windows11", 4096, 40, "cần tối thiểu 64 GB"), ("winserver2022", 4096, 30, "cần tối thiểu 40 GB"), ("ubuntu2404", 512, 10, "RAM"), ("ubuntu2604", 512, 10, "RAM"), ("centos10", 512, 10, "RAM"), ("kali", 2048, 20, "25 GB")])
def test_minimum_checked_before_wallet_or_proxmox(client, db, headers, seed, images, instance_payload, mock_proxmox, ma, ram, disk, reason):
    seed["plan"].ram_mb, seed["plan"].disk_gb = ram, disk
    seed["user"].wallet.balance = 0
    db.commit()
    result = client.post("/api/v1/instances", headers=headers["user"], json={**instance_payload, "os_ma": ma})
    assert result.status_code == 422 and reason in result.json()["detail"]
    mock_proxmox[0].assert_not_called()
    assert db.scalar(select(Instance.id)) is None and seed["node"].used_vcpu == 0


@pytest.mark.parametrize("ma", ["debian13", "ubuntu2404", "ubuntu2604", "centos10", "kali"])
def test_linux_creation_uses_mapping(client, db, headers, seed, images, instance_payload, mock_proxmox, ma):
    image = images[ma]
    seed["plan"].ram_mb, seed["plan"].disk_gb = image.min_ram_mb, image.min_disk_gb
    if ma != "debian13":
        seed["node"].os_templates.append(NodeOSTemplate(os_image=image, template_id=9010 + image.thu_tu))
    db.commit()
    result = client.post("/api/v1/instances", headers=headers["user"], json={**instance_payload, "os_ma": ma})
    assert result.status_code == 201, result.text
    instance = db.get(Instance, result.json()["id"])
    assert instance.os_image_id == image.id and instance.ket_noi == "ssh"
    assert mock_proxmox[1].clone_template.call_args.args[0] == instance.template_id


def test_default_debian_and_no_fallback_when_mapping_removed(client, db, headers, seed, instance_payload, mock_proxmox):
    seed["node"].os_templates.clear()
    db.commit()
    result = client.post("/api/v1/instances", headers=headers["user"], json=instance_payload)
    assert result.status_code == 503 and "Debian 13" in result.json()["detail"]
    mock_proxmox[0].assert_not_called()


def test_unknown_os(client, headers, images, instance_payload, mock_proxmox):
    result = client.post("/api/v1/instances", headers=headers["user"], json={**instance_payload, "os_ma": "missing"})
    assert result.status_code == 422 and "danh mục" in result.json()["detail"]
    mock_proxmox[0].assert_not_called()


@pytest.mark.parametrize("ma", ["winserver2022", "windows11"])
@pytest.mark.parametrize("username", [None, "binh"])
def test_windows_password_rdp_and_reinstall(client, db, headers, seed, images, mock_proxmox, monkeypatch, ma, username):
    seed["plan"].ram_mb, seed["plan"].disk_gb = 4096, 64
    seed["node"].os_templates.append(NodeOSTemplate(os_image=images[ma], template_id=9020))
    db.commit()
    mock_proxmox[1].get_ip.return_value = "10.0.0.2"
    body = {"ten": "windows-vps", "plan_id": seed["plan"].id, "os_ma": ma}
    if username:
        body["cloud_user"] = username
    result = client.post("/api/v1/instances", headers=headers["user"], json=body)
    assert result.status_code == 201, result.text
    instance = db.get(Instance, result.json()["id"])
    password = decrypt_secret(instance.password_encrypted)
    assert len(password) == 8 and sum(any(t(c) for c in password) for t in (str.isupper, str.islower, str.isdigit, lambda c: not c.isalnum())) == 4 and instance.password_encrypted != password and password not in result.text
    assert instance.ssh_public_key is None and instance.cloud_user == "tbtadmin"
    configured = mock_proxmox[1].configure_cloud_init.call_args
    assert configured.args[4] is None and configured.kwargs["password"] == password
    path = f"/api/v1/instances/{instance.id}"
    monkeypatch.setattr(get_settings(), "gateway_host", "2001:db8::1")
    connection = client.get(path + "/credentials", headers=headers["user"])
    assert connection.headers["cache-control"] == "no-store"
    assert connection.json()["dia_chi"] == f"[2001:db8::1]:{instance.ssh_port}" and connection.json()["ket_noi"] == "rdp"
    assert connection.json()["password"] == password
    assert client.get(path + "/credentials", headers=headers["other"]).status_code == 404
    assert client.get(path + "/credentials").status_code == 401
    detail = client.get(path + "/detail", headers=headers["user"]).json()
    assert detail["ten_he_dieu_hanh"] == images[ma].ten and detail["ket_noi"] == "rdp"
    mock_proxmox[1].get_template_name.assert_not_called()
    monkeypatch.setattr(get_settings(), "agent_token", SimpleNamespace(get_secret_value=lambda: "fixture-agent-token"))
    ports = client.get("/api/v1/agent/ports?node=pve", headers={"X-Agent-Token": "fixture-agent-token"}).json()
    assert ports == [{"ssh_port": instance.ssh_port, "port": instance.ssh_port, "target_port": 3389, "ip": "10.0.0.2", "vmid": instance.vmid}]
    seed["node"].os_templates.clear()
    db.commit()
    mock_proxmox[1].reset_mock()
    result = client.post(path + "/reinstall", headers=headers["user"])
    assert result.status_code == 200, result.text
    assert mock_proxmox[1].clone_template.call_args.args[0] == 9020
    assert decrypt_secret(instance.password_encrypted) != password
    assert instance.os_image_id == images[ma].id
    assert password not in str(list(db.scalars(select(AuditLog.detail))))


@pytest.mark.parametrize("strategy", ["best-fit", "least-loaded"])
def test_scheduler_requires_selected_os_and_capacity(db, seed, images, strategy):
    plan = SimpleNamespace(vcpu=1, ram_mb=1024, disk_gb=10)
    base = {key: getattr(seed["node"], key) for key in ("trang_thai", "total_vcpu", "total_ram_mb", "total_disk_gb", "used_vcpu", "used_ram_mb", "used_disk_gb")}
    mapping = SimpleNamespace(os_image_id=images["ubuntu2404"].id, template_id=9010)
    nodes = [SimpleNamespace(**base, id=1, vm_template_id=9000, os_templates=[]), SimpleNamespace(**base, id=2, vm_template_id=None, os_templates=[mapping])]
    assert select_node(nodes, plan, strategy, os_image=images["ubuntu2404"]).id == 2
    for field, value in [("trang_thai", "offline"), ("used_ram_mb", 16384), ("used_vcpu", 8), ("used_disk_gb", 200)]:
        previous = getattr(nodes[1], field)
        setattr(nodes[1], field, value)
        with pytest.raises(HTTPException) as error:
            select_node(nodes, plan, strategy, os_image=images["ubuntu2404"])
        assert error.value.status_code == 503
        setattr(nodes[1], field, previous)


@pytest.mark.parametrize("kind", ["vm", "lxc"])
def test_configure_onboot_and_no_ssh_for_windows(seed, kind):
    client = object.__new__(ProxmoxClient)
    client.node = seed["node"]
    guest = MagicMock()
    guest.config.get.return_value = {"scsi0" if kind == "vm" else "rootfs": "local:disk,size=8G", "hookscript": "local:snippets/hook.sh"}
    guest.config.put.return_value = None
    guest.resize.put.return_value = None
    client._guest = lambda vmid, loai: guest
    client.configure_cloud_init(101, kind, SimpleNamespace(vcpu=2, ram_mb=4096, disk_gb=64), "tbtadmin" if kind == "vm" else "root", None if kind == "vm" else "ssh-key", password="FixturePassword123")
    options = guest.config.put.call_args.kwargs
    assert options["onboot"] == 1
    if kind == "vm":
        assert options["ciuser"] == "tbtadmin" and options["cipassword"] == "FixturePassword123" and "sshkeys" not in options


def test_os_migration_preserves_legacy_data_and_reupgrades(tmp_path, monkeypatch, seed):
    url = "sqlite+pysqlite:///" + (tmp_path / "os.sqlite").as_posix()
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0005_plan_catalog")
    engine = create_engine(url)
    nodes = Table("nodes", MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(nodes.insert().values(**{column.name: getattr(seed["node"], column.name) for column in nodes.columns}))
        connection.execute(text("INSERT INTO users (id,email,password_hash,role,created_at) VALUES (1,'legacy@example.test','unused','user',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO wallets (user_id,balance) VALUES (1,12345)"))
        for row_id, kind, service in [(101, "vm", "vps"), (102, "lxc", "vps"), (103, "vm", "postgres")]:
            connection.execute(text("INSERT INTO instances (id,ten,user_id,node_id,plan_id,vmid,loai,dich_vu,trang_thai,vcpu,ram_mb,disk_gb,gia_theo_gio,created_at) VALUES (:id,'legacy',1,:node,1,:id,:kind,:service,'running',1,1024,10,10,CURRENT_TIMESTAMP)"), {"id": row_id, "node": seed["node"].id, "kind": kind, "service": service})
    engine.dispose()
    command.upgrade(config, "0006_os_images")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM os_images")) == 7
        assert connection.scalar(text("SELECT template_id FROM node_os_templates")) == 9000
        assert connection.scalar(text("SELECT os_images.ma FROM instances JOIN os_images ON instances.os_image_id=os_images.id WHERE instances.id=101")) == "debian13"
        assert connection.scalar(text("SELECT COUNT(*) FROM instances WHERE os_image_id IS NULL")) == 2
        assert connection.scalar(text("SELECT COUNT(*) FROM plans WHERE ten LIKE 'Windows%'")) == 2
        assert connection.scalar(text("SELECT balance FROM wallets")) == 12345
        assert connection.execute(text("SELECT ram_mb,disk_gb,gia_theo_gio FROM plans WHERE ten='Windows Tiêu chuẩn'")).one() == (4096, 64, 2500)
    engine.dispose()
    command.downgrade(config, "0005_plan_catalog")
    engine = create_engine(url)
    assert "os_images" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM instances")) == 3
        assert connection.scalar(text("SELECT balance FROM wallets")) == 12345
    engine.dispose()
    command.upgrade(config, "0006_os_images")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM plans WHERE ten LIKE 'Windows%'")) == 2
    engine.dispose()
