# Nguyễn Tâm Bình - 2324801030003
from sqlalchemy import select

from app.models import Instance, NodeGPU

ACTIVE = ("deleted", "error")


def busy_gpu_ids(db):
    return set(db.scalars(select(Instance.gpu_id).where(Instance.gpu_id.is_not(None), Instance.trang_thai.not_in(ACTIVE))))


def free_gpus(db, node, busy=None):
    busy = busy_gpu_ids(db) if busy is None else busy
    return [gpu for gpu in sorted(node.gpus, key=lambda item: item.id) if gpu.id not in busy]


def gpu_summary(db):
    gpus = list(db.scalars(select(NodeGPU).order_by(NodeGPU.id)))
    busy = busy_gpu_ids(db)
    names = sorted({f"{gpu.ten} {gpu.vram_mb // 1024} GB" for gpu in gpus})
    return {"tong": len(gpus), "ranh": sum(gpu.id not in busy for gpu in gpus), "loai": names}
