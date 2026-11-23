# Nguyễn Tâm Bình - 2324801030003
import base64
import json
from unittest.mock import MagicMock

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.models import Instance
from app.security import decrypt_secret
from app.services.port_mapper import allocate_app_port, allocate_ssh_port, release_app_port
from app.services.proxmox_client import ProxmoxClient
from app.services.scheduler import select_node


@pytest.mark.parametrize("kind,target", [("postgres", 5432), ("webapp", 80)])
def test_create_service_smbios_reinstall_and_delete(client, db, seed, headers, instance_payload, mock_proxmox, monkeypatch, kind, target):
    seed["node"].paas_template_id = 9001
    seed["plan"].dich_vu = kind
    db.commit()
    factory, proxmox = mock_proxmox
    payload = {**instance_payload, "dich_vu": kind}
    if kind == "webapp":
        payload.update(repo_url="https://example.test/app.git", branch="release/v1")
    result = client.post("/api/v1/instances", json=payload, headers=headers["user"])
    assert result.status_code == 201, result.text
    data = result.json()
    assert data["dich_vu"] == kind and data["app_port"] == 23000 and data["ssh_port"] == 22000
    instance = db.get(Instance, data["id"])
    config = json.loads(decrypt_secret(instance.app_config_encrypted))
    assert config["kind"] == kind and instance.template_id == 9001
    assert "app_config_encrypted" not in data and "password" not in data
    if kind == "postgres":
        assert config["db"] == config["user"] == "app" and len(config["password"]) >= 10
        assert config["password"] not in instance.app_config_encrypted
    else:
        assert config == {"kind": kind, "repo": payload["repo_url"], "branch": "release/v1"}
    serial = proxmox.configure_cloud_init.call_args.kwargs["smbios_serial"]
    assert json.loads(base64.b64decode(serial, validate=True)) == config
    proxmox.clone_template.assert_called_once_with(9001, 102, payload["ten"], "vm")
    real = object.__new__(ProxmoxClient)
    real.node = seed["node"]
    guest = MagicMock()
    guest.config.get.return_value = {"scsi0": "local-lvm:disk,size=10G"}
    guest.config.put.return_value = None
    monkeypatch.setattr(real, "_guest", lambda *args: guest)
    real.configure_cloud_init(102, "vm", instance, payload["cloud_user"], payload["ssh_public_key"], smbios_serial=serial)
    assert guest.config.put.call_args.kwargs["smbios1"] == f"serial={serial},base64=1"
    result = client.post(f"/api/v1/instances/{instance.id}/reinstall", headers=headers["user"])
    assert result.status_code == 200, result.text
    assert proxmox.configure_cloud_init.call_args.kwargs["smbios_serial"] == serial
    monkeypatch.setattr(get_settings(), "agent_token", SecretStr("test-agent-token-000000000000000000000000"))
    instance.ip = "10.0.0.10"
    db.commit()
    for scope, node in (("node", "pve"), ("all", "edge")):
        rows = client.get(f"/api/v1/agent/ports?node={node}&scope={scope}", headers={"X-Agent-Token": get_settings().agent_token.get_secret_value()}).json()
        assert [(row["ssh_port"], row["target_port"]) for row in rows] == [(22000, 22), (23000, target)]
        assert all(row["port"] == row["ssh_port"] for row in rows)
    assert client.get("/api/v1/agent/ports?node=other", headers={"X-Agent-Token": get_settings().agent_token.get_secret_value()}).json() == []
    path = f"/api/v1/instances/{instance.id}/service"
    monkeypatch.setattr(get_settings(), "gateway_host", "2001:db8::1")
    for who in ("user", "admin"):
        result = client.get(path, headers=headers[who])
        assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
        service = result.json()
        assert service["dich_vu"] == kind and service["port"] == 23000
        if kind == "postgres":
            assert service["connection_string"] == f"postgresql://app:{config['password']}@[2001:db8::1]:23000/app"
            assert service["url"] is None and service["repo_url"] is None
        else:
            assert service["url"] == "http://[2001:db8::1]:23000" and service["connection_string"] is None
            assert service["repo_url"] == payload["repo_url"] and service["branch"] == "release/v1"
    assert client.get(path, headers=headers["other"]).status_code == 404
    assert client.get(path).status_code == 401
    result = client.delete(f"/api/v1/instances/{instance.id}", headers=headers["user"])
    assert result.status_code == 200 and result.json()["app_port"] is None and result.json()["ssh_port"] is None
    assert client.get(path, headers=headers["user"]).status_code == 404


def test_vps_service_not_found(client, headers, instance):
    result = client.get(f"/api/v1/instances/{instance.id}/service", headers=headers["user"])
    assert result.status_code == 404 and "VPS" in result.json()["detail"]


@pytest.mark.parametrize("url", ["http://example.test/repo", "https://user:pass@example.test/repo", "https://user@example.test/repo", "https://example.test/a b", "https://example.test/`id`", "https://example.test/ứng-dụng", "https://example.test/<>bad", "https://example.test/%GG", "https://", "https://example.test/" + "a" * 300])
def test_invalid_repo_returns_422(client, headers, instance_payload, url):
    result = client.post("/api/v1/instances", json={**instance_payload, "dich_vu": "webapp", "repo_url": url}, headers=headers["user"])
    assert result.status_code == 422


@pytest.mark.parametrize("extra", [{"dich_vu": "webapp"}, {"dich_vu": "postgres", "loai": "lxc", "cloud_user": "root"}, {"dich_vu": "webapp", "repo_url": "https://example.test/repo", "loai": "lxc", "cloud_user": "root"}, {"dich_vu": "webapp", "repo_url": "https://example.test/repo", "branch": "main;id"}])
def test_service_input_requirements(client, headers, instance_payload, extra):
    assert client.post("/api/v1/instances", json={**instance_payload, **extra}, headers=headers["user"]).status_code == 422


def test_scheduler_requires_paas_template(seed):
    node, plan = seed["node"], seed["plan"]
    with pytest.raises(HTTPException) as error:
        select_node([node], plan, dich_vu="postgres")
    assert error.value.status_code == 503
    node.paas_template_id, node.vm_template_id = 9001, None
    assert select_node([node], plan, dich_vu="webapp") == node


def test_allocate_release_app_port(db, instance):
    assert allocate_app_port(db, instance) is None
    instance.dich_vu = "postgres"
    assert allocate_app_port(db, instance, 23000, 23000) == 23000
    assert allocate_app_port(db, instance, 23000, 23000) == 23000
    other = Instance(ten="second", user_id=instance.user_id, node_id=instance.node_id, plan_id=instance.plan_id, vmid=102, loai="vm", dich_vu="webapp", vcpu=1, ram_mb=512, disk_gb=10, gia_theo_gio=instance.gia_theo_gio)
    db.add(other)
    db.flush()
    with pytest.raises(HTTPException) as error:
        allocate_app_port(db, other, 23000, 23000)
    assert error.value.status_code == 503
    with pytest.raises(ValueError):
        release_app_port(db, instance)
    with pytest.raises(ValueError):
        allocate_app_port(db, other, 23999, 23000)
    instance.trang_thai = "deleted"
    release_app_port(db, instance)
    assert allocate_app_port(db, other, 23000, 23000) == 23000
    assert allocate_ssh_port(db, instance, 23000, 23001) == 23001
    assert allocate_app_port(db, instance, 23000, 23002) == 23002


@pytest.mark.parametrize("field,value", [("dich_vu", "invalid"), ("app_port", 1023), ("app_port", 65536)])
def test_database_checks_service(db, instance, field, value):
    setattr(instance, field, value)
    with pytest.raises(IntegrityError):
        db.flush()


def test_database_app_port_unique(db, instance):
    instance.dich_vu, instance.app_port = "postgres", 23000
    db.flush()
    db.add(Instance(ten="duplicate", user_id=instance.user_id, node_id=instance.node_id, plan_id=instance.plan_id, vmid=102, loai="vm", dich_vu="webapp", app_port=23000, vcpu=1, ram_mb=512, disk_gb=10, gia_theo_gio=instance.gia_theo_gio))
    with pytest.raises(IntegrityError):
        db.flush()


def test_no_paas_template_rejects_before_provision(client, db, seed, headers, instance_payload, mock_proxmox):
    seed["plan"].dich_vu = "postgres"
    db.commit()
    result = client.post("/api/v1/instances", json={**instance_payload, "dich_vu": "postgres"}, headers=headers["user"])
    assert result.status_code == 503
    mock_proxmox[0].assert_not_called()


def test_webapp_default_branch_and_vps_no_app_port(client, db, seed, headers, instance_payload, mock_proxmox):
    result = client.post("/api/v1/instances", json=instance_payload, headers=headers["user"])
    assert result.status_code == 201 and result.json()["dich_vu"] == "vps" and result.json()["app_port"] is None
    assert "smbios_serial" not in mock_proxmox[1].configure_cloud_init.call_args.kwargs
    seed["node"].paas_template_id = 9001
    seed["plan"].dich_vu = "webapp"
    db.commit()
    mock_proxmox[1].find_free_vmid.return_value = 103
    result = client.post("/api/v1/instances", json={**instance_payload, "dich_vu": "webapp", "repo_url": "https://example.test/app.git"}, headers=headers["user"])
    assert result.status_code == 201
    config = json.loads(base64.b64decode(mock_proxmox[1].configure_cloud_init.call_args.kwargs["smbios_serial"]))
    assert config["branch"] == "main"


def test_reinstall_missing_service_config_keeps_guest(client, db, headers, instance, instance_payload, mock_proxmox):
    instance.dich_vu, instance.cloud_user, instance.ssh_public_key, instance.template_id = "postgres", "ubuntu", instance_payload["ssh_public_key"], 9001
    db.commit()
    result = client.post(f"/api/v1/instances/{instance.id}/reinstall", headers=headers["user"])
    assert result.status_code == 409
    mock_proxmox[1].delete.assert_not_called()
    mock_proxmox[1].clone_template.assert_not_called()


def test_node_schema_paas_template(client, headers):
    payload = {"ten": "paas-node", "api_url": "https://100.64.0.10:8006", "token_id": "cloud@pve!control", "token_secret": "fixture-token", "mesh_ip": "100.64.0.10", "proxmox_node": "paas-node", "paas_template_id": 9001}
    result = client.post("/api/v1/nodes", json=payload, headers=headers["admin"])
    assert result.status_code == 201 and result.json()["paas_template_id"] == 9001
    assert "token_secret" not in result.json()


def test_paas_migration_preserves_existing_data_and_downgrades(tmp_path, monkeypatch, instance):
    url = "sqlite+pysqlite:///" + (tmp_path / "paas.sqlite").as_posix()
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0003_payos_notify")
    engine = create_engine(url)
    table = Table("instances", MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(table.insert().values(**{column.name: getattr(instance, column.name) for column in table.columns}))
    engine.dispose()
    command.upgrade(config, "0004_paas")
    engine = create_engine(url)
    table = Table("instances", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        row = connection.execute(select(table)).mappings().one()
        assert row["dich_vu"] == "vps" and row["app_port"] is None and row["app_config_encrypted"] is None
        assert row["vmid"] == instance.vmid
    assert "paas_template_id" in {column["name"] for column in inspect(engine).get_columns("nodes")}
    engine.dispose()
    command.downgrade(config, "0003_payos_notify")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT vmid FROM instances")) == instance.vmid
    assert "dich_vu" not in {column["name"] for column in inspect(engine).get_columns("instances")}
    assert "paas_template_id" not in {column["name"] for column in inspect(engine).get_columns("nodes")}
    engine.dispose()
