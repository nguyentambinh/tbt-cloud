# Nguyễn Tâm Bình - 2324801030003
import argparse
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select

from app.db import get_session_factory, lock_control_plane
from app.models import AuditLog, User, Wallet
from app.schemas import RegisterInput
from app.security import hash_password


def main():
    parser = argparse.ArgumentParser(description="Tạo tài khoản quản trị cục bộ.")
    parser.add_argument("email")
    args = parser.parse_args()
    password = getpass("Mật khẩu quản trị: ")
    if password != getpass("Nhập lại mật khẩu: "):
        raise SystemExit("Mật khẩu nhập lại không khớp.")
    try:
        data = RegisterInput(email=args.email, password=password)
    except ValidationError:
        raise SystemExit("Email không hợp lệ hoặc mật khẩu chưa đủ 10 ký tự.") from None
    with get_session_factory()() as db:
        lock_control_plane(db)
        if db.scalar(select(User.id).where(User.email == str(data.email))):
            raise SystemExit("Email đã tồn tại; không tự thay đổi quyền tài khoản hiện có.")
        user = User(email=str(data.email), password_hash=hash_password(password), role="admin")
        db.add(user)
        db.flush()
        db.add(Wallet(user_id=user.id))
        db.add(AuditLog(user_id=user.id, action="admin.bootstrap", resource=f"user:{user.id}"))
        db.commit()
    print("Đã tạo tài khoản quản trị.")


if __name__ == "__main__":
    main()
