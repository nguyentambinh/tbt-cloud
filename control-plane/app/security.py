# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
import secrets
import string

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet

from app.config import get_settings

hasher = PasswordHasher()


def generate_vps_password() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(16))
        if any(c.islower() for c in password) and any(c.isupper() for c in password) and any(c.isdigit() for c in password):
            return password


LOGIN_SYMBOLS = "!@%*-_+=?"


def generate_login_password(length: int = 8) -> str:
    # Đủ 4 loại ký tự (hoa, thường, số, đặc biệt): đạt chính sách độ phức tạp của cả Linux lẫn Windows
    groups = [string.ascii_uppercase, string.ascii_lowercase, string.digits, LOGIN_SYMBOLS]
    chars = [secrets.choice(group) for group in groups] + [secrets.choice("".join(groups)) for _ in range(length - len(groups))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def create_access_token(user_id: int, token_version: int = 0) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "ver": token_version, "iat": now, "exp": now + timedelta(minutes=settings.jwt_expire_minutes), "iss": settings.jwt_issuer, "type": "access"}, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def encrypt_secret(secret: str) -> str:
    return Fernet(get_settings().fernet_key.get_secret_value().encode()).encrypt(secret.encode()).decode()


def decrypt_secret(secret: str) -> str:
    return Fernet(get_settings().fernet_key.get_secret_value().encode()).decrypt(secret.encode()).decode()
