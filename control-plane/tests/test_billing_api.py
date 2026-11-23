# Nguyễn Tâm Bình - 2324801030003
from decimal import Decimal

import pytest

from app.config import get_settings
from app.services.billing import topup


def test_wallet_history_only_contains_own_transactions(client, db, seed, headers):
    topup(db, seed["user"].id, Decimal("50.00"), "owner-topup-01")
    db.commit()
    own = client.get("/api/v1/billing/transactions", headers=headers["user"])
    other = client.get("/api/v1/billing/transactions", headers=headers["other"])
    assert own.status_code == 200
    assert len(own.json()) == 1
    assert other.json() == []


def test_virtual_topup_can_be_disabled(client, headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "virtual_topup_enabled", False)
    response = client.post("/api/v1/billing/topup", json={"amount": "50.00", "request_id": "request-0001"}, headers=headers["user"])
    assert response.status_code == 403


@pytest.mark.parametrize("amount", ["-1.00", "0.00", "0.001", "10000001.00", "NaN", "Infinity"])
def test_rejects_invalid_topups(client, headers, amount):
    response = client.post("/api/v1/billing/topup", json={"amount": amount, "request_id": "request-0001"}, headers=headers["user"])
    assert response.status_code == 422


def test_duplicate_api_topup_does_not_add_money_twice(client, headers):
    data = {"amount": "50.00", "request_id": "request-0001"}
    first = client.post("/api/v1/billing/topup", json=data, headers=headers["user"])
    second = client.post("/api/v1/billing/topup", json=data, headers=headers["user"])
    assert first.status_code == second.status_code == 200
    assert Decimal(second.json()["balance"]) == Decimal("150.00")
