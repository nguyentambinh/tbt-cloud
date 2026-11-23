# Nguyễn Tâm Bình - 2324801030003
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.models import AuditLog, Instance, Plan, Transaction


EXPECTED = [
    ("Nano", "vps", 1, 512, 10, 300, "Thử nghiệm, bot nhỏ, máy học Linux"),
    ("Lớn", "vps", 4, 4096, 30, 2000, "Ứng dụng web nhiều người dùng"),
    ("Rất lớn", "vps", 8, 8192, 40, 4000, "Biên dịch, xử lý dữ liệu"),
    ("Tối ưu CPU", "vps", 4, 2048, 20, 1500, "Tính toán nặng, ít bộ nhớ"),
    ("Tối ưu RAM", "vps", 2, 8192, 20, 2500, "Bộ nhớ đệm, phân tích dữ liệu"),
    ("CSDL Cơ bản", "postgres", 1, 1024, 10, 600, "Đồ án, ứng dụng thử"),
    ("CSDL Tiêu chuẩn", "postgres", 2, 2048, 20, 1200, "Ứng dụng chạy thật, vài chục kết nối"),
    ("CSDL Hiệu năng", "postgres", 4, 4096, 40, 2400, "Truy vấn nặng, dữ liệu lớn hơn"),
    ("Web Cơ bản", "webapp", 1, 1024, 10, 500, "Trang tĩnh, portfolio"),
    ("Web Tiêu chuẩn", "webapp", 2, 2048, 15, 1000, "Ứng dụng Node.js nhỏ"),
    ("Web Mở rộng", "webapp", 4, 4096, 20, 2000, "Ứng dụng nhiều truy cập"),
]


@pytest.mark.parametrize("duplicate", [False, True])
def test_catalog_migration_upgrade_data_and_downgrade(tmp_path, monkeypatch, duplicate):
    url = "sqlite+pysqlite:///" + (tmp_path / "catalog.sqlite").as_posix()
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0004_paas")
    engine = create_engine(url)
    old = Table("plans", MetaData(), autoload_with=engine)
    legacy = [dict(id=41, ten="Nhỏ", vcpu=1, ram_mb=1024, disk_gb=10, gia_theo_gio=500), dict(id=42, ten="Vừa", vcpu=2, ram_mb=2048, disk_gb=20, gia_theo_gio=1000), dict(id=43, ten="Gói riêng", vcpu=3, ram_mb=3000, disk_gb=12, gia_theo_gio=777)]
    if duplicate:
        legacy.append(dict(id=44, ten="Nano", vcpu=2, ram_mb=768, disk_gb=15, gia_theo_gio=350))
    with engine.begin() as connection:
        connection.execute(old.insert(), legacy)
    engine.dispose()
    command.upgrade(config, "0005_plan_catalog")
    engine = create_engine(url)
    plans = Table("plans", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        rows = {row["ten"]: dict(row) for row in connection.execute(select(plans)).mappings()}
        assert len(rows) == 14
        for row in legacy:
            assert all(rows[row["ten"]][key] == value for key, value in row.items())
            assert rows[row["ten"]]["dich_vu"] == "vps"
        for name, service, cpu, ram, disk, price, description in EXPECTED:
            if duplicate and name == "Nano":
                continue
            row = rows[name]
            assert tuple(row[key] for key in ("dich_vu", "vcpu", "ram_mb", "disk_gb", "gia_theo_gio", "mo_ta")) == (service, cpu, ram, disk, price, description)
            assert service == "vps" or disk >= 10
        assert rows["Nhỏ"]["mo_ta"] == "Web cá nhân, môi trường học tập"
        assert rows["Vừa"]["mo_ta"] == "Ứng dụng nhỏ có cơ sở dữ liệu"
        assert rows["Gói riêng"]["mo_ta"] == ""
    with engine.begin() as connection:
        connection.execute(old.insert().values(ten="Mặc định", vcpu=1, ram_mb=512, disk_gb=10, gia_theo_gio=1))
        row = connection.execute(select(plans).where(plans.c.ten == "Mặc định")).mappings().one()
        assert row["dich_vu"] == "vps" and row["mo_ta"] == ""
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(plans.update().values(dich_vu="invalid"))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(plans.update().values(dich_vu=None))
    engine.dispose()
    command.downgrade(config, "0004_paas")
    engine = create_engine(url)
    assert {column["name"] for column in inspect(engine).get_columns("plans")} == set(old.columns.keys())
    with engine.connect() as connection:
        for row in legacy:
            assert dict(connection.execute(select(old).where(old.c.id == row["id"])).mappings().one()) == row
        assert connection.scalar(text("SELECT COUNT(*) FROM plans")) == 15
    engine.dispose()
    command.upgrade(config, "0005_plan_catalog")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM plans")) == 15
    engine.dispose()


@pytest.mark.parametrize("service", [None, "vps", "postgres", "webapp"])
def test_public_plans_filter_and_price_order(client, db, seed, service):
    db.add_all([Plan(ten=f"{kind}-{price}", dich_vu=kind, mo_ta="Dùng thử", vcpu=1, ram_mb=1024, disk_gb=10, gia_theo_gio=price) for kind in ("vps", "postgres", "webapp") for price in (30, 5, 20)])
    db.commit()
    response = client.get("/api/v1/plans", params={"dich_vu": service} if service else {})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == (10 if service is None else 4 if service == "vps" else 3)
    assert all(service is None or row["dich_vu"] == service for row in rows)
    assert [Decimal(row["gia_theo_gio"]) for row in rows] == sorted(Decimal(row["gia_theo_gio"]) for row in rows)
    assert all("mo_ta" in row for row in rows)


def test_plan_filter_rejects_unknown_service(client):
    assert client.get("/api/v1/plans?dich_vu=invalid").status_code == 422


@pytest.mark.parametrize("service", ["vps", "postgres", "webapp"])
def test_admin_creates_service_plan(client, headers, service):
    payload = dict(ten="Gói thử", dich_vu=service, mo_ta="Ứng dụng thử", vcpu=1, ram_mb=1024, disk_gb=10, gia_theo_gio=100)
    assert client.post("/api/v1/plans", json=payload).status_code == 401
    assert client.post("/api/v1/plans", json=payload, headers=headers["user"]).status_code == 403
    response = client.post("/api/v1/plans", json=payload, headers=headers["admin"])
    assert response.status_code == 201
    assert response.json()["dich_vu"] == service and response.json()["mo_ta"] == payload["mo_ta"]


@pytest.mark.parametrize("extra", [{"dich_vu": "invalid"}, {"mo_ta": "a" * 161}, {"dich_vu": "postgres", "disk_gb": 8}, {"dich_vu": "webapp", "disk_gb": 9}])
def test_invalid_plan_input(client, headers, extra):
    payload = dict(ten="Sai", vcpu=1, ram_mb=1024, disk_gb=10, gia_theo_gio=100)
    assert client.post("/api/v1/plans", json={**payload, **extra}, headers=headers["admin"]).status_code == 422


@pytest.mark.parametrize("plan_service,request_service", [(a, b) for a in ("vps", "postgres", "webapp") for b in ("vps", "postgres", "webapp") if a != b])
def test_wrong_service_plan_rejected_without_side_effects(client, db, seed, headers, instance_payload, mock_proxmox, plan_service, request_service):
    seed["plan"].dich_vu = plan_service
    seed["user"].wallet.balance = 0
    db.commit()
    response = client.post("/api/v1/instances", json={**instance_payload, "dich_vu": request_service, "repo_url": "https://example.test/app.git"}, headers=headers["user"])
    assert response.status_code == 422
    assert response.json()["detail"] == "Gói này dành cho dịch vụ khác."
    mock_proxmox[0].assert_not_called()
    assert seed["user"].wallet.balance == 0
    assert seed["node"].used_vcpu == 0
    for model in (Instance, Transaction, AuditLog):
        assert db.scalar(select(model.id)) is None
