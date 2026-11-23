# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db, lock_control_plane
from app.dependencies import admin_user
from app.models import AuditLog, Node, NodeOSTemplate, OSImage, User
from app.schemas import NodeInput, NodeOutput, NodeMapOutput
from app.security import encrypt_secret
from app.services.node_sync import sync_node
from app.services.proxmox_client import ProxmoxClient

router = APIRouter(prefix="/nodes", tags=["nodes"])


def map_nodes(db):
    now = datetime.now(timezone.utc)
    result = []
    for node in db.scalars(select(Node).order_by(Node.id)):
        seen = node.last_seen_at
        if seen is not None and seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        online = node.trang_thai == "online" and seen is not None and 0 <= (now - seen).total_seconds() <= 120
        values = {field: getattr(node, field) for field in NodeMapOutput.model_fields if field != "online"}
        values["last_seen_at"] = seen
        result.append(NodeMapOutput(**values, online=online))
    return result


@router.get("/map", response_model=list[NodeMapOutput])
def node_map(db: Session = Depends(get_db), user: User = Depends(admin_user)):
    return map_nodes(db)


def require_node(db, node_id):
    node = db.get(Node, node_id, populate_existing=True)
    if node is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy node.")
    return node


@router.get("", response_model=list[NodeOutput])
def list_nodes(db: Session = Depends(get_db), user: User = Depends(admin_user)):
    return list(db.scalars(select(Node).order_by(Node.id)))


@router.post("", response_model=NodeOutput, status_code=201)
def create_node(data: NodeInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    values = data.model_dump(exclude={"token_secret"})
    node = Node(**values, token_secret=encrypt_secret(data.token_secret.get_secret_value()))
    db.add(node)
    try:
        db.flush()
        debian = db.scalar(select(OSImage).where(OSImage.ma == "debian13"))
        if node.vm_template_id is not None and debian is not None:
            node.os_templates.append(NodeOSTemplate(os_image=debian, template_id=node.vm_template_id))
        db.add(AuditLog(user_id=user.id, action="node.create", resource=f"node:{node.id}"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên node hoặc địa chỉ mesh đã tồn tại.") from None
    return node


@router.post("/{node_id}/check")
def check_node(node_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    ProxmoxClient(require_node(db, node_id)).check_connection()
    db.add(AuditLog(user_id=user.id, action="node.check", resource=f"node:{node_id}"))
    db.commit()
    return {"detail": "Kết nối đến node thành công."}


@router.post("/{node_id}/sync", response_model=NodeOutput)
def synchronize_node(node_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    lock_control_plane(db)
    node = require_node(db, node_id)
    connected = sync_node(db, node)
    db.add(AuditLog(user_id=user.id, action="node.sync", resource=f"node:{node_id}", detail="Đồng bộ thành công" if connected else "Node mất kết nối"))
    db.commit()
    return node
