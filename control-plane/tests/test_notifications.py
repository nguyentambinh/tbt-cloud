# Nguyễn Tâm Bình - 2324801030003
from app.models import AuditLog


def test_customer_notifications_links_and_read(client, db, headers, seed, instance):
    db.add_all([AuditLog(user_id=seed["user"].id, action="instance.create", resource=f"instance:{instance.id}"), AuditLog(user_id=seed["user"].id, action="payment.paid", resource="payment:123456", detail="Nạp 50000 VND qua payOS"), AuditLog(user_id=seed["user"].id, action="auth.login", resource="user:1"), AuditLog(user_id=seed["other"].id, action="instance.create", resource="instance:999")])
    db.commit()
    data = client.get("/api/v1/notifications", headers=headers["user"]).json()
    assert data["chua_doc"] == 2 and [item["link"] for item in data["items"]] == ["/vi?orderCode=123456", f"/may-chu/{instance.id}"]
    assert data["items"][1]["tieu_de"] == f"Đã tạo máy chủ {instance.ten}" and data["items"][0]["noi_dung"] == "Nạp 50000 VND qua payOS"
    assert client.post("/api/v1/notifications/read", headers=headers["user"]).json() == {"chua_doc": 0}
    data = client.get("/api/v1/notifications", headers=headers["user"]).json()
    assert data["chua_doc"] == 0 and all(item["da_doc"] for item in data["items"])
    db.add(AuditLog(user_id=seed["user"].id, action="billing.suspend", resource=f"instance:{instance.id}"))
    db.commit()
    data = client.get("/api/v1/notifications", headers=headers["user"]).json()
    assert data["chua_doc"] == 1 and data["items"][0]["link"] == "/vi" and data["items"][0]["da_doc"] is False


def test_admin_notifications_system_wide(client, db, headers, seed):
    db.add_all([AuditLog(user_id=seed["user"].id, action="auth.register", resource=f"user:{seed['user'].id}"), AuditLog(user_id=seed["user"].id, action="instance.create", resource="instance:1")])
    db.commit()
    data = client.get("/api/v1/notifications", headers=headers["admin"]).json()
    assert data["chua_doc"] == 1 and data["items"][0]["tieu_de"] == "Tài khoản mới: owner@example.com" and data["items"][0]["link"] == f"/quan-tri/nguoi-dung/{seed['user'].id}"
    assert client.get("/api/v1/notifications").status_code == 401
