# Nguyễn Tâm Bình - 2324801030003
import jwt
from pathlib import Path
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    error = HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise error
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret.get_secret_value(), algorithms=["HS256"], issuer=settings.jwt_issuer, options={"require": ["sub", "exp", "iat", "iss", "type"]})
        if payload["type"] != "access":
            raise error
        epoch = Path(settings.backup_dir) / ".auth-epoch"
        if epoch.exists() and int(payload["iat"]) <= int(epoch.read_text(encoding="ascii")):
            raise error
        user = db.get(User, int(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError, TypeError, OSError):
        raise error from None
    if user is None or user.is_blocked or user.deleted_at is not None or payload.get("ver", 0) != user.token_version:
        raise error
    return user


def tenant_user(user: User = Depends(current_user)) -> User:
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Quản trị viên không thể thuê dịch vụ hoặc nạp tiền. Hãy dùng tài khoản khách hàng.")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Chức năng này chỉ dành cho quản trị viên.")
    return user
