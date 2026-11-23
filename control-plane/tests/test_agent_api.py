# Nguyễn Tâm Bình - 2324801030003
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError

from app.config import Settings, get_settings

TOKEN = "test-agent-token-000000000000000000000000"


@pytest.mark.parametrize("token", [None, "", "short", "é" * 15])
def test_agent_token_validation(token):
    values = dict(database_url="sqlite://", jwt_secret="test-jwt-secret-000000000000000000000", fernet_key=Fernet.generate_key().decode(), agent_token=token)
    if token is None:
        assert Settings(_env_file=None, **values).agent_token is None
    else:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **values)


def test_agent_token_byte_length_and_masking():
    settings = Settings(_env_file=None, database_url="sqlite://", jwt_secret="test-jwt-secret-000000000000000000000", fernet_key=Fernet.generate_key().decode(), agent_token="é" * 16)
    assert isinstance(settings.agent_token, SecretStr) and "é" not in repr(settings)


def test_agent_disabled_and_invalid_token(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_token", None)
    assert client.get("/api/v1/agent/ports?node=pve").status_code == 404
    monkeypatch.setattr(get_settings(), "agent_token", SecretStr(TOKEN))
    for token in (None, "wrong"):
        result = client.get("/api/v1/agent/ports?node=pve", headers={"X-Agent-Token": token} if token else {})
        assert result.status_code == 401 and TOKEN not in result.text


@pytest.mark.parametrize("state, ip, port, node, expected", [("running", "10.0.0.2", 22000, "pve", True), ("stopped", "10.0.0.2", 22000, "pve", False), ("suspended", "10.0.0.2", 22000, "pve", False), ("provisioning", "10.0.0.2", 22000, "pve", False), ("error", "10.0.0.2", 22000, "pve", False), ("deleted", "10.0.0.2", 22000, "pve", False), ("running", None, 22000, "pve", False), ("running", "10.0.0.2", None, "pve", False), ("running", "10.0.0.2", 22000, "different-node", False)])
def test_agent_ports_filters(client, db, instance, monkeypatch, state, ip, port, node, expected):
    monkeypatch.setattr(get_settings(), "agent_token", SecretStr(TOKEN))
    instance.trang_thai, instance.ip, instance.ssh_port = state, ip, port
    db.commit()
    result = client.get(f"/api/v1/agent/ports?node={node}", headers={"X-Agent-Token": TOKEN})
    assert result.status_code == 200
    assert result.json() == ([{"ssh_port": 22000, "port": 22000, "target_port": 22, "ip": "10.0.0.2", "vmid": instance.vmid}] if expected else [])
    assert result.headers["cache-control"] == "no-store"


def test_agent_ports_scope_all_includes_other_nodes(client, db, instance, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_token", SecretStr(TOKEN))
    instance.ip, instance.ssh_port = "10.20.20.5", 22001
    db.commit()
    only_node = client.get("/api/v1/agent/ports?node=edge", headers={"X-Agent-Token": TOKEN})
    every_node = client.get("/api/v1/agent/ports?node=edge&scope=all", headers={"X-Agent-Token": TOKEN})
    assert only_node.json() == []
    assert every_node.json() == [{"ssh_port": 22001, "port": 22001, "target_port": 22, "ip": "10.20.20.5", "vmid": instance.vmid}]
    assert client.get("/api/v1/agent/ports?node=edge&scope=other", headers={"X-Agent-Token": TOKEN}).status_code == 422


def test_agent_ipv6_prefix_and_addresses(client, db, seed, instance, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_token", SecretStr(TOKEN))
    head = {"X-Agent-Token": TOKEN}
    assert client.post("/api/v1/agent/ipv6?node=pve", json={"prefix": "2402:800:639e:f77c::/64"}).status_code == 401
    for bad in ("fd00::/64", "2402:800::/48", "khong-phai-ip"):
        assert client.post("/api/v1/agent/ipv6?node=pve", json={"prefix": bad}, headers=head).status_code == 422
    assert client.post("/api/v1/agent/ipv6?node=khong-co", json={"prefix": None}, headers=head).status_code == 404
    result = client.post("/api/v1/agent/ipv6?node=pve", json={"prefix": "2402:800:639e:f77c::/64"}, headers=head)
    assert result.status_code == 200 and result.json() == []
    db.refresh(seed["node"])
    assert seed["node"].ipv6_prefix == "2402:800:639e:f77c::/64"
    instance.ipv6 = "2402:800:639e:f77c::101"
    db.commit()
    assert client.post("/api/v1/agent/ipv6?node=pve", json={"prefix": "2402:800:639e:f77c::/64"}, headers=head).json() == [{"vmid": instance.vmid, "ipv6": "2402:800:639e:f77c::101"}]
    client.post("/api/v1/agent/ipv6?node=pve", json={"prefix": None}, headers=head)
    db.refresh(seed["node"])
    assert seed["node"].ipv6_prefix is None
