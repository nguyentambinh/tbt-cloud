# Nguyễn Tâm Bình - 2324801030003
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import json
from threading import Barrier

import httpx
from pydantic import SecretStr
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base
from app.models import AllocationLock, AuditLog, Notification, Payment, Transaction, User, Wallet
from app.services import payos
from app.services.billing import get_wallet
from app.workers.scheduler import create_scheduler


@pytest.fixture
def gateway(monkeypatch):
    settings = get_settings()
    for key in ("payos_client_id", "payos_api_key", "payos_checksum_key"):
        monkeypatch.setattr(settings, key, SecretStr("fake-" + key))
    monkeypatch.setattr(settings, "payos_return_url", "https://cloud.example/return")
    monkeypatch.setattr(settings, "payos_cancel_url", "https://cloud.example/cancel")
    state = {"status": "PENDING", "amountPaid": 0, "calls": [], "signed": True}
    real_client = httpx.Client

    def respond(request):
        state["calls"].append(request)
        if state.get("error"):
            raise state["error"]
        if state.get("http_status"):
            return httpx.Response(state["http_status"], json={"secret": "RAW-UPSTREAM-SECRET"})
        if request.method == "POST" and request.url.path == "/v2/payment-requests":
            body = json.loads(request.content)
            state.update(orderCode=body["orderCode"], amount=body["amount"])
            data = {"orderCode": state["orderCode"], "amount": state["amount"], "paymentLinkId": "link-test", "checkoutUrl": "https://pay.payos.vn/test", "qrCode": "TEST-QR", "status": "PENDING"}
        else:
            status = state.get("cancel_status", "CANCELLED") if request.url.path.endswith("/cancel") else state["status"]
            data = {"id": "link-test", "orderCode": state["orderCode"], "amount": state["amount"], "status": status, "amountPaid": state["amountPaid"]}
        data.update(state.get("override", {}))
        result = {"code": state.get("code", "00"), "data": data}
        if state["signed"]:
            result["signature"] = payos.signature(data) if state["signed"] is True else "invalid-signature"
        return httpx.Response(200, json=result)

    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(payos.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs))
    return state


def create(client, headers, amount=10000):
    result = client.post("/api/v1/billing/payos", json={"amount": amount}, headers=headers["user"])
    assert result.status_code == 201, result.text
    return result.json()["order_code"]


def test_request_signature_matches_independent_example(gateway):
    data = {"returnUrl": "https://cloud.example/return", "orderCode": 123456, "description": "TBT NAP 123456", "cancelUrl": "https://cloud.example/cancel", "amount": 10000}
    canonical = "amount=10000&cancelUrl=https://cloud.example/cancel&description=TBT NAP 123456&orderCode=123456&returnUrl=https://cloud.example/return"
    expected = hmac.new(b"fake-payos_checksum_key", canonical.encode(), hashlib.sha256).hexdigest()
    assert payos.signature(data) == expected
    canonical_response = 'a=&b=[1,{"x":2}]&c={"name":"Bình"}'
    expected = hmac.new(b"fake-payos_checksum_key", canonical_response.encode(), hashlib.sha256).hexdigest()
    assert payos.signature({"c": {"name": "Bình"}, "b": [1, {"x": 2}], "a": None}) == expected


def test_create_link_headers_body_and_pending(client, db, seed, headers, gateway):
    code = create(client, headers)
    request = gateway["calls"][0]
    assert request.url == "https://api-merchant.payos.vn/v2/payment-requests"
    assert request.headers["x-client-id"] == "fake-payos_client_id" and request.headers["x-api-key"] == "fake-payos_api_key"
    body = json.loads(request.content)
    signed = body.pop("signature")
    assert signed == payos.signature(body)
    assert body["orderCode"] == code and 0 < code < 2**53
    assert body["returnUrl"] == "http://testserver/thanh-toan/ket-qua" and body["cancelUrl"] == "http://testserver/thanh-toan/huy"
    assert len(body["description"]) <= 25 and body["description"].isascii() and body["description"].startswith("TBT NAP ")
    payment = db.scalar(select(Payment))
    assert payment.status == "pending" and payment.payment_link_id == "link-test" and payment.transaction_id is None
    assert get_wallet(db, seed["user"].id).balance == 100


@pytest.mark.parametrize("amount", [9999, 5000001, 10000.5, "10000", True, 0, -100])
def test_invalid_amount_never_calls_gateway(client, headers, gateway, amount):
    assert client.post("/api/v1/billing/payos", json={"amount": amount}, headers=headers["user"]).status_code == 422
    assert gateway["calls"] == []


@pytest.mark.parametrize("amount", [10000, 5000000])
def test_amount_boundaries(client, headers, gateway, amount):
    create(client, headers, amount)


@pytest.mark.parametrize("method,path", [("post", "/payos"), ("get", "/payos"), ("get", "/payos/123"), ("post", "/payos/123/cancel")])
def test_missing_configuration_is_503(client, headers, monkeypatch, method, path):
    monkeypatch.setattr(get_settings(), "payos_api_key", None)
    kwargs = {"json": {"amount": 10000}} if path == "/payos" and method == "post" else {}
    result = getattr(client, method)("/api/v1/billing" + path, headers=headers["user"], **kwargs)
    assert result.status_code == 503 and result.json()["detail"] == "Cổng thanh toán chưa được cấu hình."


@pytest.mark.parametrize("signed", [False, True])
def test_paid_credits_once_with_audit_and_notification(notify_settings, client, db, seed, headers, gateway, signed):
    code = create(client, headers)
    gateway.update(status="PAID", amountPaid=10000, signed=signed)
    for _ in range(3):
        result = client.get(f"/api/v1/billing/payos/{code}", headers=headers["user"])
        assert result.status_code == 200 and result.json()["status"] == "paid"
    assert get_wallet(db, seed["user"].id).balance == 10100
    transactions = list(db.scalars(select(Transaction)))
    assert len(transactions) == 1 and transactions[0].kind == "topup" and str(code) in transactions[0].description
    payment = db.scalar(select(Payment))
    assert payment.transaction_id == transactions[0].id and payment.paid_at is not None
    assert db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "payment.paid")) == 1
    notification = db.get(Notification, f"payment:{code}:paid")
    assert notification.pending and seed["user"].email in notification.details and "10100" in notification.details
    assert len(gateway["calls"]) == 2


@pytest.mark.parametrize("phase", ["create", "status", "cancel"])
def test_bad_response_signature_rejected_without_credit(client, db, seed, headers, gateway, phase):
    if phase != "create":
        code = create(client, headers)
    gateway.update(signed="bad", status="PAID", amountPaid=10000)
    if phase == "create":
        result = client.post("/api/v1/billing/payos", json={"amount": 10000}, headers=headers["user"])
    elif phase == "status":
        result = client.get(f"/api/v1/billing/payos/{code}", headers=headers["user"])
    else:
        result = client.post(f"/api/v1/billing/payos/{code}/cancel", headers=headers["user"])
    assert result.status_code == 502 and "invalid-signature" not in result.text and "fake-payos" not in result.text
    assert get_wallet(db, seed["user"].id).balance == 100 and db.scalar(select(func.count(Transaction.id))) == 0
    assert db.scalar(select(func.count(Payment.id))) == (0 if phase == "create" else 1)


@pytest.mark.parametrize("override", [{"orderCode": 1}, {"amount": 9999}, {"amountPaid": 9999}, {"amountPaid": "10000"}, {"status": "UNKNOWN"}, {"id": "other-link"}])
def test_paid_mismatch_never_credits(client, db, seed, headers, gateway, override):
    code = create(client, headers)
    gateway.update(status="PAID", amountPaid=10000, override=override)
    assert client.get(f"/api/v1/billing/payos/{code}", headers=headers["user"]).status_code == 502
    assert get_wallet(db, seed["user"].id).balance == 100 and db.scalar(select(Payment.status)) == "pending"


@pytest.mark.parametrize("status", ["CANCELLED", "EXPIRED", "FAILED", "PROCESSING"])
def test_remote_status_mapping(client, db, headers, gateway, status):
    code = create(client, headers)
    gateway["status"] = status
    result = client.get(f"/api/v1/billing/payos/{code}", headers=headers["user"])
    assert result.json()["status"] == ("pending" if status == "PROCESSING" else status.lower())
    assert db.scalar(select(func.count(Transaction.id))) == 0


def test_ownership_admin_and_paginated_history(client, db, seed, headers, gateway):
    first = create(client, headers)
    second = create(client, headers)
    calls = len(gateway["calls"])
    assert client.get(f"/api/v1/billing/payos/{first}", headers=headers["other"]).status_code == 404
    assert client.post(f"/api/v1/billing/payos/{first}/cancel", headers=headers["other"]).status_code == 404
    assert client.post(f"/api/v1/billing/payos/{first}/cancel", headers=headers["admin"]).status_code == 404
    assert len(gateway["calls"]) == calls
    gateway.update(orderCode=first, status="PAID", amountPaid=10000)
    assert client.get(f"/api/v1/billing/payos/{first}", headers=headers["admin"]).json()["status"] == "paid"
    assert get_wallet(db, seed["admin"].id).balance == 0
    assert client.get("/api/v1/billing/payos?limit=1", headers=headers["user"]).json()[0]["order_code"] == second
    assert client.get("/api/v1/billing/payos?limit=1&offset=1", headers=headers["user"]).json()[0]["order_code"] == first
    assert client.get("/api/v1/billing/payos", headers=headers["other"]).json() == []
    assert client.get("/api/v1/billing/payos?limit=201", headers=headers["user"]).status_code == 422


def test_cancel_owner_and_no_credit(client, db, headers, gateway):
    code = create(client, headers)
    result = client.post(f"/api/v1/billing/payos/{code}/cancel", json={"cancellationReason": "Không còn nhu cầu"}, headers=headers["user"])
    assert result.status_code == 200 and result.json()["status"] == "cancelled"
    request = gateway["calls"][-1]
    assert json.loads(request.content) == {"cancellationReason": "Không còn nhu cầu"}
    calls = len(gateway["calls"])
    assert client.post(f"/api/v1/billing/payos/{code}/cancel", headers=headers["user"]).status_code == 200
    assert len(gateway["calls"]) == calls and db.scalar(select(func.count(Transaction.id))) == 0


@pytest.mark.parametrize("error,expected", [(httpx.ConnectError("RAW-UPSTREAM-SECRET"), 503), (httpx.ReadTimeout("RAW-UPSTREAM-SECRET"), 503)])
def test_network_errors_are_safe(client, headers, gateway, error, expected):
    gateway["error"] = error
    result = client.post("/api/v1/billing/payos", json={"amount": 10000}, headers=headers["user"])
    assert result.status_code == expected and "RAW-UPSTREAM" not in result.text and "fake-payos" not in result.text


@pytest.mark.parametrize("upstream", [400, 401, 500, 503])
def test_http_errors_hide_original_body(client, headers, gateway, upstream):
    gateway["http_status"] = upstream
    result = client.post("/api/v1/billing/payos", json={"amount": 10000}, headers=headers["user"])
    assert result.status_code == 502 and "RAW-UPSTREAM" not in result.text and "fake-payos" not in result.text


def test_non_success_payos_code(client, headers, gateway):
    gateway["code"] = "214"
    assert client.post("/api/v1/billing/payos", json={"amount": 10000}, headers=headers["user"]).status_code == 502


def test_reserved_virtual_topup_namespace(client, headers):
    result = client.post("/api/v1/billing/topup", json={"amount": 10000, "request_id": "payos-123456789"}, headers=headers["user"])
    assert result.status_code == 422


def test_order_code_collision_is_retried(client, db, headers, gateway, monkeypatch):
    monkeypatch.setattr(payos.time, "time_ns", lambda: 1000000000000000)
    choices = iter([1, 1, 2])
    monkeypatch.setattr(payos.secrets, "randbelow", lambda _: next(choices))
    first = create(client, headers)
    second = create(client, headers)
    assert first == 1000000000001 and second == 1000000000002
    assert db.scalar(select(func.count(Payment.id))) == 2


def test_paid_during_cancel_is_credited(client, db, seed, headers, gateway):
    code = create(client, headers)
    gateway.update(cancel_status="PAID", amountPaid=10000)
    assert client.post(f"/api/v1/billing/payos/{code}/cancel", headers=headers["user"]).json()["status"] == "paid"
    assert get_wallet(db, seed["user"].id).balance == 10100
    assert client.get(f"/api/v1/billing/payos/{code}", headers=headers["user"]).json()["status"] == "paid"
    assert db.scalar(select(func.count(Transaction.id))) == 1


def test_amount_range_is_configurable(client, headers, gateway, monkeypatch):
    monkeypatch.setattr(get_settings(), "payos_min_amount", 20000)
    monkeypatch.setattr(get_settings(), "payos_max_amount", 30000)
    assert client.post("/api/v1/billing/payos", json={"amount": 10000}, headers=headers["user"]).status_code == 422
    create(client, headers, 20000)
    create(client, headers, 30000)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://pay.payos.vn/test", "https://[broken"])
def test_bad_checkout_url_is_safe_502(client, headers, gateway, url):
    gateway["override"] = {"checkoutUrl": url}
    assert client.post("/api/v1/billing/payos", json={"amount": 10000}, headers=headers["user"]).status_code == 502


def test_worker_continues_after_one_gateway_error(client, db, headers, gateway, monkeypatch, caplog):
    first = create(client, headers)
    second = create(client, headers)

    def respond(method, path, body=None):
        if path.endswith(str(first)):
            raise payos.PayosError()
        return {"id": "link-test", "orderCode": second, "amount": 10000, "amountPaid": 10000, "status": "PAID"}

    monkeypatch.setattr(payos, "request", respond)
    payos.poll_payments(db)
    assert db.scalar(select(Payment.status).where(Payment.order_code == first)) == "pending"
    assert db.scalar(select(Payment.status).where(Payment.order_code == second)) == "paid"
    assert len(caplog.records) == 1 and "fake-payos" not in caplog.text


def test_worker_poll_and_expiry(client, db, seed, headers, gateway):
    old_code = create(client, headers)
    old = db.scalar(select(Payment).where(Payment.order_code == old_code))
    old.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
    db.commit()
    code = create(client, headers)
    gateway.update(status="PAID", amountPaid=10000)
    calls = len(gateway["calls"])
    payos.poll_payments(db)
    payos.poll_payments(db)
    assert db.get(Payment, old.id).status == "expired"
    assert db.scalar(select(Payment.status).where(Payment.order_code == code)) == "paid"
    assert get_wallet(db, seed["user"].id).balance == 10100
    assert len(gateway["calls"]) == calls + 1
    job = create_scheduler().get_job("payos")
    assert job.trigger.interval.total_seconds() == 60


def test_parallel_poll_credits_once_across_sessions(tmp_path, gateway, monkeypatch):
    engine = create_engine("sqlite+pysqlite:///" + (tmp_path / "concurrent.sqlite").as_posix(), connect_args={"check_same_thread": False, "timeout": 15})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([AllocationLock(id=1), User(id=1, email="parallel@example.com", password_hash="unused"), Wallet(id=1, user_id=1, balance=100), Payment(id=1, user_id=1, order_code=123456789, amount=10000, checkout_url="https://pay.payos.vn/test", qr_code="QR", payment_link_id="link-test")])
        db.commit()
    barrier = Barrier(2)

    def response(method, path, body=None):
        barrier.wait(timeout=10)
        return {"id": "link-test", "orderCode": 123456789, "amount": 10000, "amountPaid": 10000, "status": "PAID"}

    monkeypatch.setattr(payos, "request", response)

    def poll():
        with factory() as db:
            return payos.refresh_payment(db, db.get(Payment, 1)).status

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(lambda _: poll(), range(2))) == ["paid", "paid"]
    with factory() as db:
        assert db.get(Wallet, 1).balance == Decimal("10100.00")
        assert db.scalar(select(func.count(Transaction.id))) == 1
        assert db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "payment.paid")) == 1
    engine.dispose()
