# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from urllib.parse import urlsplit

from fastapi import HTTPException
import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import lock_control_plane
from app.models import AuditLog, Payment, Transaction, User
from app.services.billing import as_utc, topup
from app.services import notify

logger = logging.getLogger(__name__)
BASE_URL = "https://api-merchant.payos.vn"


class PayosError(HTTPException):
    def __init__(self, detail="Cổng thanh toán chưa thể xử lý yêu cầu. Vui lòng thử lại.", status_code=502):
        super().__init__(status_code=status_code, detail=detail)


def require_configured():
    settings = get_settings()
    if not all(key and key.get_secret_value().strip() for key in (settings.payos_client_id, settings.payos_api_key, settings.payos_checksum_key)) or not settings.payos_return_url or not settings.payos_cancel_url:
        raise PayosError("Cổng thanh toán chưa được cấu hình.", 503)
    return settings


def signature(data):
    def value(item):
        if item is None:
            return ""
        if isinstance(item, (list, dict)):
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        return str(item)
    content = "&".join(f"{key}={value(data[key])}" for key in sorted(data))
    return hmac.new(get_settings().payos_checksum_key.get_secret_value().encode(), content.encode(), hashlib.sha256).hexdigest()


def request(method, path, body=None):
    settings = require_configured()
    try:
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
            response = client.request(method, BASE_URL + path, headers={"x-client-id": settings.payos_client_id.get_secret_value(), "x-api-key": settings.payos_api_key.get_secret_value()}, json=body)
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict) or result.get("code") != "00" or not isinstance(result.get("data"), dict):
            raise PayosError()
        data = result["data"]
        if "signature" in result and (not isinstance(result["signature"], str) or not hmac.compare_digest(signature(data), result["signature"])):
            raise PayosError("Không xác minh được phản hồi thanh toán. Vui lòng thử lại.")
        return data
    except (httpx.TimeoutException, httpx.NetworkError):
        raise PayosError("Không kết nối được cổng thanh toán. Vui lòng thử lại sau.", 503) from None
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise PayosError() from None


def owned_payment(db, order_code, user, owner_only=False):
    payment = db.scalar(select(Payment).where(Payment.order_code == order_code).execution_options(populate_existing=True))
    if payment is None or (payment.user_id != user.id and (owner_only or user.role != "admin")):
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn nạp tiền.")
    return payment


def validate_order(data, payment):
    if type(data.get("orderCode")) is not int or data["orderCode"] != payment.order_code or type(data.get("amount")) is not int or data["amount"] != payment.amount:
        raise PayosError("Thông tin đơn thanh toán chưa khớp. Vui lòng thử lại.")
    if data.get("id") is not None and data["id"] != payment.payment_link_id:
        raise PayosError("Thông tin đơn thanh toán chưa khớp. Vui lòng thử lại.")


def create_payment(db, user, amount, origin=None):
    settings = require_configured()
    if not settings.payos_min_amount <= amount <= settings.payos_max_amount:
        raise HTTPException(status_code=422, detail=f"Số tiền nạp phải từ {settings.payos_min_amount:,} đến {settings.payos_max_amount:,} đồng.")
    lock_control_plane(db)
    for _ in range(20):
        order_code = time.time_ns() // 1000000 * 1000 + secrets.randbelow(1000)
        if db.scalar(select(Payment.id).where(Payment.order_code == order_code)) is None:
            break
    else:
        raise PayosError("Chưa tạo được mã đơn nạp tiền. Vui lòng thử lại.", 503)
    return_url, cancel_url = settings.payos_return_url, settings.payos_cancel_url
    # Quay về đúng địa chỉ khách đang mở (LAN hay đường hầm công khai)
    if origin and re.fullmatch(r"https?://[A-Za-z0-9.-]+(:\d{1,5})?/", origin):
        return_url, cancel_url = f"{origin}thanh-toan/ket-qua", f"{origin}thanh-toan/huy"
    body = {"orderCode": order_code, "amount": amount, "description": f"TBT NAP {str(order_code)[-16:]}", "returnUrl": return_url, "cancelUrl": cancel_url}
    body["signature"] = signature(body)
    data = request("POST", "/v2/payment-requests", body)
    checkout_url, qr_code, link_id = data.get("checkoutUrl"), data.get("qrCode"), data.get("paymentLinkId")
    if type(data.get("orderCode")) is not int or data["orderCode"] != order_code or type(data.get("amount")) is not int or data["amount"] != amount or not all(isinstance(value, str) and value for value in (checkout_url, qr_code, link_id)) or len(link_id) > 100:
        raise PayosError()
    try:
        parsed = urlsplit(checkout_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError()
    except ValueError:
        raise PayosError() from None
    payment = Payment(user_id=user.id, order_code=order_code, amount=amount, status="pending", checkout_url=checkout_url, qr_code=qr_code, payment_link_id=link_id)
    db.add(payment)
    db.add(AuditLog(user_id=user.id, action="payment.create", resource=f"payment:{order_code}"))
    db.commit()
    return payment


def apply_status(db, payment, data):
    lock_control_plane(db)
    payment = db.get(Payment, payment.id, populate_existing=True, with_for_update=True)
    validate_order(data, payment)
    if payment.status != "pending":
        return payment
    status = data.get("status")
    if status == "PAID":
        if type(data.get("amountPaid")) is not int or data["amountPaid"] < payment.amount:
            raise PayosError("Đơn nạp tiền chưa được thanh toán đủ. Vui lòng kiểm tra lại sau.")
        request_id = f"payos-{payment.order_code}"
        wallet = topup(db, payment.user_id, Decimal(payment.amount), request_id, description=f"Nạp ví qua payOS, đơn {payment.order_code}", max_amount=Decimal(payment.amount))
        payment.transaction_id = db.scalar(select(Transaction.id).where(Transaction.idempotency_key == f"topup:{wallet.id}:{request_id}"))
        payment.status = "paid"
        payment.paid_at = datetime.now(timezone.utc)
        db.add(AuditLog(user_id=payment.user_id, action="payment.paid", resource=f"payment:{payment.order_code}", detail=f"Nạp {payment.amount} VND qua payOS"))
        notify.enqueue(db, f"payment:{payment.order_code}:paid", "Khách hàng nạp tiền thành công", {"Khách hàng": db.get(User, payment.user_id).email, "Số tiền (VND)": payment.amount, "Mã đơn": payment.order_code, "Số dư mới (VND)": str(wallet.balance)})
    elif status in {"CANCELLED", "EXPIRED", "FAILED"}:
        payment.status = status.lower()
    elif status not in {"PENDING", "PROCESSING"}:
        raise PayosError()
    db.flush()
    return payment


def refresh_payment(db, payment):
    require_configured()
    if payment.status == "pending":
        data = request("GET", f"/v2/payment-requests/{payment.order_code}")
        payment = apply_status(db, payment, data)
    db.commit()
    return payment


def cancel_payment(db, payment, reason):
    require_configured()
    lock_control_plane(db)
    payment = db.get(Payment, payment.id, populate_existing=True, with_for_update=True)
    if payment.status == "pending":
        data = request("POST", f"/v2/payment-requests/{payment.order_code}/cancel", {"cancellationReason": reason})
        if data.get("status") not in {"CANCELLED", "PAID", "EXPIRED"}:
            raise PayosError()
        payment = apply_status(db, payment, data)
        db.add(AuditLog(user_id=payment.user_id, action="payment.cancel", resource=f"payment:{payment.order_code}"))
    db.commit()
    return payment


def poll_payments(db, now=None):
    now = as_utc(now or datetime.now(timezone.utc))
    orders = list(db.scalars(select(Payment.order_code).where(Payment.status == "pending").order_by(Payment.id)))
    db.rollback()
    for order_code in orders:
        try:
            lock_control_plane(db)
            payment = db.scalar(select(Payment).where(Payment.order_code == order_code).execution_options(populate_existing=True))
            if payment.status != "pending":
                db.rollback()
                continue
            if as_utc(payment.created_at) < now - timedelta(hours=24):
                payment.status = "expired"
                db.commit()
                continue
            db.commit()
            refresh_payment(db, payment)
        except PayosError:
            db.rollback()
            logger.error("Chưa cập nhật được trạng thái đơn nạp tiền payOS.")
