# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import math
import secrets

from fastapi import HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.models import AuditLog, PendingRegistration, User, Wallet
from app.security import create_access_token, hash_password
from app.services import notify


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def lock_registration(db):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(1413633106)"))
    elif db.bind.dialect.name == "sqlite" and not db.connection().connection.driver_connection.in_transaction:
        db.execute(text("BEGIN IMMEDIATE"))


def check_conflicts(db, email, username):
    if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
        raise HTTPException(status_code=409, detail="Email đã được đăng ký. Hãy đăng nhập hoặc dùng email khác.")
    if db.scalar(select(User.id).where(or_(func.lower(User.username) == username, func.lower(User.email) == username))) is not None:
        raise HTTPException(status_code=409, detail="Tên tài khoản đã được sử dụng. Hãy chọn tên khác.")


def digest_code(email, code):
    key = get_settings().jwt_secret.get_secret_value().encode()
    return hmac.new(key, f"register:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def check_send_limit(pending, now):
    if pending is None:
        return
    remaining = math.ceil(60 - (now - as_utc(pending.last_sent_at)).total_seconds())
    if remaining > 0:
        raise HTTPException(status_code=429, detail=f"Vui lòng chờ {remaining} giây trước khi gửi lại mã.", headers={"Retry-After": str(remaining)})
    if now < as_utc(pending.window_started_at) + timedelta(hours=1) and pending.send_count >= 5:
        remaining = math.ceil((as_utc(pending.window_started_at) + timedelta(hours=1) - now).total_seconds())
        raise HTTPException(status_code=429, detail="Email này đã nhận đủ 5 mã trong một giờ. Vui lòng thử lại sau.", headers={"Retry-After": str(remaining)})


def send_code(db, pending, now):
    if pending.window_started_at is None or now >= as_utc(pending.window_started_at) + timedelta(hours=1):
        pending.window_started_at, pending.send_count = now, 0
    code = f"{secrets.randbelow(1000000):06d}"
    pending.code_hash = digest_code(pending.email, code)
    pending.expires_at = now + timedelta(minutes=10)
    pending.failed_attempts = 0
    pending.last_sent_at = now
    pending.send_count += 1
    try:
        db.flush()
        notify.send_registration_code(pending.email, pending.ho_ten, code)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Thông tin đăng ký đang được cập nhật. Vui lòng thử lại.") from None
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="Chưa gửi được mã xác nhận. Vui lòng thử lại sau ít phút.") from None
    local, domain = pending.email.rsplit("@", 1)
    return {"email_masked": f"{local[0]}***@{domain}"}


def start_registration(db, data):
    lock_registration(db)
    check_conflicts(db, data.email, data.username)
    now = utcnow()
    pending = db.get(PendingRegistration, data.email, populate_existing=True)
    check_send_limit(pending, now)
    if pending is None:
        pending = PendingRegistration(email=data.email, window_started_at=now, send_count=0)
        db.add(pending)
    pending.ho_ten, pending.username = data.ho_ten, data.username
    pending.password_hash = hash_password(data.password.get_secret_value())
    return send_code(db, pending, now)


def resend_code(db, email):
    lock_registration(db)
    pending = db.get(PendingRegistration, email, populate_existing=True)
    if pending is None:
        raise HTTPException(status_code=400, detail="Chưa có yêu cầu đăng ký. Vui lòng điền lại thông tin đăng ký.")
    check_conflicts(db, email, pending.username)
    now = utcnow()
    check_send_limit(pending, now)
    return send_code(db, pending, now)


def verify_registration(db, data):
    lock_registration(db)
    pending = db.get(PendingRegistration, data.email, populate_existing=True)
    if pending is None:
        raise HTTPException(status_code=400, detail="Không tìm thấy đăng ký chờ xác nhận. Vui lòng đăng ký lại.")
    if pending.failed_attempts >= 5:
        raise HTTPException(status_code=400, detail="Mã đã bị khóa sau 5 lần nhập sai. Hãy gửi lại mã.")
    if utcnow() >= as_utc(pending.expires_at):
        raise HTTPException(status_code=400, detail="Mã xác nhận đã hết hạn. Hãy gửi lại mã.")
    if not hmac.compare_digest(pending.code_hash, digest_code(data.email, data.code.get_secret_value())):
        pending.failed_attempts += 1
        remaining = 5 - pending.failed_attempts
        db.commit()
        raise HTTPException(status_code=400, detail=f"Mã xác nhận chưa đúng. Còn {remaining} lần thử." if remaining else "Mã xác nhận chưa đúng. Còn 0 lần thử; mã đã bị khóa. Hãy gửi lại mã.")
    check_conflicts(db, pending.email, pending.username)
    user = User(email=pending.email, ho_ten=pending.ho_ten, username=pending.username, password_hash=pending.password_hash, role="user")
    try:
        db.add(user)
        db.flush()
        db.add(Wallet(user_id=user.id))
        db.add(AuditLog(user_id=user.id, action="auth.register", resource=f"user:{user.id}"))
        db.delete(pending)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email hoặc tên tài khoản đã được đăng ký. Hãy dùng thông tin khác.") from None
    return {"access_token": create_access_token(user.id)}
