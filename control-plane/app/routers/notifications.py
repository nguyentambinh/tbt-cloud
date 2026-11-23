# Nguyễn Tâm Bình - 2324801030003
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import current_user
from app.models import AuditLog, Instance, User

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Thông báo dựng từ nhật ký kiểm toán: mỗi loại sự kiện một tiêu đề và đường dẫn tới đúng trang
CUSTOMER = {
    "instance.create": ("Đã tạo máy chủ {ten}", "Máy đã chạy, xem tài khoản và lệnh SSH ở trang chi tiết.", "/may-chu/{id}"),
    "instance.reinstall": ("Đã cài lại {ten}", "Hệ điều hành và mật khẩu mới đã sẵn sàng.", "/may-chu/{id}"),
    "instance.password": ("Đã đổi mật khẩu {ten}", "Máy khởi động lại để áp dụng mật khẩu mới.", "/may-chu/{id}"),
    "instance.delete": ("Đã hủy dịch vụ {ten}", "Máy và dữ liệu đã được xóa, cổng kết nối đã thu hồi.", "/may-chu"),
    "instance.provision_failed": ("Chưa tạo được {ten}", "Hệ thống gặp lỗi khi cấp phát. Quản trị viên đã được báo.", "/may-chu/{id}"),
    "instance.reinstall_failed": ("Cài lại {ten} chưa thành công", "Hãy thử lại hoặc liên hệ quản trị viên.", "/may-chu/{id}"),
    "instance.password_failed": ("Đổi mật khẩu {ten} chưa thành công", "Hãy thử lại sau ít phút.", "/may-chu/{id}"),
    "billing.suspend": ("{ten} tạm dừng vì hết số dư", "Nạp thêm tiền rồi bật lại máy.", "/vi"),
    "payment.paid": ("Nạp tiền thành công", "{detail}", "/vi?orderCode={code}"),
    "wallet.topup": ("Ví được cộng tiền", "{detail}", "/vi"),
}
ADMIN = {
    "auth.register": ("Tài khoản mới: {email}", "Khách hàng vừa xác nhận đăng ký.", "/quan-tri/nguoi-dung/{user_id}"),
    "payment.paid": ("{email} nạp tiền", "{detail}", "/quan-tri/nguoi-dung/{user_id}"),
    "instance.provision_failed": ("Lỗi tạo máy {ten}", "Cần kiểm tra node trước khi thu hồi tài nguyên.", "/quan-tri/ban-do"),
    "instance.reinstall_failed": ("Lỗi cài lại {ten}", "Cần kiểm tra tác vụ trên node.", "/quan-tri/ban-do"),
    "billing.suspend": ("{ten} của {email} tạm dừng", "Khách hết số dư cho giờ tiếp theo.", "/quan-tri/nguoi-dung/{user_id}"),
}


def notification_query(user):
    rules = ADMIN if user.role == "admin" else CUSTOMER
    query = select(AuditLog).where(AuditLog.action.in_(rules))
    return rules, query if user.role == "admin" else query.where(AuditLog.user_id == user.id)


@router.get("")
def notifications(limit: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(current_user)):
    rules, query = notification_query(user)
    rows = list(db.scalars(query.order_by(AuditLog.id.desc()).limit(limit)))
    ids = {int(row.resource.split(":")[1]) for row in rows if row.resource.startswith("instance:") and row.resource.split(":")[1].isdigit()}
    names = dict(db.execute(select(Instance.id, Instance.ten).where(Instance.id.in_(ids))).all()) if ids else {}
    emails = dict(db.execute(select(User.id, User.email).where(User.id.in_({row.user_id for row in rows if row.user_id}))).all()) if rows else {}
    unread = db.scalar(select(func.count()).select_from(query.where(AuditLog.id > user.thong_bao_da_doc).subquery()))
    items = []
    for row in rows:
        kind, _, key = row.resource.partition(":")
        values = {"id": key, "ten": names.get(int(key), f"máy {key}") if kind == "instance" and key.isdigit() else "", "code": key, "detail": row.detail or "", "user_id": row.user_id or "", "email": emails.get(row.user_id, "khách hàng")}
        title, body, link = rules[row.action]
        items.append({"id": row.id, "tieu_de": title.format(**values), "noi_dung": body.format(**values), "link": link.format(**values), "luc": row.created_at, "da_doc": row.id <= user.thong_bao_da_doc})
    return {"chua_doc": unread, "items": items}


@router.post("/read")
def mark_read(db: Session = Depends(get_db), user: User = Depends(current_user)):
    _, query = notification_query(user)
    latest = db.scalar(select(func.max(AuditLog.id)).where(AuditLog.id.in_(query.with_only_columns(AuditLog.id).scalar_subquery()))) or 0
    target = db.get(User, user.id)
    target.thong_bao_da_doc = max(target.thong_bao_da_doc, latest)
    db.commit()
    return {"chua_doc": 0}
