# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
import json
import logging
from pathlib import Path
import smtplib
import ssl
from threading import Event, Lock, Thread

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session_factory, lock_control_plane
from app.models import Notification, User

logger = logging.getLogger(__name__)
wakeup = Event()
sender_lock = Lock()
sender = None
stopping = Event()
VIETNAM = timezone(timedelta(hours=7))


def configured():
    settings = get_settings()
    return settings.notify_enabled and bool(settings.smtp_host and settings.smtp_user and settings.smtp_password_file and recipients())


def recipients():
    return [address.strip() for address in get_settings().notify_to.split(",") if address.strip()]


def enqueue(db, key, subject, details):
    if not configured():
        return False
    lock_control_plane(db)
    now = datetime.now(timezone.utc)
    notification = db.get(Notification, key, populate_existing=True)
    if notification is not None:
        last_sent = notification.last_sent_at
        if notification.pending or (last_sent and last_sent.replace(tzinfo=timezone.utc) > now - timedelta(minutes=get_settings().notify_dedup_minutes)):
            return False
    else:
        notification = Notification(key=key, count=0)
        db.add(notification)
    notification.subject = subject
    notification.details = json.dumps(details, ensure_ascii=False)
    notification.queued_at = now
    notification.pending = True
    db.info["notify_queued"] = True
    return True


def instance_event(db, instance, action, subject):
    owner = db.get(User, instance.user_id)
    return enqueue(db, f"instance:{instance.id}:{action}", subject, {"Khách hàng": owner.email, "VPS": instance.ten, "Mã VPS": instance.id, "Node": instance.node.ten})


@event.listens_for(Session, "after_commit")
def notify_after_commit(db):
    if db.info.pop("notify_queued", False):
        wakeup.set()


@event.listens_for(Session, "after_rollback")
def notify_after_rollback(db):
    db.info.pop("notify_queued", None)


def send_mail(notification):
    settings = get_settings()
    details = json.loads(notification.details)
    happened_at = notification.queued_at.astimezone(VIETNAM) if notification.queued_at.tzinfo else notification.queued_at.replace(tzinfo=timezone.utc).astimezone(VIETNAM)
    message = EmailMessage()
    message["Subject"] = f"[TBT Cloud] {notification.subject}"
    message["From"] = settings.smtp_user
    message["To"] = ", ".join(recipients())
    message.set_content(f"Thời gian: {happened_at:%d/%m/%Y %H:%M:%S} (giờ Việt Nam)\nSự kiện: {notification.subject}\n" + "\n".join(f"{key}: {value}" for key, value in details.items()))
    rows = "".join(f"<tr><th style='text-align:left;padding:8px'>{escape(str(key))}</th><td style='padding:8px'>{escape(str(value))}</td></tr>" for key, value in details.items())
    message.add_alternative(f"<html lang='vi'><body><h2>{escape(notification.subject)}</h2><p>Thời gian: {happened_at:%d/%m/%Y %H:%M:%S} (giờ Việt Nam)</p><p>Sự kiện: {escape(notification.subject)}</p><table>{rows}</table></body></html>", subtype="html")
    send_message(message)


def send_message(message):
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password_file:
        raise ValueError("SMTP chưa được cấu hình.")
    password = "".join(Path(settings.smtp_password_file).read_text(encoding="utf-8").split())
    if not password:
        raise ValueError("Mật khẩu SMTP chưa được cấu hình.")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(settings.smtp_user, password)
        smtp.send_message(message)


def send_registration_code(email, ho_ten, code):
    message = EmailMessage()
    message["Subject"] = "[TBT Cloud] Mã xác nhận đăng ký"
    message["From"] = get_settings().smtp_user
    message["To"] = email
    message.set_content(f"Xin chào {ho_ten},\nMã xác nhận đăng ký TBT Cloud của bạn: {code}\nMã có hiệu lực trong 10 phút. Không chia sẻ mã này với người khác.\nNếu bạn không đăng ký, hãy bỏ qua thư này.")
    message.add_alternative(f"<html lang='vi'><body><h2>Xác nhận đăng ký TBT Cloud</h2><p>Xin chào {escape(ho_ten)},</p><p>Mã xác nhận đăng ký của bạn là:</p><p style='font-size:32px;font-weight:bold;letter-spacing:6px'>{escape(code)}</p><p>Mã có hiệu lực trong <strong>10 phút</strong>. Không chia sẻ mã này với người khác.</p><p>Nếu bạn không đăng ký, hãy bỏ qua thư này.</p></body></html>", subtype="html")
    send_message(message)


def send_pending():
    if not configured():
        return
    for _ in range(100):
        with get_session_factory()() as db:
            if db.bind.dialect.name == "sqlite":
                lock_control_plane(db)
            notification = db.scalar(select(Notification).where(Notification.pending.is_(True)).order_by(Notification.queued_at, Notification.key).with_for_update(skip_locked=True))
            if notification is None:
                return
            try:
                send_mail(notification)
                notification.last_sent_at = datetime.now(timezone.utc)
                notification.count += 1
            except Exception:
                logger.error("Không gửi được email thông báo. Vui lòng kiểm tra cấu hình SMTP.")
            notification.pending = False
            db.commit()


def sender_loop():
    while not stopping.is_set():
        wakeup.clear()
        try:
            send_pending()
        except Exception:
            logger.error("Hàng đợi thông báo tạm thời chưa sẵn sàng.")
        wakeup.wait(60)


def start_sender():
    global sender
    if not configured():
        return
    with sender_lock:
        if sender is None or not sender.is_alive():
            stopping.clear()
            sender = Thread(target=sender_loop, name="tbt-notify", daemon=True)
            sender.start()


def stop_sender():
    stopping.set()
    wakeup.set()
    if sender is not None:
        sender.join(timeout=12)
