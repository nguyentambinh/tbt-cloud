# Nguyễn Tâm Bình - 2324801030003
import json
import subprocess
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text

from app.config import get_settings
from app.models import AuditLog, Payment, Plan, Transaction, User, Wallet
from app.security import create_access_token, verify_password
from app.services import backups

ROOT = "/api/v1/admin"


@pytest.mark.parametrize("method,path,body", [("GET", "/stats", None), ("GET", "/map", None), ("GET", "/users/1", None), ("GET", "/data/users", None), ("GET", "/backups", None), ("GET", "/revenue", None), ("GET", "/reports/daily/csv", None), ("PUT", "/users/1/state", {"is_blocked": True}), ("PUT", "/users/1/role", {"role": "admin"}), ("POST", "/users/1/reset-password", None), ("POST", "/users/1/wallet", {"amount": 1, "reason": "Điều chỉnh", "request_id": "request-001"}), ("DELETE", "/users/1", None), ("POST", "/plans", {}), ("PUT", "/plans/1", {}), ("DELETE", "/plans/1", None), ("PUT", "/nodes/1", {}), ("POST", "/backups", None), ("DELETE", "/backups/fake", None), ("POST", "/backups/fake/restore", {"confirmation": "KHOI PHUC"})])
def test_admin_permissions(client, headers, method, path, body):
    assert client.request(method, ROOT + path, json=body).status_code == 401
    assert client.request(method, ROOT + path, json=body, headers=headers["user"]).status_code == 403


def test_block_unlock_revokes_old_tokens(client, headers, seed):
    path = ROOT + f"/users/{seed['user'].id}/state"
    assert client.put(path, json={"is_blocked": True}, headers=headers["admin"]).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers["user"]).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": seed["user"].email, "password": "Owner-password-123"}).status_code == 403
    assert client.put(path, json={"is_blocked": False}, headers=headers["admin"]).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers["user"]).status_code == 401
    login = client.post("/api/v1/auth/login", json={"email": seed["user"].email, "password": "Owner-password-123"})
    assert login.status_code == 200
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}).status_code == 200


def test_self_admin_safeguards_and_role_change(client, db, seed, headers):
    admin_id = seed["admin"].id
    for method, suffix, body in [("PUT", "/state", {"is_blocked": True}), ("PUT", "/role", {"role": "user"}), ("DELETE", "", None)]:
        assert client.request(method, f"{ROOT}/users/{admin_id}{suffix}", json=body, headers=headers["admin"]).status_code == 409
    user_id = seed["user"].id
    assert client.put(f"{ROOT}/users/{user_id}/role", json={"role": "admin"}, headers=headers["admin"]).status_code == 200
    assert client.get(f"{ROOT}/users", headers=headers["user"]).status_code == 401
    promoted = {"Authorization": f"Bearer {create_access_token(user_id, seed['user'].token_version)}"}
    assert client.get(f"{ROOT}/stats", headers=promoted).status_code == 200
    assert client.put(f"{ROOT}/users/{admin_id}/role", json={"role": "user"}, headers=promoted).status_code == 200
    assert client.get(f"{ROOT}/stats", headers=headers["admin"]).status_code == 401
    assert db.scalar(select(func.count(User.id)).where(User.role == "admin", User.is_blocked.is_(False))) == 1


def test_reset_password_is_one_time_and_revokes(client, db, seed, headers):
    response = client.post(f"{ROOT}/users/{seed['user'].id}/reset-password", headers=headers["admin"])
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    password = response.json()["temporary_password"]
    assert verify_password(password, seed["user"].password_hash)
    assert client.get("/api/v1/auth/me", headers=headers["user"]).status_code == 401
    detail = client.get(f"{ROOT}/users/{seed['user'].id}", headers=headers["admin"])
    assert password not in detail.text and "temporary_password" not in detail.text
    assert password not in " ".join(db.scalars(select(AuditLog.detail)))


def test_adjustment_reason_idempotency_negative_and_audit(client, db, seed, headers):
    path = f"{ROOT}/users/{seed['user'].id}/wallet"
    body = {"amount": "25.50", "reason": "Bù dịch vụ gián đoạn", "request_id": "adjustment-001"}
    for invalid in [{**body, "reason": "  "}, {**body, "amount": 0}, {**body, "amount": "1.001"}, {**body, "reason": ""}]:
        assert client.post(path, json=invalid, headers=headers["admin"]).status_code == 422
    first = client.post(path, json=body, headers=headers["admin"])
    assert first.status_code == 200 and Decimal(str(first.json()["balance"])) == Decimal("125.50")
    assert client.post(path, json=body, headers=headers["admin"]).json() == first.json()
    assert client.post(path, json={**body, "amount": 30}, headers=headers["admin"]).status_code == 409
    assert client.post(path, json={**body, "amount": -200, "request_id": "adjustment-002"}, headers=headers["admin"]).status_code == 409
    assert db.scalar(select(func.count(Transaction.id)).where(Transaction.kind == "adjustment")) == 1
    assert db.scalar(select(AuditLog.detail).where(AuditLog.action == "admin.wallet.adjust")) == "25.50: Bù dịch vụ gián đoạn"


def test_delete_only_without_services_preserves_history(client, db, seed, instance, headers):
    path = f"{ROOT}/users/{seed['user'].id}"
    assert client.delete(path, headers=headers["admin"]).status_code == 409
    instance.trang_thai = "deleted"
    db.commit()
    assert client.delete(path, headers=headers["admin"]).status_code == 200
    assert seed["user"].deleted_at is not None and seed["user"].is_blocked
    assert client.get(path, headers=headers["admin"]).status_code == 404
    assert client.get("/api/v1/auth/me", headers=headers["user"]).status_code == 401
    assert seed["user"].id not in [row["id"] for row in client.get(ROOT + "/data/users", headers=headers["admin"]).json()["items"]]
    assert db.scalar(select(Wallet).where(Wallet.user_id == seed["user"].id)) is not None


@pytest.mark.parametrize("table", ["users", "instances", "transactions", "payments", "audit-logs", "plans", "nodes"])
def test_data_explicit_columns_no_secrets(client, seed, instance, headers, table):
    response = client.get(f"{ROOT}/data/{table}?limit=1", headers=headers["admin"])
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 1 and data["limit"] == 1
    for column in data["columns"]:
        assert not any(word in column for word in ["password", "secret", "token", "encrypted", "key"])
    for secret in [seed["user"].password_hash, seed["node"].token_secret]:
        assert secret not in response.text
    assert client.get(f"{ROOT}/data/{table}?column=password_hash&value=x", headers=headers["admin"]).status_code == 422


def test_data_search_filter_paging_csv_and_sql_rejected(client, seed, db, headers):
    seed["user"].ho_ten = "=HYPERLINK(1)"
    db.commit()
    assert client.get(ROOT + "/data/users?q=owner&limit=1", headers=headers["admin"]).json()["total"] == 1
    assert client.get(ROOT + "/data/users?column=is_blocked&value=false", headers=headers["admin"]).json()["total"] == 3
    assert client.get(ROOT + "/data/users?q=' OR 1=1 --", headers=headers["admin"]).json()["total"] == 0
    assert client.get(ROOT + "/data/users?limit=201", headers=headers["admin"]).status_code == 422
    assert client.get(ROOT + "/data/users?offset=-1", headers=headers["admin"]).status_code == 422
    assert client.get(ROOT + "/data/users?start=2026-11-25&end=2026-11-20", headers=headers["admin"]).status_code == 422
    assert client.get(ROOT + "/data/not-a-table", headers=headers["admin"]).status_code == 404
    csv = client.get(ROOT + "/data/users?csv=true", headers=headers["admin"])
    assert csv.status_code == 200 and "text/csv" in csv.headers["content-type"]
    assert "'=HYPERLINK" in csv.text and "password_hash" not in csv.text


def test_stats_paid_revenue_usage_only_range_and_map(client, db, seed, instance, headers):
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == seed["user"].id))
    now = datetime.now(timezone.utc)
    db.add_all([Transaction(wallet_id=wallet.id, amount=-10, kind="usage", idempotency_key="usage-1", description="Một giờ", created_at=now), Transaction(wallet_id=wallet.id, amount=100, kind="adjustment", idempotency_key="adjust-1", description="Điều chỉnh", created_at=now)])
    for index, status in enumerate(["paid", "pending", "paid"]):
        moment = now if index < 2 else now - timedelta(days=60)
        db.add(Payment(user_id=seed["user"].id, order_code=100 + index, amount=10000, status=status, checkout_url="https://fixture.invalid", qr_code="dummy", payment_link_id=str(index), paid_at=moment if status == "paid" else None, created_at=moment))
    db.commit()
    today = now.date().isoformat()
    response = client.get(ROOT + f"/stats?start={today}&end={today}", headers=headers["admin"])
    assert response.status_code == 200
    data = response.json()
    assert data["revenue"] == 10000 and Decimal(str(data["spent"])) == 10 and data["users"] == 3
    assert data["running"]["service"] == [{"name": "vps", "count": 1}]
    series = client.get(ROOT + "/revenue", headers=headers["admin"]).json()
    assert len(series["daily"]) == 30 and sum(row["amount"] for row in series["daily"]) == 10000
    assert len(series["monthly"]) == 12 and sum(Decimal(str(row["amount"])) for row in series["monthly"]) == 20000
    for report in ["totals", "daily", "monthly", "service", "os", "node", "top_customers", "nodes"]:
        assert client.get(ROOT + f"/reports/{report}/csv", headers=headers["admin"]).status_code == 200
    map = client.get(ROOT + "/map", headers=headers["admin"]).json()
    assert map["items"][0]["user_id"] == seed["user"].id
    detail = client.get(f"{ROOT}/users/{seed['user'].id}", headers=headers["admin"]).json()
    assert detail["instances"]["total"] == 1 and detail["transactions"]["total"] == 2


def test_plans_hidden_creation_blocked_and_snapshot_price(client, db, instance, seed, headers, instance_payload):
    payload = {"ten": "Small", "dich_vu": "vps", "mo_ta": "Cập nhật", "vcpu": 2, "ram_mb": 2048, "disk_gb": 20, "gia_theo_gio": 99, "active": False}
    path = f"{ROOT}/plans/{seed['plan'].id}"
    assert client.put(path, json=payload, headers=headers["admin"]).status_code == 200
    assert client.get("/api/v1/plans").json() == []
    assert client.post("/api/v1/instances", json=instance_payload, headers=headers["user"]).status_code == 404
    assert instance.gia_theo_gio == Decimal("10.00")
    assert client.delete(path, headers=headers["admin"]).status_code == 409
    added = client.post(ROOT + "/plans", json={**payload, "ten": "New"}, headers=headers["admin"])
    assert added.status_code == 201
    assert client.delete(ROOT + f"/plans/{added.json()['id']}", headers=headers["admin"]).status_code == 200


def test_admin_cannot_rent_or_top_up(client, headers, instance_payload, monkeypatch):
    monkeypatch.setattr("app.services.payos.create_payment", lambda *args: pytest.fail("Không được gọi payOS"))
    for path, body in [("/instances", instance_payload), ("/billing/topup", {"amount": 100, "request_id": "admin-topup"}), ("/billing/payos", {"amount": 10000})]:
        response = client.post("/api/v1" + path, json=body, headers=headers["admin"])
        assert response.status_code == 403 and "Quản trị viên" in response.json()["detail"]


@pytest.fixture
def fake_backup(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(settings, "backup_keep", 2)
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://cloud:dummy-password@localhost:5432/cloud")
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        assert isinstance(args, list) and kwargs["shell"] is False and kwargs["timeout"] == settings.backup_timeout
        assert "dummy-password" not in " ".join(args) and kwargs["env"]["PGPASSWORD"] == "dummy-password"
        if args[0] == "pg_dump":
            Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("--file="))).write_bytes(b"PGDMP-dummy-test")
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(backups.subprocess, "run", run)
    return calls


def test_backup_lifecycle_retention_confirmation_and_restore(client, db, seed, headers, fake_backup):
    names = []
    for _ in range(3):
        response = client.post(ROOT + "/backups", headers=headers["admin"])
        assert response.status_code == 201
        names.append(response.json()["name"])
    listing = client.get(ROOT + "/backups?limit=1", headers=headers["admin"]).json()
    assert listing["total"] == 2 and len(listing["items"]) == 1
    assert client.get(ROOT + f"/backups/{names[0]}/download", headers=headers["admin"]).status_code == 404
    assert client.get(ROOT + f"/backups/{names[-1]}/download", headers=headers["admin"]).content == b"PGDMP-dummy-test"
    path = ROOT + f"/backups/{names[-1]}/restore"
    assert client.post(path, json={"confirmation": "wrong"}, headers=headers["admin"]).status_code == 422
    before = len(fake_backup)
    result = client.post(path, json={"confirmation": "KHOI PHUC"}, headers=headers["admin"])
    assert result.status_code == 200
    assert [call[0][0] for call in fake_backup[before:]] == ["pg_dump", "pg_restore"]
    restore_args = fake_backup[-1][0]
    assert all(flag in restore_args for flag in ["--clean", "--if-exists", "--single-transaction"])
    assert backups.backup_path(result.json()["safety_backup"]).is_file()
    assert len(backups.listing()) == 2
    assert client.get("/api/v1/auth/me", headers=headers["admin"]).status_code == 401
    assert db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "admin.backup.restore")) == 1


def test_backup_failures_lock_and_traversal(client, headers, fake_backup, monkeypatch):
    for name in ["arbitrary.dump", "..%2Foutside.dump"]:
        assert client.get(ROOT + f"/backups/{name}/download", headers=headers["admin"]).status_code == 404
    with backups.operation():
        assert client.post(ROOT + "/backups", headers=headers["admin"]).status_code == 409
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("pg_dump", 120, stderr="dummy-secret-must-not-leak")
    monkeypatch.setattr(backups.subprocess, "run", fail)
    response = client.post(ROOT + "/backups", headers=headers["admin"])
    assert response.status_code == 503 and "dummy-secret" not in response.text
    assert backups.listing() == [] and not list(backups.root().glob("*.dump"))


def test_backup_delete_and_failed_safety_never_runs_restore(client, headers, fake_backup, monkeypatch):
    first = client.post(ROOT + "/backups", headers=headers["admin"]).json()
    assert client.delete(ROOT + f"/backups/{first['name']}", headers=headers["admin"]).status_code == 200
    assert backups.listing() == []
    target = client.post(ROOT + "/backups", headers=headers["admin"]).json()
    def fail(*args, **kwargs):
        raise FileNotFoundError("pg_dump")
    monkeypatch.setattr(backups.subprocess, "run", fail)
    result = client.post(ROOT + f"/backups/{target['name']}/restore", json={"confirmation": "KHOI PHUC"}, headers=headers["admin"])
    assert result.status_code == 503 and len(backups.listing()) == 1
    assert not any(call[0][0] == "pg_restore" for call in fake_backup)


def test_failed_restore_keeps_safety_and_rejects_old_sessions(client, headers, fake_backup, monkeypatch):
    target = client.post(ROOT + "/backups", headers=headers["admin"]).json()
    fake_run = backups.subprocess.run
    def fail_restore(args, **kwargs):
        if args[0] == "pg_restore":
            raise subprocess.CalledProcessError(1, args)
        return fake_run(args, **kwargs)
    monkeypatch.setattr(backups.subprocess, "run", fail_restore)
    response = client.post(ROOT + f"/backups/{target['name']}/restore", json={"confirmation": "KHOI PHUC"}, headers=headers["admin"])
    assert response.status_code == 503
    assert len(backups.listing()) == 2 and any(row["safety"] for row in backups.listing())
    assert client.get("/api/v1/auth/me", headers=headers["user"]).status_code == 401


def test_backup_requires_postgresql(client, headers, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path / "backups"))
    assert client.post(ROOT + "/backups", headers=headers["admin"]).status_code == 503
    assert backups.listing() == []


def test_admin_migration_preserves_data_and_adjustments(tmp_path, monkeypatch):
    url = "sqlite+pysqlite:///" + (tmp_path / "admin.sqlite").as_posix()
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0007_dang_ky_xac_nhan")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id,email,password_hash,role,username,created_at) VALUES (1,'old','hash','admin','admin',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO wallets (id,user_id,balance) VALUES (1,1,125)"))
    command.upgrade(config, "head")
    with engine.begin() as connection:
        assert connection.execute(text("SELECT is_blocked,token_version,username FROM users")).one() == (0, 0, "admin")
        connection.execute(text("INSERT INTO transactions (wallet_id,amount,kind,idempotency_key,description,created_at) VALUES (1,25,'adjustment','adjust-old','Bù tiền',CURRENT_TIMESTAMP)"))
        assert connection.scalar(text("SELECT COUNT(*) FROM sqlite_master WHERE name='uq_users_username_lower'")) == 1
    command.downgrade(config, "0007_dang_ky_xac_nhan")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT balance FROM wallets")) == 125
        assert connection.execute(text("SELECT kind,amount FROM transactions")).one() == ("topup", 25)
    command.upgrade(config, "head")
    engine.dispose()
