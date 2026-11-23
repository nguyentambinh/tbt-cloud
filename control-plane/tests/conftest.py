# Nguyễn Tâm Bình - 2324801030003
import os
import socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

os.environ["JWT_SECRET"] = "test-only-jwt-key-000000000000000000000000"
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["WORKERS_ENABLED"] = "false"
os.environ["VIRTUAL_TOPUP_ENABLED"] = "true"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base, get_db
from app.main import app
from app.models import AllocationLock, Instance, Node, NodeOSTemplate, OSImage, Plan, User, Wallet
from app.security import create_access_token, encrypt_secret, hash_password


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    original_connect = socket.socket.connect

    def reject(*args, **kwargs):
        raise AssertionError("Kiểm thử không được mở kết nối mạng thật.")

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        return reject()

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", reject)


@pytest.fixture
def notify_settings(monkeypatch, tmp_path):
    from app.services import notify

    password_file = tmp_path / "smtp-test.txt"
    password_file.write_text(" fake app \r\n password \n", encoding="utf-8")
    for key, value in {"notify_enabled": True, "smtp_user": "sender@example.com", "smtp_password_file": str(password_file), "notify_to": "admin@example.com, second@example.com"}.items():
        monkeypatch.setattr(get_settings(), key, value)
    monkeypatch.setattr(notify, "start_sender", lambda: None)
    return get_settings()


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        session.add(AllocationLock(id=1))
        session.commit()
        yield session
        session.rollback()
    engine.dispose()


@pytest.fixture
def seed(db):
    user = User(email="owner@example.com", password_hash=hash_password("Owner-password-123"))
    other = User(email="other@example.com", password_hash=hash_password("Other-password-123"))
    admin = User(email="admin@example.com", password_hash=hash_password("Admin-password-123"), role="admin")
    plan = Plan(ten="Small", vcpu=1, ram_mb=512, disk_gb=10, gia_theo_gio=Decimal("10.00"))
    node = Node(ten="node-1", api_url="https://100.64.0.1:8006", token_id="cloud@pve!control", token_secret=encrypt_secret("dummy-token"), mesh_ip="100.64.0.1", proxmox_node="pve", vm_template_id=9000, lxc_template_id=9001, trang_thai="online", total_vcpu=8, total_ram_mb=16384, total_disk_gb=200, last_seen_at=datetime.now(timezone.utc))
    db.add_all([user, other, admin, plan, node])
    debian = OSImage(ma="debian13", ten="Debian 13", ho="linux", min_ram_mb=512, min_disk_gb=10, ket_noi="ssh", thu_tu=1)
    db.add(debian)
    node.os_templates.append(NodeOSTemplate(os_image=debian, template_id=9000))
    db.flush()
    db.add_all([Wallet(user_id=user.id, balance=Decimal("100.00")), Wallet(user_id=other.id), Wallet(user_id=admin.id)])
    db.commit()
    return {"user": user, "other": other, "admin": admin, "plan": plan, "node": node}


@pytest.fixture
def instance(db, seed):
    plan = seed["plan"]
    value = Instance(ten="server-1", user_id=seed["user"].id, node_id=seed["node"].id, plan_id=plan.id, vmid=101, loai="vm", trang_thai="running", vcpu=plan.vcpu, ram_mb=plan.ram_mb, disk_gb=plan.disk_gb, gia_theo_gio=plan.gia_theo_gio, paid_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    db.add(value)
    db.commit()
    return value


@pytest.fixture
def client(db):
    def override_db():
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def headers(seed):
    return {name: {"Authorization": f"Bearer {create_access_token(seed[name].id)}"} for name in ("user", "other", "admin")}


@pytest.fixture
def mock_proxmox(monkeypatch):
    client = MagicMock()
    client.find_free_vmid.return_value = 102
    client.get_status.return_value = "running"
    client.get_ip.return_value = None
    factory = MagicMock(return_value=client)
    monkeypatch.setattr("app.services.instances.ProxmoxClient", factory)
    return factory, client


@pytest.fixture
def instance_payload(seed):
    key = Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH).decode()
    return {"ten": "server-new", "plan_id": seed["plan"].id, "loai": "vm", "cloud_user": "ubuntu", "ssh_public_key": key}
