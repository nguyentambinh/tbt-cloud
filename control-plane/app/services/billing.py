# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from app.db import lock_control_plane
from app.models import AuditLog, Instance, Transaction, Wallet
from app.services.proxmox_client import ProxmoxClient, ProxmoxError
from app.services import notify


def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def get_wallet(db, user_id):
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id).execution_options(populate_existing=True))
    if wallet is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ví của tài khoản.")
    return wallet


def topup(db, user_id, amount, request_id, description=None, max_amount=Decimal("10000000")):
    lock_control_plane(db)
    wallet = get_wallet(db, user_id)
    key = f"topup:{wallet.id}:{request_id}"
    previous = db.scalar(select(Transaction).where(Transaction.idempotency_key == key))
    if previous:
        if previous.amount != amount:
            raise HTTPException(status_code=409, detail="Mã yêu cầu đã được dùng với số tiền khác.")
        return wallet
    if amount <= 0 or amount > max_amount or amount != amount.quantize(Decimal("0.01")):
        raise HTTPException(status_code=422, detail="Số tiền nạp không hợp lệ.")
    wallet.balance += amount
    db.add(Transaction(wallet_id=wallet.id, amount=amount, kind="topup", idempotency_key=key, description=description or "Nạp ví ảo"))
    db.add(AuditLog(user_id=user_id, action="wallet.topup", resource=f"wallet:{wallet.id}", detail=description or "Nạp tiền ảo"))
    db.flush()
    return wallet


def charge_hour(db, instance, now=None, reset_period=False):
    lock_control_plane(db)
    now = as_utc(now or datetime.now(timezone.utc))
    if instance.paid_until and as_utc(instance.paid_until) > now:
        return True
    wallet = get_wallet(db, instance.user_id)
    if wallet.balance < instance.gia_theo_gio:
        return False
    start = now if reset_period or instance.paid_until is None else as_utc(instance.paid_until)
    key = f"usage:{instance.id}:{start.isoformat()}"
    if db.scalar(select(Transaction.id).where(Transaction.idempotency_key == key)) is None:
        wallet.balance -= instance.gia_theo_gio
        db.add(Transaction(wallet_id=wallet.id, instance_id=instance.id, amount=-instance.gia_theo_gio, kind="usage", idempotency_key=key, description="Thanh toán một giờ sử dụng"))
    instance.paid_until = start + timedelta(hours=1)
    db.flush()
    return True


def charge_due_hours(db, instance, now=None):
    now = as_utc(now or datetime.now(timezone.utc))
    while instance.paid_until is None or as_utc(instance.paid_until) <= now:
        if not charge_hour(db, instance, now):
            return False
    return True


def bill_instances(db, now=None, client_factory=ProxmoxClient):
    now = as_utc(now or datetime.now(timezone.utc))
    lock_control_plane(db)
    instances = list(db.scalars(select(Instance).where(Instance.trang_thai.in_(["running", "suspended"])).order_by(Instance.id).execution_options(populate_existing=True)))
    for instance in instances:
        if instance.trang_thai == "running":
            if not charge_due_hours(db, instance, now):
                instance.trang_thai = "suspended"
                db.add(AuditLog(user_id=instance.user_id, action="billing.suspend", resource=f"instance:{instance.id}", detail="Số dư không đủ cho giờ tiếp theo"))
                notify.instance_event(db, instance, "suspended", "VPS bị dừng do hết tiền")
        if instance.trang_thai == "suspended":
            try:
                client = client_factory(instance.node)
                client.stop(instance.vmid, instance.loai)
            except ProxmoxError:
                db.add(AuditLog(user_id=instance.user_id, action="billing.stop_pending", resource=f"instance:{instance.id}", detail="Chờ node kết nối để dừng instance"))
    db.commit()
