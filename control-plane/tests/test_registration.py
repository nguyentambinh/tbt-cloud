# Nguyễn Tâm Bình - 2324801030003
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base
from app.models import AuditLog, PendingRegistration, User, Wallet
from app.schemas import RegistrationVerify
from app.security import verify_password
from app.services import notify, registration


@pytest.fixture
def mail(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "send_registration_code", lambda *args: sent.append(args))
    return sent


@pytest.fixture
def payload():
    return {"ho_ten": "Nguyễn Tâm Bình", "username": "Binh.003", "email": "Binh003@example.com", "password": "Binh@123", "password_confirm": "Binh@123"}


@pytest.fixture
def now(monkeypatch):
    value = [registration.utcnow()]
    monkeypatch.setattr(registration, "utcnow", lambda: value[0])
    return value


def verify(client, payload, code):
    return client.post("/api/v1/auth/register/verify", json={"email": payload["email"], "code": code})


def test_pending_has_only_hashes_no_account_wallet_or_login(client, db, payload, mail, now, caplog):
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 202 and response.json() == {"email_masked": "b***@example.com", "detail": "Đã gửi mã xác nhận. Vui lòng kiểm tra hộp thư.", "resend_after": 60, "expires_in": 600}
    row = db.get(PendingRegistration, "binh003@example.com")
    assert row.ho_ten == payload["ho_ten"] and row.username == "binh.003"
    assert row.password_hash.startswith("$argon2") and verify_password(payload["password"], row.password_hash)
    assert len(mail[0][2]) == 6 and mail[0][2].isascii() and mail[0][2].isdigit()
    assert row.code_hash == registration.digest_code(row.email, mail[0][2]) and row.code_hash != mail[0][2]
    assert registration.as_utc(row.expires_at) == now[0] + timedelta(minutes=10)
    for model in (User, Wallet, AuditLog):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    for identifier in (payload["email"], payload["username"]):
        assert client.post("/api/v1/auth/login", json={"email": identifier, "password": payload["password"]}).status_code == 401
    assert payload["password"] not in response.text + caplog.text and mail[0][2] not in response.text + caplog.text


def test_verify_creates_one_account_wallet_and_token(client, db, payload, mail):
    assert client.post("/api/v1/auth/register", json=payload).status_code == 202
    response = verify(client, payload, mail[0][2])
    assert response.status_code == 200 and response.json()["token_type"] == "bearer"
    auth = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=auth).json()
    assert me["ho_ten"] == payload["ho_ten"] and me["username"] == "binh.003"
    assert "hash" not in str(me) and "password" not in str(me)
    assert client.get("/api/v1/billing/balance", headers=auth).json()["balance"] == "0.00"
    assert db.get(PendingRegistration, "binh003@example.com") is None
    assert verify(client, payload, mail[0][2]).status_code == 400
    assert db.scalar(select(func.count(User.id))) == 1 and db.scalar(select(func.count(Wallet.user_id))) == 1
    for identifier in ("BINH.003", "BINH003@EXAMPLE.COM"):
        assert client.post("/api/v1/auth/login", json={"email": identifier, "password": payload["password"]}).status_code == 200


def test_five_wrong_codes_persist_and_lock_even_correct_code(client, db, payload, mail):
    client.post("/api/v1/auth/register", json=payload)
    wrong = "000000" if mail[0][2] != "000000" else "111111"
    for attempts in range(1, 6):
        response = verify(client, payload, wrong)
        assert response.status_code == 400 and str(5 - attempts) in response.json()["detail"]
        db.expire_all()
        assert db.get(PendingRegistration, "binh003@example.com").failed_attempts == attempts
    assert "khóa" in verify(client, payload, mail[0][2]).json()["detail"]
    assert db.scalar(select(User)) is None


def test_expiry_exact_boundary_and_resend_unlocks(client, db, payload, mail, now):
    client.post("/api/v1/auth/register", json=payload)
    now[0] += timedelta(minutes=10)
    assert "hết hạn" in verify(client, payload, mail[0][2]).json()["detail"]
    db.get(PendingRegistration, "binh003@example.com").failed_attempts = 5
    db.commit()
    assert client.post("/api/v1/auth/register/resend", json={"email": payload["email"]}).status_code == 202
    row = db.get(PendingRegistration, "binh003@example.com")
    assert row.failed_attempts == 0 and registration.as_utc(row.expires_at) == now[0] + timedelta(minutes=10)
    assert verify(client, payload, mail[-1][2]).status_code == 200


def test_resend_and_re_registration_share_cooldown_hourly_limit(client, payload, mail, now):
    assert client.post("/api/v1/auth/register", json=payload).status_code == 202
    for path, data in [("", payload), ("/resend", {"email": payload["email"]})]:
        response = client.post("/api/v1/auth/register" + path, json=data)
        assert response.status_code == 429 and response.headers["retry-after"] == "60"
    now[0] += timedelta(seconds=59)
    assert client.post("/api/v1/auth/register/resend", json={"email": payload["email"]}).headers["retry-after"] == "1"
    now[0] += timedelta(seconds=1)
    for _ in range(4):
        assert client.post("/api/v1/auth/register/resend", json={"email": payload["email"]}).status_code == 202
        now[0] += timedelta(seconds=60)
    assert len(mail) == 5
    for path, data in [("", payload), ("/resend", {"email": payload["email"]})]:
        assert client.post("/api/v1/auth/register" + path, json=data).status_code == 429
    now[0] += timedelta(seconds=3300)
    assert client.post("/api/v1/auth/register/resend", json={"email": payload["email"]}).status_code == 202


def test_re_registration_replaces_pending_and_old_code(client, db, payload, mail, now, monkeypatch):
    codes = iter([123456, 654321])
    monkeypatch.setattr(registration.secrets, "randbelow", lambda _: next(codes))
    client.post("/api/v1/auth/register", json=payload)
    now[0] += timedelta(seconds=60)
    updated = dict(payload, username="new.name", ho_ten="Nguyễn Bình", password="Changed@123", password_confirm="Changed@123")
    assert client.post("/api/v1/auth/register", json=updated).status_code == 202
    assert db.scalar(select(func.count()).select_from(PendingRegistration)) == 1
    assert verify(client, payload, "123456").status_code == 400
    assert verify(client, payload, "654321").status_code == 200
    user = db.scalar(select(User))
    assert user.username == "new.name" and user.ho_ten == "Nguyễn Bình" and verify_password("Changed@123", user.password_hash)


@pytest.mark.parametrize("field,value", [("ho_ten", "A"), ("ho_ten", "A" * 81), ("ho_ten", "Bình 123"), ("ho_ten", "Bình\nTâm"), ("ho_ten", "Bình<script>"), ("username", "ab"), ("username", "a" * 31), ("username", "1binh"), ("username", "bình"), ("username", "a-binh"), ("username", " abcd"), ("email", "admin"), ("email", "a b@example.com"), ("password", "Ab1@aaa"), ("password", "a" * 129), ("password", "abcdefgh1@"), ("password", "ABCDEFGH1@"), ("password", "Abcdefgh@"), ("password", "Abcdefgh1"), ("password", "Abcd 123@"), ("password", "Abcd\u00a0123@"), ("password_confirm", "Different@123"), ("role", "admin")])
def test_invalid_registration_has_no_effect(client, db, payload, mail, field, value):
    data = dict(payload, **{field: value})
    if field == "password":
        data["password_confirm"] = value
    response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422 and not mail
    assert data["password"] not in response.text and data["password_confirm"] not in response.text
    assert db.scalar(select(PendingRegistration)) is None and db.scalar(select(User)) is None


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "１２３４５６", 123456])
def test_invalid_code_format(client, payload, mail, code):
    client.post("/api/v1/auth/register", json=payload)
    assert verify(client, payload, code).status_code == 422


def test_missing_pending_has_clear_errors(client):
    assert client.post("/api/v1/auth/register/resend", json={"email": "missing@example.com"}).status_code == 400
    assert client.post("/api/v1/auth/register/verify", json={"email": "missing@example.com", "code": "123456"}).status_code == 400


def test_conflicts_at_start_and_verification(client, db, payload, mail, seed):
    seed["user"].username = "binh.003"
    db.commit()
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409 and "Tên tài khoản" in response.json()["detail"]
    response = client.post("/api/v1/auth/register", json=dict(payload, username="available", email="OWNER@EXAMPLE.COM"))
    assert response.status_code == 409 and "Email" in response.json()["detail"] and not mail
    data = dict(payload, username="available")
    assert client.post("/api/v1/auth/register", json=data).status_code == 202
    seed["other"].username = "AVAILABLE"
    db.commit()
    assert verify(client, data, mail[-1][2]).status_code == 409
    assert db.scalar(select(func.count(User.id))) == 3 and db.scalar(select(func.count(Wallet.user_id))) == 3


def test_smtp_failure_rolls_back_new_and_existing_pending(client, db, payload, mail, monkeypatch, now, caplog):
    client.post("/api/v1/auth/register", json=payload)
    original = db.get(PendingRegistration, "binh003@example.com").code_hash
    now[0] += timedelta(seconds=60)
    def fail(*args):
        raise RuntimeError("smtp-secret-library-error password")
    monkeypatch.setattr(notify, "send_registration_code", fail)
    for path, data in [("/resend", {"email": payload["email"]}), ("", dict(payload, username="changed")), ("", dict(payload, email="new@example.com"))]:
        response = client.post("/api/v1/auth/register" + path, json=data)
        assert response.status_code == 503 and "smtp-secret" not in response.text + caplog.text
    db.expire_all()
    row = db.get(PendingRegistration, "binh003@example.com")
    assert row.code_hash == original and row.username == "binh.003" and row.send_count == 1
    assert db.get(PendingRegistration, "new@example.com") is None
    assert verify(client, payload, mail[0][2]).status_code == 200


def test_registration_mail_uses_shared_transport_html_and_safe_recipient(notify_settings, monkeypatch):
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    connect = MagicMock(return_value=smtp)
    monkeypatch.setattr(notify.smtplib, "SMTP", connect)
    notify.send_registration_code("recipient@example.com", "Nguyễn <Bình>", "012345")
    connect.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("sender@example.com", "fakeapppassword")
    message = smtp.send_message.call_args.args[0]
    assert str(message["To"]) == "recipient@example.com" and message["Subject"] == "[TBT Cloud] Mã xác nhận đăng ký"
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "Nguyễn &lt;Bình&gt;" in html and "012345" in html and "10 phút" in html
    assert "Nếu bạn không đăng ký, hãy bỏ qua thư này." in html
    assert "fakeapppassword" not in message.as_string()


def test_username_unique_case_insensitive_and_old_login(client, db, seed):
    seed["admin"].username = "admin"
    seed["admin"].email = "ADMIN"
    seed["other"].username = "ADMIN"
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    seed["admin"].email = "ADMIN"
    db.commit()
    assert client.post("/api/v1/auth/login", json={"email": "admin", "password": "Admin-password-123"}).status_code == 200


def test_registration_migration_up_down_preserves_users_wallets(tmp_path, monkeypatch):
    url = "sqlite+pysqlite:///" + (tmp_path / "registration.sqlite").as_posix()
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0006_os_images")
    engine = create_engine(url)
    with engine.begin() as connection:
        for user_id, email in [(1, "admin"), (2, "old@example.com"), (3, "ab"), (4, "ADMIN")]:
            connection.execute(text("INSERT INTO users (id,email,password_hash,role,created_at) VALUES (:id,:email,'legacy-hash','user',CURRENT_TIMESTAMP)"), {"id": user_id, "email": email})
            connection.execute(text("INSERT INTO wallets (user_id,balance) VALUES (:id,12345)"), {"id": user_id})
    engine.dispose()
    command.upgrade(config, "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0011_thong_bao"
        assert connection.execute(text("SELECT id,username,ho_ten FROM users ORDER BY id")).all() == [(1, "admin", None), (2, None, None), (3, None, None), (4, None, None)]
        assert connection.scalar(text("SELECT SUM(balance) FROM wallets")) == 49380
        assert connection.scalar(text("SELECT COUNT(*) FROM pending_registrations")) == 0
    engine.dispose()
    command.downgrade(config, "0006_os_images")
    engine = create_engine(url)
    assert "pending_registrations" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM users WHERE password_hash='legacy-hash'")) == 4
        assert connection.scalar(text("SELECT SUM(balance) FROM wallets")) == 49380
        assert connection.scalar(text("SELECT COUNT(*) FROM os_images")) == 7
    engine.dispose()
    command.upgrade(config, "head")


def test_parallel_verify_creates_one_wallet_and_persists_attempt_limit(tmp_path, payload, monkeypatch):
    from fastapi import HTTPException

    engine = create_engine("sqlite+pysqlite:///" + (tmp_path / "parallel.sqlite").as_posix(), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = registration.utcnow()
    with factory() as db:
        db.add(PendingRegistration(email="binh003@example.com", ho_ten=payload["ho_ten"], username="binh.003", password_hash="unused-test-hash", code_hash=registration.digest_code("binh003@example.com", "012345"), expires_at=now + timedelta(minutes=10), failed_attempts=0, last_sent_at=now, window_started_at=now, send_count=1))
        db.commit()

    def attempt(code):
        with factory() as db:
            try:
                registration.verify_registration(db, RegistrationVerify(email=payload["email"], code=code))
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=3) as pool:
        assert list(pool.map(attempt, ["111111"] * 6)) == [400] * 6
    with factory() as db:
        pending = db.get(PendingRegistration, "binh003@example.com")
        assert pending.failed_attempts == 5
        pending.failed_attempts = 0
        db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, ["012345", "012345"])) == [200, 400]
    with factory() as db:
        assert db.scalar(select(func.count(User.id))) == 1
        assert db.scalar(select(func.count(Wallet.user_id))) == 1
    engine.dispose()
