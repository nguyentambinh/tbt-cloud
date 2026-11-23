# Nguyễn Tâm Bình - 2324801030003
import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_, select

from app.models import AuditLog, Instance, Node, Payment, Plan, Transaction, User, Wallet

TABLES = {
    "users": (User, ("id", "ho_ten", "username", "email", "role", "is_blocked", "created_at", "deleted_at", "balance")),
    "instances": (Instance, ("id", "ten", "user_id", "node_id", "plan_id", "dich_vu", "loai", "os_image_id", "trang_thai", "vcpu", "ram_mb", "disk_gb", "gia_theo_gio", "created_at")),
    "transactions": (Transaction, ("id", "wallet_id", "instance_id", "amount", "kind", "description", "created_at")),
    "payments": (Payment, ("id", "user_id", "order_code", "amount", "status", "created_at", "paid_at")),
    "audit-logs": (AuditLog, ("id", "user_id", "action", "resource", "detail", "created_at")),
    "plans": (Plan, ("id", "ten", "dich_vu", "mo_ta", "vcpu", "ram_mb", "disk_gb", "gia_theo_gio", "active")),
    "nodes": (Node, ("id", "ten", "mesh_ip", "proxmox_node", "storage", "bridge", "trang_thai", "used_vcpu", "total_vcpu", "used_ram_mb", "total_ram_mb", "used_disk_gb", "total_disk_gb", "last_seen_at", "cpu_percent", "measured_ram_mb", "measured_disk_gb")),
}


def record(db, actor, action, resource, detail=""):
    db.add(AuditLog(user_id=actor.id, action=action, resource=resource, detail=detail[:255]))


def date_bounds(start, end):
    if end == date.max:
        raise HTTPException(status_code=422, detail="Ngày kết thúc vượt phạm vi hỗ trợ.")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="Ngày bắt đầu cần trước hoặc bằng ngày kết thúc.")
    return datetime.combine(start, time.min, timezone.utc) if start else None, datetime.combine(end + timedelta(days=1), time.min, timezone.utc) if end else None


def during(query, column, bounds):
    start, end = bounds
    if start:
        query = query.where(column >= start)
    if end:
        query = query.where(column < end)
    return query


def data_page(db, table, q="", column=None, value=None, start=None, end=None, offset=0, limit=50):
    if table not in TABLES:
        raise HTTPException(status_code=404, detail="Bảng dữ liệu không nằm trong danh mục truy xuất.")
    model, fields = TABLES[table]
    columns = {field: getattr(model, field) for field in fields if field != "balance"}
    if table == "users":
        columns["balance"] = Wallet.balance
    query = select(*(column.label(field) for field, column in columns.items()))
    if table == "users":
        query = query.select_from(User).outerjoin(Wallet, Wallet.user_id == User.id).where(User.deleted_at.is_(None))
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(or_(*(cast(column, String).ilike(pattern, escape="\\") for column in columns.values())))
    if column:
        if column not in fields or value is None:
            raise HTTPException(status_code=422, detail="Cột lọc hoặc giá trị lọc không hợp lệ.")
        field = columns[column]
        if column in {"is_blocked", "active"}:
            if value not in {"true", "false", "1", "0"}:
                raise HTTPException(status_code=422, detail="Bộ lọc trạng thái cần giá trị true hoặc false.")
            query = query.where(field.is_(value in {"true", "1"}))
        else:
            query = query.where(cast(field, String) == value)
    bounds = date_bounds(start, end)
    if start or end:
        date_column = getattr(model, "created_at", getattr(model, "last_seen_at", None))
        if date_column is None:
            raise HTTPException(status_code=422, detail="Bảng này không có cột thời gian để lọc.")
        query = during(query, date_column, bounds)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = [dict(row) for row in db.execute(query.order_by(model.id.desc()).offset(offset).limit(limit)).mappings()]
    return {"columns": fields, "items": rows, "total": total, "offset": offset, "limit": limit}


def csv_response(rows, columns, filename):
    from fastapi.responses import Response

    def cell(value):
        text = "" if value is None else str(value)
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            return text
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else text

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows([cell(row.get(column)) for column in columns] for row in rows)
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


def summary(db, start=None, end=None):
    from app.models import OSImage
    from app.routers.nodes import map_nodes

    bounds = date_bounds(start, end)
    now = datetime.now(timezone.utc)
    paid = during(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paid"), Payment.paid_at, bounds)
    spent = during(select(func.coalesce(-func.sum(Transaction.amount), 0)).where(Transaction.kind == "usage"), Transaction.created_at, bounds)
    users = select(func.count(User.id)).where(User.deleted_at.is_(None))
    running = select(Instance).where(Instance.trang_thai == "running")
    running = during(running, Instance.created_at, bounds)
    active = running.subquery()
    breakdowns = {}
    for name, column in (("service", active.c.dich_vu), ("os", active.c.os_image_id), ("node", active.c.node_id)):
        breakdowns[name] = [{"name": key if key is not None else "Không khai báo", "count": count} for key, count in db.execute(select(column, func.count()).group_by(column))]
    images = {image.id: image.ten for image in db.scalars(select(OSImage))}
    node_records = list(db.scalars(select(Node)))
    nodes = {node.id: node.ten for node in node_records}
    telemetry = {node.id: {field: getattr(node, field) for field in ("cpu_percent", "measured_ram_mb", "measured_disk_gb")} for node in node_records}
    for row in breakdowns["os"]:
        row["name"] = images.get(row["name"], "LXC / PaaS chưa khai báo OS")
    for row in breakdowns["node"]:
        row["name"] = nodes.get(row["name"], f"Node {row['name']}")
    top_query = select(User.id, User.ho_ten, User.username, User.email, (-func.sum(Transaction.amount)).label("spent")).join(Wallet, Wallet.user_id == User.id).join(Transaction, Transaction.wallet_id == Wallet.id).where(Transaction.kind == "usage")
    top_query = during(top_query, Transaction.created_at, bounds).group_by(User.id, User.ho_ten, User.username, User.email).order_by((-func.sum(Transaction.amount)).desc(), User.id).limit(20)
    return {"revenue": db.scalar(paid), "spent": db.scalar(spent), "wallet_balance": db.scalar(select(func.coalesce(func.sum(Wallet.balance), 0))), "users": db.scalar(during(users, User.created_at, bounds)), "new_7": db.scalar(users.where(User.created_at >= now - timedelta(days=7))), "new_30": db.scalar(users.where(User.created_at >= now - timedelta(days=30))), "running": breakdowns, "top_customers": [dict(row) for row in db.execute(top_query).mappings()], "nodes": [{**node.model_dump(), **telemetry[node.id]} for node in map_nodes(db)], "scope": "Doanh thu/chi tiêu theo ngày giao dịch UTC; dịch vụ chạy tạo trong khoảng chọn. Số dư, tài nguyên và người mới 7/30 ngày là hiện tại."}


def revenue_series(db, start=None, end=None, offset=0, limit=50):
    today = datetime.now(timezone.utc).date()
    default_months = start is None and end is None
    start, end = start or today - timedelta(days=29), end or today
    bounds = date_bounds(start, end)
    if (end - start).days > 3660:
        raise HTTPException(status_code=422, detail="Chọn khoảng thời gian không quá 10 năm.")
    query = during(select(func.date(Payment.paid_at).label("day"), func.sum(Payment.amount).label("amount")).where(Payment.status == "paid"), Payment.paid_at, bounds).group_by(func.date(Payment.paid_at))
    amounts = {str(day): amount for day, amount in db.execute(query)}
    days = [{"period": (start + timedelta(days=index)).isoformat(), "amount": amounts.get((start + timedelta(days=index)).isoformat(), 0)} for index in range((end - start).days + 1)]
    month_index = today.year * 12 + today.month - 1 - 11
    monthly_start = date(month_index // 12, month_index % 12 + 1, 1) if default_months else start
    monthly_query = during(select(func.date(Payment.paid_at), func.sum(Payment.amount)).where(Payment.status == "paid"), Payment.paid_at, date_bounds(monthly_start, end)).group_by(func.date(Payment.paid_at))
    months = {}
    index = monthly_start.year * 12 + monthly_start.month - 1
    last = end.year * 12 + end.month - 1
    for month in range(index, last + 1):
        months[f"{month // 12:04d}-{month % 12 + 1:02d}"] = Decimal(0)
    for day, amount in db.execute(monthly_query):
        months[str(day)[:7]] += amount
    return {"daily": days[offset:offset + limit], "monthly": [{"period": key, "amount": amount} for key, amount in months.items()], "daily_total": len(days), "monthly_total": len(months), "offset": offset, "limit": limit}
