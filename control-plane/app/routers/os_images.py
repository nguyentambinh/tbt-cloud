# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Node, NodeOSTemplate, OSImage
from app.schemas import OSImageOutput

router = APIRouter(prefix="/os", tags=["os"])


@router.get("", response_model=list[OSImageOutput])
def list_os(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    ready = set(db.scalars(select(Node.id).where(Node.trang_thai == "online", Node.last_seen_at >= now - timedelta(seconds=120), Node.last_seen_at <= now)))
    mappings = list(db.scalars(select(NodeOSTemplate)))
    result = []
    for image in db.scalars(select(OSImage).order_by(OSImage.thu_tu, OSImage.id)):
        node_ids = {mapping.node_id for mapping in mappings if mapping.os_image_id == image.id}
        result.append({**{key: getattr(image, key) for key in OSImageOutput.model_fields if key not in {"san_sang", "so_node"}}, "san_sang": bool(node_ids & ready), "so_node": len(node_ids)})
    return result
