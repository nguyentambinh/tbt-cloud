# Nguyễn Tâm Bình - 2324801030003
from secrets import compare_digest
from typing import Literal

import ipaddress

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Instance, Node

router = APIRouter(prefix="/agent", tags=["agent"])


def require_agent(x_agent_token: str | None = Header(default=None)):
    token = get_settings().agent_token
    if token is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy chức năng này.")
    if x_agent_token is None or not compare_digest(x_agent_token.encode(), token.get_secret_value().encode()):
        raise HTTPException(status_code=401, detail="Thông tin xác thực node-agent không hợp lệ.")


@router.get("/ports", dependencies=[Depends(require_agent)])
def ports(response: Response, node: str = Query(min_length=1, max_length=100), scope: Literal["node", "all"] = "node", db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    query = select(Instance).join(Node).where(Instance.trang_thai == "running", Instance.ip.is_not(None), Instance.ssh_port.is_not(None)).order_by(Instance.ssh_port)
    if scope == "node":
        query = query.where(Node.proxmox_node == node)
    instances = db.scalars(query)
    rows = []
    for instance in instances:
        rows.append({"ssh_port": instance.ssh_port, "port": instance.ssh_port, "target_port": 3389 if instance.ket_noi == "rdp" else 22, "ip": instance.ip, "vmid": instance.vmid})
        if instance.dich_vu in {"postgres", "webapp"} and instance.app_port is not None:
            rows.append({"ssh_port": instance.app_port, "port": instance.app_port, "target_port": 5432 if instance.dich_vu == "postgres" else 80, "ip": instance.ip, "vmid": instance.vmid})
    return rows


@router.post("/ipv6", dependencies=[Depends(require_agent)])
def ipv6(response: Response, node: str = Query(min_length=1, max_length=100), prefix: str | None = Body(default=None, embed=True, max_length=64), db: Session = Depends(get_db)):
    # Agent báo prefix /64 công cộng hiện tại, nhận danh sách địa chỉ IPv6 cần định tuyến trên node
    response.headers["Cache-Control"] = "no-store"
    target = db.scalar(select(Node).where(Node.proxmox_node == node))
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy node.")
    if prefix is not None:
        try:
            network = ipaddress.IPv6Network(prefix)
        except ValueError:
            raise HTTPException(status_code=422, detail="Prefix IPv6 không hợp lệ.") from None
        if network.prefixlen != 64 or not network.is_global:
            raise HTTPException(status_code=422, detail="Prefix IPv6 phải là /64 công cộng.")
        prefix = str(network)
    if target.ipv6_prefix != prefix:
        target.ipv6_prefix = prefix
        db.commit()
    rows = db.scalars(select(Instance).where(Instance.node_id == target.id, Instance.ipv6.is_not(None), Instance.trang_thai.in_(("running", "stopped", "provisioning"))))
    return [{"vmid": row.vmid, "ipv6": row.ipv6} for row in rows]
