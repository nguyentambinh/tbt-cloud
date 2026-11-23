# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import lock_control_plane
from app.models import AuditLog, Instance, Node
from app.services.billing import as_utc, charge_due_hours
from app.services.proxmox_client import ProxmoxClient, ProxmoxError
from app.services import notify


def sync_node(db, node, client_factory=ProxmoxClient):
    lock_control_plane(db)
    try:
        client = client_factory(node)
        resources = client.get_node_resources()
    except ProxmoxError:
        node.trang_thai = "offline"
        if node.last_seen_at and as_utc(node.last_seen_at) < datetime.now(timezone.utc) - timedelta(seconds=120) and not node.notify_offline:
            node.notify_offline = True
            notify.enqueue(db, f"node:{node.id}:offline", "Node mất kết nối quá 2 phút", {"Node": node.ten, "Kết nối gần nhất": as_utc(node.last_seen_at).astimezone(notify.VIETNAM).strftime("%d/%m/%Y %H:%M:%S")})
        return False
    active = list(db.scalars(select(Instance).where(Instance.node_id == node.id, Instance.trang_thai != "deleted")))
    for field, value in resources.items():
        setattr(node, field, value)
    for field in ("vcpu", "ram_mb", "disk_gb"):
        setattr(node, f"used_{field}", max(resources[f"used_{field}"], sum(getattr(instance, field) for instance in active)))
    node.trang_thai = "online"
    node.last_seen_at = datetime.now(timezone.utc)
    if node.notify_offline:
        node.notify_offline = False
        notify.enqueue(db, f"node:{node.id}:online", "Node đã kết nối trở lại", {"Node": node.ten})
    for instance in active:
        if instance.trang_thai == "provisioning":
            continue
        try:
            state = client.get_status(instance.vmid, instance.loai)
            if instance.trang_thai in {"suspended", "error"}:
                if state == "running":
                    client.stop(instance.vmid, instance.loai)
            elif state in {"running", "stopped"}:
                if instance.trang_thai == "running" and state == "stopped":
                    charge_due_hours(db, instance)
                instance.trang_thai = state
            if not instance.ip and state == "running":
                discovered_ip = client.get_ip(instance.vmid, instance.loai)
                if discovered_ip:
                    instance.ip = discovered_ip
        except ProxmoxError:
            db.add(AuditLog(action="instance.sync_pending", resource=f"instance:{instance.id}", detail="Chưa lấy được trạng thái từ node"))
    return True


def sync_nodes(db):
    for node_id in list(db.scalars(select(Node.id).order_by(Node.id))):
        lock_control_plane(db)
        node = db.get(Node, node_id, populate_existing=True)
        sync_node(db, node)
        db.commit()
