# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import User, Wallet
from app.security import verify_password


def test_registration_hash_and_login(client, db, monkeypatch):
    from app.models import PendingRegistration
    from app.services import notify
    sent = []
    monkeypatch.setattr(notify, "send_registration_code", lambda *args: sent.append(args))
    data = {"ho_ten": "Nguyễn Tâm Bình", "username": "New.User", "email": "NewUser@example.com", "password": "Secure-password-123", "password_confirm": "Secure-password-123"}
    response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 202, response.text
    assert "password" not in response.text
    assert db.scalar(select(User)) is None
    pending = db.get(PendingRegistration, "newuser@example.com")
    assert verify_password(data["password"], pending.password_hash)
    response = client.post("/api/v1/auth/register/verify", json={"email": data["email"], "code": sent[0][2]})
    assert response.status_code == 200, response.text
    user = db.scalar(select(User).where(User.email == "newuser@example.com"))
    assert user.role == "user"
    assert user.password_hash != data["password"]
    assert verify_password(data["password"], user.password_hash)
    assert db.scalar(select(Wallet).where(Wallet.user_id == user.id)).balance == 0
    login = client.post("/api/v1/auth/login", json={"email": data["email"], "password": data["password"]})
    assert login.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == user.id


def test_duplicate_email_and_no_admin_self_registration(client, seed):
    data = {"ho_ten": "Nguyễn Tâm Bình", "username": "new.user", "email": "OWNER@example.com", "password": "Owner-password-123", "password_confirm": "Owner-password-123"}
    assert client.post("/api/v1/auth/register", json=data).status_code == 409
    data.update(email="attacker@example.com", role="admin")
    assert client.post("/api/v1/auth/register", json=data).status_code == 422


@pytest.mark.parametrize("email", ["owner@example.com", "unknown@example.com"])
def test_wrong_credentials_are_indistinguishable(client, seed, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password-123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Tên tài khoản, email hoặc mật khẩu không đúng."


def test_missing_invalid_and_expired_token(client, seed):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    settings = get_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": str(seed["user"].id), "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1), "iss": settings.jwt_issuer, "type": "access"}, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_admin_boundaries(client, headers):
    assert client.get("/api/v1/nodes", headers=headers["user"]).status_code == 403
    assert client.get("/api/v1/admin/users", headers=headers["user"]).status_code == 403
    assert client.get("/api/v1/admin/users", headers=headers["admin"]).status_code == 200
    assert client.get("/api/v1/nodes", headers=headers["admin"]).status_code == 200


def test_validation_does_not_echo_secrets(client):
    response = client.post("/api/v1/auth/register", json={"email": "invalid", "password": "a-sensitive-invalid-password"})
    assert response.status_code == 422
    assert "a-sensitive-invalid-password" not in response.text
