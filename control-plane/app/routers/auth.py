# Nguyễn Tâm Bình - 2324801030003
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import current_user
from app.models import AuditLog, User
from app.schemas import LoginInput, RegisterInput, RegistrationEmail, RegistrationOutput, RegistrationVerify, TokenOutput, UserOutput
from app.security import create_access_token, hash_password, verify_password
from app.services import registration

router = APIRouter(prefix="/auth", tags=["auth"])
dummy_hash = hash_password("dummy-password-for-timing-only")


@router.post("/register", response_model=RegistrationOutput, status_code=202)
def register(data: RegisterInput, db: Session = Depends(get_db)):
    return registration.start_registration(db, data)


@router.post("/register/verify", response_model=TokenOutput)
def verify_registration(data: RegistrationVerify, db: Session = Depends(get_db)):
    return registration.verify_registration(db, data)


@router.post("/register/resend", response_model=RegistrationOutput, status_code=202)
def resend_registration(data: RegistrationEmail, db: Session = Depends(get_db)):
    return registration.resend_code(db, data.email)


@router.post("/login", response_model=TokenOutput)
def login(data: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(or_(func.lower(User.email) == data.email, func.lower(User.username) == data.email)))
    valid = verify_password(data.password.get_secret_value(), user.password_hash if user else dummy_hash)
    if user is None or not valid:
        raise HTTPException(status_code=401, detail="Tên tài khoản, email hoặc mật khẩu không đúng.", headers={"WWW-Authenticate": "Bearer"})
    if user.is_blocked or user.deleted_at is not None:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa. Hãy liên hệ quản trị viên để được hỗ trợ.")
    db.add(AuditLog(user_id=user.id, action="auth.login", resource=f"user:{user.id}"))
    db.commit()
    return TokenOutput(access_token=create_access_token(user.id, user.token_version))


@router.get("/me", response_model=UserOutput)
def me(user: User = Depends(current_user)):
    return user
