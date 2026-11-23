# Nguyễn Tâm Bình - 2324801030003
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db, lock_control_plane
from app.dependencies import admin_user
from app.models import AuditLog, Instance, Node, NodeGPU, NodeOSTemplate, OSImage, Payment, Plan, Transaction, User, Wallet
from app.admin_schemas import AdjustmentInput, AdminPlanInput, NodeEditInput, RestoreInput, RoleInput, UserStateInput
from app.schemas import AuditOutput, NodeGPUInput, NodeGPUOutput, OSTemplateInput, OSTemplateOutput, UserOutput
from app.services.gpu import busy_gpu_ids
from app.routers.nodes import require_node
from app.services import notify
from app.services import admin_data, backups
from app.security import generate_vps_password, hash_password

def no_cache(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(no_cache)])


@router.get("/nodes/{node_id}/os-templates", response_model=list[OSTemplateOutput])
def node_os_templates(node_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    return require_node(db, node_id).os_templates


@router.put("/nodes/{node_id}/os-templates", response_model=list[OSTemplateOutput])
def replace_os_templates(node_id: int, data: list[OSTemplateInput], db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    node = require_node(db, node_id)
    if len(data) != len({row.os_ma for row in data}):
        raise HTTPException(status_code=422, detail="Mỗi hệ điều hành chỉ được khai báo một template trên node.")
    images = {image.ma: image for image in db.scalars(select(OSImage))}
    if any(row.os_ma not in images for row in data):
        raise HTTPException(status_code=422, detail="Hệ điều hành chưa có trong danh mục.")
    node.os_templates.clear()
    db.flush()
    node.os_templates.extend(NodeOSTemplate(os_image=images[row.os_ma], template_id=row.template_id) for row in data)
    db.add(AuditLog(user_id=user.id, action="node.os_templates", resource=f"node:{node.id}", detail=", ".join(f"{row.os_ma}:{row.template_id}" for row in data)[:255]))
    db.commit()
    return node.os_templates


def gpu_rows(db, node):
    busy = busy_gpu_ids(db)
    return [{"id": gpu.id, "pci_id": gpu.pci_id, "ten": gpu.ten, "vram_mb": gpu.vram_mb, "dang_dung": gpu.id in busy} for gpu in sorted(node.gpus, key=lambda item: item.id)]


@router.get("/nodes/{node_id}/gpus", response_model=list[NodeGPUOutput])
def node_gpus(node_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    return gpu_rows(db, require_node(db, node_id))


@router.put("/nodes/{node_id}/gpus", response_model=list[NodeGPUOutput])
def replace_gpus(node_id: int, data: list[NodeGPUInput], db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    node = require_node(db, node_id)
    if len(data) != len({row.pci_id for row in data}):
        raise HTTPException(status_code=422, detail="Mỗi GPU chỉ được khai báo một lần trên node.")
    keep = {row.pci_id for row in data}
    busy = busy_gpu_ids(db)
    if any(gpu.id in busy and gpu.pci_id not in keep for gpu in node.gpus):
        raise HTTPException(status_code=409, detail="GPU đang gắn vào máy của khách, hãy xóa máy đó trước khi bỏ GPU.")
    current = {gpu.pci_id: gpu for gpu in node.gpus}
    for gpu in list(node.gpus):
        if gpu.pci_id not in keep:
            if db.scalar(select(Instance.id).where(Instance.gpu_id == gpu.id)):
                raise HTTPException(status_code=409, detail="GPU đã có lịch sử sử dụng, không thể xóa khỏi node.")
            node.gpus.remove(gpu)
    for row in data:
        if row.pci_id in current:
            current[row.pci_id].ten, current[row.pci_id].vram_mb = row.ten, row.vram_mb
        else:
            node.gpus.append(NodeGPU(pci_id=row.pci_id, ten=row.ten, vram_mb=row.vram_mb))
    db.add(AuditLog(user_id=user.id, action="node.gpus", resource=f"node:{node.id}", detail=", ".join(f"{row.pci_id}:{row.ten}" for row in data)[:255]))
    db.commit()
    return gpu_rows(db, node)


@router.post("/notify/test", status_code=202)
def test_notification(db: Session = Depends(get_db), user: User = Depends(admin_user)):
    if not notify.configured():
        raise HTTPException(status_code=503, detail="Thông báo email chưa được cấu hình hoặc đang tắt.")
    queued = notify.enqueue(db, "admin:notify:test", "Kiểm tra thông báo Gmail", {"Sự kiện": "Gửi thử thông báo từ Control API", "Quản trị viên": user.email})
    db.commit()
    return {"detail": "Đã đưa email thử vào hàng đợi." if queued else "Email thử đã có trong hàng đợi hoặc vừa được gửi."}


@router.get("/users", response_model=list[UserOutput])
def users(q: str = Query(default="", max_length=150), status: str | None = Query(default=None, pattern="^(active|blocked)$"), offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    query = select(User).where(User.deleted_at.is_(None))
    if q:
        query = query.where(or_(User.ho_ten.icontains(q, autoescape=True), User.username.icontains(q, autoescape=True), User.email.icontains(q, autoescape=True)))
    if status:
        query = query.where(User.is_blocked.is_(status == "blocked"))
    result = list(db.scalars(query.order_by(User.id).offset(offset).limit(limit)))
    admin_data.record(db, user, "admin.users.read", "users")
    db.commit()
    return result


@router.get("/audit-logs", response_model=list[AuditOutput])
def audit_logs(offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    return list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit)))


@router.get("/stats")
def stats(start: date | None = None, end: date | None = None, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    result = admin_data.summary(db, start, end)
    result.update({"nodes_online": db.scalar(select(func.count(Node.id)).where(Node.trang_thai == "online")), "instances": db.scalar(select(func.count(Instance.id)).where(Instance.trang_thai != "deleted"))})
    admin_data.record(db, user, "admin.stats.read", "stats")
    db.commit()
    return result


@router.post("/instances/{instance_id}/resolve-provisioning", response_model=dict)
def resolve_provisioning(instance_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    instance = db.get(Instance, instance_id, populate_existing=True)
    if instance is None or instance.trang_thai != "provisioning":
        raise HTTPException(status_code=409, detail="Instance không ở trạng thái chờ cấp phát.")
    instance.trang_thai = "error"
    db.add(AuditLog(user_id=user.id, action="instance.resolve_provisioning", resource=f"instance:{instance.id}", detail="Đánh dấu để kiểm tra và thu hồi an toàn"))
    db.commit()
    return {"detail": "Có thể kiểm tra node và xóa instance để thu hồi tài nguyên."}


def lock_admin(db, actor):
    lock_control_plane(db)
    db.refresh(actor)
    if actor.role != "admin" or actor.is_blocked or actor.deleted_at is not None:
        raise HTTPException(status_code=403, detail="Quyền quản trị đã thay đổi. Hãy đăng nhập lại.")


def require_user(db, user_id):
    target = db.get(User, user_id, populate_existing=True)
    if target is None or target.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    return target


def preserve_admin(db, actor, target):
    if target.id == actor.id:
        raise HTTPException(status_code=409, detail="Bạn không thể tự khóa, xóa hoặc hạ quyền tài khoản đang sử dụng.")
    if target.role == "admin" and not target.is_blocked and db.scalar(select(func.count(User.id)).where(User.role == "admin", User.is_blocked.is_(False), User.deleted_at.is_(None))) <= 1:
        raise HTTPException(status_code=409, detail="Hệ thống cần còn ít nhất một quản trị viên đang hoạt động.")


def user_info(db, target):
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == target.id))
    return {**{field: getattr(target, field) for field in ("id", "ho_ten", "username", "email", "role", "is_blocked", "created_at")}, "balance": wallet.balance if wallet else Decimal(0)}


@router.get("/users/{user_id}")
def user_detail(user_id: int, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    target = require_user(db, user_id)
    result = user_info(db, target)
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id))
    result["transactions"] = admin_data.data_page(db, "transactions", column="wallet_id", value=str(wallet.id), offset=offset, limit=limit) if wallet else {"items": [], "total": 0}
    result["instances"] = admin_data.data_page(db, "instances", column="user_id", value=str(user_id), offset=offset, limit=limit)
    log_fields = admin_data.TABLES["audit-logs"][1]
    logs = select(*(getattr(AuditLog, field) for field in log_fields)).where(or_(AuditLog.user_id == user_id, AuditLog.resource == f"user:{user_id}"))
    result["logs"] = {"items": [dict(row) for row in db.execute(logs.order_by(AuditLog.id.desc()).offset(offset).limit(limit)).mappings()], "total": db.scalar(select(func.count()).select_from(logs.subquery())), "offset": offset, "limit": limit}
    admin_data.record(db, user, "admin.user.read", f"user:{user_id}")
    db.commit()
    return result


@router.put("/users/{user_id}/state")
def user_state(user_id: int, data: UserStateInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    target = require_user(db, user_id)
    if data.is_blocked:
        preserve_admin(db, user, target)
    if target.is_blocked != data.is_blocked:
        target.token_version += 1
    target.is_blocked = data.is_blocked
    admin_data.record(db, user, "admin.user.block" if data.is_blocked else "admin.user.unblock", f"user:{user_id}")
    db.commit()
    return user_info(db, target)


@router.put("/users/{user_id}/role")
def user_role(user_id: int, data: RoleInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    target = require_user(db, user_id)
    if data.role == "user" and target.role == "admin":
        preserve_admin(db, user, target)
    if target.role != data.role:
        target.token_version += 1
    target.role = data.role
    admin_data.record(db, user, "admin.user.role", f"user:{user_id}", data.role)
    db.commit()
    return user_info(db, target)


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, response: Response, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    target = require_user(db, user_id)
    password = generate_vps_password() + "!"
    target.password_hash = hash_password(password)
    target.token_version += 1
    admin_data.record(db, user, "admin.user.password", f"user:{user_id}", "Mật khẩu tạm chỉ hiện trong phản hồi này")
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"temporary_password": password, "detail": "Sao chép mật khẩu tạm và chuyển riêng cho người dùng. Mật khẩu chỉ hiện một lần."}


@router.post("/users/{user_id}/wallet")
def adjust_wallet(user_id: int, data: AdjustmentInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    target = require_user(db, user_id)
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == target.id).with_for_update())
    if wallet is None:
        wallet = Wallet(user_id=target.id, balance=Decimal(0))
        db.add(wallet)
        db.flush()
    key = f"admin-adjust:{user.id}:{data.request_id}"
    previous = db.scalar(select(Transaction).where(Transaction.idempotency_key == key))
    if previous:
        if previous.wallet_id != wallet.id or previous.amount != data.amount or previous.description != data.reason:
            raise HTTPException(status_code=409, detail="Mã điều chỉnh đã dùng với nội dung khác.")
        return {"balance": wallet.balance, "transaction_id": previous.id}
    if wallet.balance + data.amount < 0:
        raise HTTPException(status_code=409, detail="Điều chỉnh này khiến số dư âm. Hãy nhập số tiền khác.")
    wallet.balance += data.amount
    transaction = Transaction(wallet_id=wallet.id, amount=data.amount, kind="adjustment", idempotency_key=key, description=data.reason)
    db.add(transaction)
    db.flush()
    admin_data.record(db, user, "admin.wallet.adjust", f"user:{user_id}", f"{data.amount}: {data.reason}")
    db.commit()
    return {"balance": wallet.balance, "transaction_id": transaction.id}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    target = require_user(db, user_id)
    preserve_admin(db, user, target)
    if db.scalar(select(func.count(Instance.id)).where(Instance.user_id == user_id, Instance.trang_thai != "deleted")):
        raise HTTPException(status_code=409, detail="Chỉ xóa tài khoản khi đã hủy hết dịch vụ.")
    target.deleted_at = datetime.now(timezone.utc)
    target.is_blocked = True
    target.token_version += 1
    target.email = f"deleted-{target.id}-{uuid4().hex}@invalid.local"
    target.username = None
    target.ho_ten = "Tài khoản đã xóa"
    target.password_hash = hash_password(generate_vps_password())
    admin_data.record(db, user, "admin.user.delete", f"user:{user_id}", "Ẩn danh tài khoản; giữ giao dịch và nhật ký đối soát")
    db.commit()
    return {"detail": "Đã xóa thông tin đăng nhập. Giao dịch và nhật ký được giữ để đối soát."}


@router.get("/data/{table}")
def query_data(table: str, q: str = Query("", max_length=150), column: str | None = None, value: str | None = Query(None, max_length=254), start: date | None = None, end: date | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), csv: bool = False, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    result = admin_data.data_page(db, table, q, column, value, start, end, offset, limit)
    admin_data.record(db, user, "admin.data.csv" if csv else "admin.data.read", table)
    db.commit()
    return admin_data.csv_response(result["items"], result["columns"], f"{table}-{offset}.csv") if csv else result


@router.get("/revenue")
def revenue(start: date | None = None, end: date | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    result = admin_data.revenue_series(db, start, end, offset, limit)
    admin_data.record(db, user, "admin.revenue.read", "payments")
    db.commit()
    return result


@router.get("/reports/{section}/csv")
def export_report(section: str, start: date | None = None, end: date | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    if section in {"daily", "monthly"}:
        rows = admin_data.revenue_series(db, start, end, offset, limit)[section]
    else:
        summary = admin_data.summary(db, start, end)
        tables = {"totals": [{key: summary[key] for key in ("revenue", "spent", "wallet_balance", "users", "new_7", "new_30")}], **summary["running"], "top_customers": summary["top_customers"], "nodes": summary["nodes"]}
        if section not in tables:
            raise HTTPException(status_code=404, detail="Không tìm thấy bảng thống kê.")
        rows = tables[section][offset:offset + limit]
    admin_data.record(db, user, "admin.report.csv", section)
    db.commit()
    return admin_data.csv_response(rows, list(rows[0]) if rows else ["Không có dữ liệu"], f"{section}-{offset}.csv")


@router.get("/map")
def admin_map(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    from app.routers.nodes import map_nodes
    result = admin_data.data_page(db, "instances", offset=offset, limit=limit)
    query = select(Instance).where(Instance.trang_thai != "deleted").order_by(Instance.id)
    result["items"] = [{field: getattr(row, field) for field in admin_data.TABLES["instances"][1]} for row in db.scalars(query.offset(offset).limit(limit))]
    result["total"] = db.scalar(select(func.count()).select_from(query.subquery()))
    result["nodes"] = [node.model_dump() for node in map_nodes(db)]
    admin_data.record(db, user, "admin.map.read", "instances")
    db.commit()
    return result


@router.post("/plans", status_code=201)
def add_plan(data: AdminPlanInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    plan = Plan(**data.model_dump())
    db.add(plan)
    db.flush()
    admin_data.record(db, user, "admin.plan.create", f"plan:{plan.id}")
    db.commit()
    return {"id": plan.id, **data.model_dump()}


@router.put("/plans/{plan_id}")
def edit_plan(plan_id: int, data: AdminPlanInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy gói.")
    if plan.dich_vu != data.dich_vu and db.scalar(select(func.count(Instance.id)).where(Instance.plan_id == plan_id)):
        raise HTTPException(status_code=409, detail="Gói đã có lịch sử dịch vụ, không thể đổi loại dịch vụ.")
    for key, value in data.model_dump().items():
        setattr(plan, key, value)
    admin_data.record(db, user, "admin.plan.update", f"plan:{plan_id}")
    db.commit()
    return {"id": plan.id, **data.model_dump()}


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy gói.")
    if db.scalar(select(func.count(Instance.id)).where(Instance.plan_id == plan_id)):
        raise HTTPException(status_code=409, detail="Gói đã được dùng cho dịch vụ. Hãy ẩn gói để giữ lịch sử.")
    db.delete(plan)
    admin_data.record(db, user, "admin.plan.delete", f"plan:{plan_id}")
    db.commit()
    return {"detail": "Đã xóa gói chưa được sử dụng."}


@router.put("/nodes/{node_id}")
def edit_node(node_id: int, data: NodeEditInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_admin(db, user)
    node = require_node(db, node_id)
    for key, value in data.model_dump().items():
        setattr(node, key, value)
    admin_data.record(db, user, "admin.node.update", f"node:{node_id}")
    db.commit()
    return {"id": node.id, **data.model_dump()}


@router.get("/backups")
def list_backups(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    rows = backups.listing()
    admin_data.record(db, user, "admin.backup.list", "backups")
    db.commit()
    return {"items": rows[offset:offset + limit], "total": len(rows), "offset": offset, "limit": limit}


@router.post("/backups", status_code=201)
def create_backup(db: Session = Depends(get_db), user: User = Depends(admin_user)):
    with backups.operation():
        admin_data.record(db, user, "admin.backup.start", "backups")
        db.commit()
        try:
            result = backups.create(user.id)
            removed = backups.prune((result["name"],))
        except HTTPException:
            admin_data.record(db, user, "admin.backup.failed", "backups")
            db.commit()
            raise
        admin_data.record(db, user, "admin.backup.create", result["name"])
        for name in removed:
            admin_data.record(db, user, "admin.backup.prune", name)
        db.commit()
        return result


@router.get("/backups/{name}/download")
def download_backup(name: str, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    from fastapi.responses import FileResponse
    path = backups.backup_path(name)
    admin_data.record(db, user, "admin.backup.download", name)
    db.commit()
    return FileResponse(path, media_type="application/octet-stream", filename=name, headers={"Cache-Control": "no-store"})


@router.delete("/backups/{name}")
def delete_backup(name: str, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    with backups.operation():
        backups.remove(name)
        admin_data.record(db, user, "admin.backup.delete", name)
        db.commit()
    return {"detail": "Đã xóa bản sao lưu."}


@router.post("/backups/{name}/restore")
def restore_backup(name: str, data: RestoreInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    from app.models import User as RestoredUser
    actor_id = user.id
    with backups.operation():
        path = backups.backup_path(name)
        admin_data.record(db, user, "admin.backup.restore.start", name)
        db.commit()
        try:
            safety = backups.create(actor_id, safety=True)
        except HTTPException:
            admin_data.record(db, user, "admin.backup.restore.failed", name, "Không tạo được bản sao lưu an toàn; chưa chạy khôi phục")
            db.commit()
            raise
        admin_data.record(db, user, "admin.backup.safety", safety["name"])
        for removed in backups.prune((name, safety["name"])):
            admin_data.record(db, user, "admin.backup.prune", removed)
        db.commit()
        try:
            backups.invalidate_sessions()
            backups.run_postgres("pg_restore", path)
        except HTTPException:
            admin_data.record(db, user, "admin.backup.restore.failed", name, f"Sao lưu an toàn: {safety['name']}")
            db.commit()
            raise
        db.expire_all()
        restored = db.get(RestoredUser, actor_id)
        db.add(AuditLog(user_id=restored.id if restored else None, action="admin.backup.restore", resource=name, detail=f"Người yêu cầu {actor_id}; sao lưu an toàn: {safety['name']}"))
        for removed in backups.prune((name, safety["name"])):
            db.add(AuditLog(user_id=restored.id if restored else None, action="admin.backup.prune", resource=removed))
        db.commit()
    return {"detail": "Đã khôi phục CSDL. Hãy đăng nhập lại.", "safety_backup": safety["name"]}
