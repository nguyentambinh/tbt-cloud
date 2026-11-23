# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.models import Instance, Notification
from app.services import notify
from app.services.billing import bill_instances, get_wallet
from app.services.node_sync import sync_node
from app.services.proxmox_client import ProxmoxError


@pytest.fixture
def mailer(notify_settings, db, monkeypatch):
    factory = sessionmaker(bind=db.bind, expire_on_commit=False)
    monkeypatch.setattr(notify, "get_session_factory", lambda: factory)
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    connect = MagicMock(return_value=smtp)
    monkeypatch.setattr(notify.smtplib, "SMTP", connect)
    return connect, smtp


def test_mail_is_queued_until_commit_and_sent_with_starttls(db, mailer):
    connect, smtp = mailer
    moment = datetime(2026, 11, 22, 0, 30, tzinfo=timezone.utc)
    assert notify.enqueue(db, "test:html", "Thử thông báo", {"Khách hàng": "binh@example.com", "Chi tiết": "<script>"})
    db.get(Notification, "test:html").queued_at = moment
    smtp.send_message.assert_not_called()
    db.commit()
    smtp.send_message.assert_not_called()
    notify.send_pending()
    connect.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("sender@example.com", "fakeapppassword")
    message = smtp.send_message.call_args.args[0]
    assert message["Subject"] == "[TBT Cloud] Thử thông báo"
    assert str(message["To"]) == "admin@example.com, second@example.com"
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "22/11/2026 07:30:00" in html and "giờ Việt Nam" in html and "&lt;script&gt;" in html
    assert "fakeapppassword" not in message.as_string()
    db.expire_all()
    record = db.get(Notification, "test:html")
    assert record.count == 1 and record.last_sent_at is not None and not record.pending


def test_dedup_pending_and_sent_survives_new_session(db, mailer):
    assert notify.enqueue(db, "same:event", "Sự kiện", {"Mã": 1})
    db.commit()
    with sessionmaker(bind=db.bind)() as second:
        assert not notify.enqueue(second, "same:event", "Sự kiện", {"Mã": 1})
        second.commit()
    notify.send_pending()
    db.expire_all()
    assert not notify.enqueue(db, "same:event", "Sự kiện", {"Mã": 1})
    db.commit()
    notify.send_pending()
    assert mailer[1].send_message.call_count == 1
    db.get(Notification, "same:event").last_sent_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    db.commit()
    assert notify.enqueue(db, "same:event", "Sự kiện lần sau", {"Mã": 2})
    db.commit()
    notify.send_pending()
    db.expire_all()
    assert mailer[1].send_message.call_count == 2 and db.get(Notification, "same:event").count == 2


def test_rollback_does_not_send(db, mailer):
    notify.enqueue(db, "rolled:back", "Không gửi", {})
    db.rollback()
    notify.send_pending()
    mailer[1].send_message.assert_not_called()
    assert db.get(Notification, "rolled:back") is None


def test_smtp_failure_is_one_safe_log_line(db, mailer, caplog):
    mailer[1].login.side_effect = notify.smtplib.SMTPAuthenticationError(535, b"fakeapppassword secret-error")
    notify.enqueue(db, "smtp:failed", "Lỗi thử", {})
    db.commit()
    notify.send_pending()
    assert len(caplog.records) == 1 and "Không gửi được email" in caplog.text
    assert "fakeapppassword" not in caplog.text and "secret-error" not in caplog.text
    db.expire_all()
    assert db.get(Notification, "smtp:failed").count == 0


def test_password_is_read_at_send_time(db, mailer, notify_settings, monkeypatch, tmp_path):
    notify.enqueue(db, "password:rotate", "Thử mật khẩu", {})
    db.commit()
    replacement = tmp_path / "rotated-test.txt"
    replacement.write_text(" new \r\n app password ", encoding="utf-8")
    monkeypatch.setattr(notify_settings, "smtp_password_file", str(replacement))
    notify.send_pending()
    mailer[1].login.assert_called_once_with("sender@example.com", "newapppassword")


def test_disabled_notifications_do_not_create_rows(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "notify_enabled", False)
    assert not notify.enqueue(db, "disabled", "Tắt", {})
    db.commit()
    assert db.scalar(select(func.count(Notification.key))) == 0


def test_admin_test_endpoint_and_dedup(mailer, client, db, headers):
    assert client.post("/api/v1/admin/notify/test", headers=headers["user"]).status_code == 403
    assert client.post("/api/v1/admin/notify/test").status_code == 401
    for _ in range(2):
        result = client.post("/api/v1/admin/notify/test", headers=headers["admin"])
        assert result.status_code == 202
    mailer[1].send_message.assert_not_called()
    assert db.scalar(select(func.count(Notification.key))) == 1
    notify.send_pending()
    mailer[1].send_message.assert_called_once()


def test_admin_test_disabled_returns_503(client, headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "notify_enabled", False)
    assert client.post("/api/v1/admin/notify/test", headers=headers["admin"]).status_code == 503


def test_blocked_sender_does_not_block_requests(mailer, client, db, headers, monkeypatch):
    entered, release = Event(), Event()

    def blocked_send():
        entered.set()
        assert release.wait(timeout=5)

    monkeypatch.setattr(notify, "send_pending", blocked_send)
    notify.stopping.clear()
    thread = Thread(target=notify.sender_loop, daemon=True)
    thread.start()
    try:
        assert entered.wait(timeout=2)
        assert client.post("/api/v1/admin/notify/test", headers=headers["admin"]).status_code == 202
        assert db.get(Notification, "admin:notify:test").pending
    finally:
        notify.stopping.set()
        release.set()
        notify.wakeup.set()
        thread.join(timeout=3)
    assert not thread.is_alive()


def test_node_disconnect_and_reconnect_only_on_transitions(mailer, db, seed):
    node = seed["node"]
    proxmox = MagicMock()
    proxmox.get_node_resources.side_effect = ProxmoxError()
    node.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=119)
    db.commit()
    assert not sync_node(db, node, lambda _: proxmox)
    db.commit()
    assert db.scalar(select(func.count(Notification.key))) == 0
    node.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=121)
    db.commit()
    for _ in range(3):
        assert not sync_node(db, node, lambda _: proxmox)
        db.commit()
    assert node.notify_offline and db.scalar(select(func.count(Notification.key))) == 1
    notify.send_pending()
    db.expire_all()
    db.get(Notification, f"node:{node.id}:offline").last_sent_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    assert not sync_node(db, node, lambda _: proxmox)
    db.commit()
    notify.send_pending()
    assert mailer[1].send_message.call_count == 1
    proxmox.get_node_resources.side_effect = None
    proxmox.get_node_resources.return_value = {"total_vcpu": 8, "total_ram_mb": 16384, "total_disk_gb": 200, "used_vcpu": 0, "used_ram_mb": 0, "used_disk_gb": 0}
    for _ in range(3):
        assert sync_node(db, node, lambda _: proxmox)
        db.commit()
    assert not node.notify_offline and db.scalar(select(func.count(Notification.key))) == 2
    notify.send_pending()
    assert mailer[1].send_message.call_count == 2


@pytest.mark.parametrize("failure", [False, True])
def test_create_vps_success_or_failure_notification(mailer, client, db, headers, instance_payload, mock_proxmox, failure):
    if failure:
        mock_proxmox[1].clone_template.side_effect = ProxmoxError()
    result = client.post("/api/v1/instances", json=instance_payload, headers=headers["user"])
    assert result.status_code == (502 if failure else 201)
    value = db.scalar(select(Instance))
    record = db.get(Notification, f"instance:{value.id}:" + ("provision_failed" if failure else "create"))
    assert record is not None and "owner@example.com" in record.details
    mailer[1].send_message.assert_not_called()


@pytest.mark.parametrize("failure", [False, True])
def test_reinstall_success_or_failure_notification(mailer, client, db, headers, instance, instance_payload, mock_proxmox, failure):
    instance.cloud_user = "ubuntu"
    instance.ssh_public_key = instance_payload["ssh_public_key"]
    instance.template_id = 9000
    instance.paid_until = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()
    if failure:
        mock_proxmox[1].clone_template.side_effect = ProxmoxError()
    result = client.post(f"/api/v1/instances/{instance.id}/reinstall", headers=headers["user"])
    assert result.status_code == (502 if failure else 200)
    record = db.get(Notification, f"instance:{instance.id}:" + ("reinstall_failed" if failure else "reinstall"))
    assert record is not None and "password" not in record.details


def test_delete_vps_notification(mailer, client, db, headers, instance, mock_proxmox):
    assert client.delete(f"/api/v1/instances/{instance.id}", headers=headers["user"]).status_code == 200
    assert db.get(Notification, f"instance:{instance.id}:delete") is not None


def test_billing_suspension_notifies_once(mailer, db, instance):
    get_wallet(db, instance.user_id).balance = 0
    db.commit()
    proxmox = MagicMock()
    for _ in range(3):
        bill_instances(db, client_factory=lambda _: proxmox)
    assert instance.trang_thai == "suspended"
    record = db.get(Notification, f"instance:{instance.id}:suspended")
    assert record is not None
    notify.send_pending()
    bill_instances(db, client_factory=lambda _: proxmox)
    notify.send_pending()
    assert mailer[1].send_message.call_count == 1


def test_new_settings_defaults_blank_values_and_no_direct_smtp_password(monkeypatch):
    for key in ("PAYOS_MIN_AMOUNT", "PAYOS_MAX_AMOUNT", "SMTP_HOST", "SMTP_PORT", "NOTIFY_ENABLED", "NOTIFY_DEDUP_MINUTES"):
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("SMTP_PASSWORD", "unused-direct-password")
    settings = Settings(_env_file=None)
    assert settings.payos_min_amount == 10000 and settings.payos_max_amount == 5000000
    assert settings.smtp_host == "smtp.gmail.com" and settings.smtp_port == 587
    assert not settings.notify_enabled and settings.notify_dedup_minutes == 30
    assert "unused-direct-password" not in repr(settings) and not hasattr(settings, "smtp_password")
