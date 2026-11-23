# Nguyễn Tâm Bình - 2324801030003
from fastapi import HTTPException
from sqlalchemy import select

from app.config import get_settings
from app.db import lock_control_plane
from app.models import Instance


def allocate_ssh_port(db, instance, start=None, end=None):
    settings = get_settings()
    start = settings.ssh_port_start if start is None else start
    end = settings.ssh_port_end if end is None else end
    if not 1024 <= start <= end <= 65535:
        raise ValueError("Khoảng cổng SSH không hợp lệ.")
    lock_control_plane(db)
    if instance.ssh_port is not None:
        return instance.ssh_port
    used = set(db.scalars(select(Instance.ssh_port).where(Instance.ssh_port.is_not(None)))) | set(db.scalars(select(Instance.app_port).where(Instance.app_port.is_not(None))))
    port = next((candidate for candidate in range(start, end + 1) if candidate not in used), None)
    if port is None:
        raise HTTPException(status_code=503, detail="Gateway đã hết cổng SSH khả dụng.")
    instance.ssh_port = port
    db.flush()
    return port


def release_ssh_port(db, instance):
    lock_control_plane(db)
    if instance.trang_thai != "deleted":
        raise ValueError("Chỉ thu hồi cổng khi instance đã được xóa.")
    instance.ssh_port = None
    db.flush()


def allocate_app_port(db, instance, start=None, end=None):
    if instance.dich_vu == "vps":
        return None
    settings = get_settings()
    start = settings.app_port_start if start is None else start
    end = settings.app_port_end if end is None else end
    if not 1024 <= start <= end <= 65535:
        raise ValueError("Khoảng cổng dịch vụ không hợp lệ.")
    lock_control_plane(db)
    if instance.app_port is not None:
        return instance.app_port
    used = set(db.scalars(select(Instance.app_port).where(Instance.app_port.is_not(None)))) | set(db.scalars(select(Instance.ssh_port).where(Instance.ssh_port.is_not(None))))
    port = next((candidate for candidate in range(start, end + 1) if candidate not in used), None)
    if port is None:
        raise HTTPException(status_code=503, detail="Gateway đã hết cổng dịch vụ khả dụng.")
    instance.app_port = port
    db.flush()
    return port


def release_app_port(db, instance):
    lock_control_plane(db)
    if instance.trang_thai != "deleted":
        raise ValueError("Chỉ thu hồi cổng khi instance đã được xóa.")
    instance.app_port = None
    db.flush()
