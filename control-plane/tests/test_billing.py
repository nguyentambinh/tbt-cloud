# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import Transaction
from app.services.billing import as_utc, bill_instances, charge_hour, get_wallet, topup
from app.services.proxmox_client import ProxmoxError


def test_charge_once_per_period(db, instance):
    now = datetime.now(timezone.utc)
    assert charge_hour(db, instance, now)
    assert charge_hour(db, instance, now)
    assert get_wallet(db, instance.user_id).balance == Decimal("90.00")
    assert db.scalar(select(func.count(Transaction.id))) == 1


def test_insufficient_balance_stops_without_negative(db, instance):
    wallet = get_wallet(db, instance.user_id)
    wallet.balance = Decimal("5.00")
    db.commit()
    proxmox = MagicMock()
    bill_instances(db, client_factory=lambda node: proxmox)
    assert instance.trang_thai == "suspended"
    assert wallet.balance == Decimal("5.00")
    proxmox.stop.assert_called_once_with(instance.vmid, "vm")


def test_exact_balance_pays_then_stops_next_hour(db, instance):
    now = datetime.now(timezone.utc)
    wallet = get_wallet(db, instance.user_id)
    wallet.balance = Decimal("10.00")
    instance.paid_until = now
    db.commit()
    proxmox = MagicMock()
    bill_instances(db, now, lambda node: proxmox)
    assert wallet.balance == 0
    assert instance.trang_thai == "running"
    bill_instances(db, now + timedelta(hours=1), lambda node: proxmox)
    assert instance.trang_thai == "suspended"
    assert db.scalar(select(func.count(Transaction.id))) == 1


def test_missed_periods_and_retry_are_idempotent(db, instance):
    now = datetime.now(timezone.utc)
    instance.paid_until = now - timedelta(hours=2)
    db.commit()
    bill_instances(db, now, lambda node: MagicMock())
    bill_instances(db, now, lambda node: MagicMock())
    assert get_wallet(db, instance.user_id).balance == Decimal("70.00")
    assert as_utc(instance.paid_until) == now + timedelta(hours=1)
    assert db.scalar(select(func.count(Transaction.id))) == 3


def test_stop_retried_when_node_was_offline(db, instance):
    get_wallet(db, instance.user_id).balance = Decimal("0.00")
    db.commit()
    offline = MagicMock()
    offline.stop.side_effect = ProxmoxError()
    bill_instances(db, client_factory=lambda node: offline)
    assert instance.trang_thai == "suspended"
    online = MagicMock()
    bill_instances(db, client_factory=lambda node: online)
    online.stop.assert_called_once()


def test_stopped_instances_not_charged(db, instance):
    instance.trang_thai = "stopped"
    db.commit()
    bill_instances(db, client_factory=lambda node: MagicMock())
    assert get_wallet(db, instance.user_id).balance == Decimal("100.00")


def test_topup_idempotency_and_amount_conflict(db, seed):
    wallet = topup(db, seed["user"].id, Decimal("50.00"), "request-001")
    topup(db, seed["user"].id, Decimal("50.00"), "request-001")
    assert wallet.balance == Decimal("150.00")
    with pytest.raises(HTTPException) as error:
        topup(db, seed["user"].id, Decimal("60.00"), "request-001")
    assert error.value.status_code == 409
