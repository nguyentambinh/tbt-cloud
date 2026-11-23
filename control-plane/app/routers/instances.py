# Nguyễn Tâm Bình - 2324801030003
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, WebSocket
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import current_user, tenant_user
from app.models import AuditLog, Instance, User
from app.schemas import AuditOutput, CredentialsOutput, InstanceDetailOutput, InstanceInput, InstanceOutput, PasswordInput, ReinstallInput, StatsPoint, StatusOutput
from app.services.instances import ProxmoxClient, create_instance, credentials, instance_detail, maintain_instance, owned_instance, perform_action, reinstall_options, service_info
from app.services.console import open_console

router = APIRouter(prefix="/instances", tags=["instances"])


@router.websocket("/{instance_id}/console")
async def console(websocket: WebSocket, instance_id: int, token: str | None = None, db: Session = Depends(get_db)):
    await open_console(websocket, db, instance_id, token)


@router.get("", response_model=list[InstanceOutput])
def list_instances(offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Instance).where(Instance.trang_thai != "deleted").order_by(Instance.id).offset(offset).limit(limit)
    if user.role != "admin":
        query = query.where(Instance.user_id == user.id)
    return list(db.scalars(query))


@router.post("", response_model=InstanceOutput, status_code=201)
def create(data: InstanceInput, db: Session = Depends(get_db), user: User = Depends(tenant_user)):
    return create_instance(db, user, data)


@router.get("/{instance_id}", response_model=InstanceOutput)
def detail(instance_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return owned_instance(db, instance_id, user)


@router.get("/{instance_id}/detail", response_model=InstanceDetailOutput)
def full_detail(instance_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return instance_detail(db, owned_instance(db, instance_id, user))


@router.get("/{instance_id}/credentials", response_model=CredentialsOutput)
def get_credentials(instance_id: int, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return credentials(owned_instance(db, instance_id, user))


@router.get("/{instance_id}/service")
def get_service(instance_id: int, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return service_info(owned_instance(db, instance_id, user))


@router.post("/{instance_id}/password", response_model=CredentialsOutput)
def change_password(instance_id: int, response: Response, data: PasswordInput | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return credentials(maintain_instance(db, user, instance_id, "password", data.password.get_secret_value() if data and data.password else None))


@router.get("/{instance_id}/reinstall-options")
def reinstall_choices(instance_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return reinstall_options(db, user, instance_id)


@router.post("/{instance_id}/reinstall", response_model=InstanceOutput)
def reinstall(instance_id: int, data: ReinstallInput | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return maintain_instance(db, user, instance_id, "reinstall", os_ma=data.os_ma if data else None, plan_id=data.plan_id if data else None)


@router.get("/{instance_id}/stats", response_model=list[StatsPoint])
def stats(instance_id: int, timeframe: Literal["hour", "day", "week"] = "hour", db: Session = Depends(get_db), user: User = Depends(current_user)):
    instance = owned_instance(db, instance_id, user)
    return ProxmoxClient(instance.node).get_stats(instance.vmid, instance.loai, timeframe)


@router.get("/{instance_id}/status-now", response_model=StatusOutput)
def status_now(instance_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    instance = owned_instance(db, instance_id, user)
    return ProxmoxClient(instance.node).get_status_now(instance.vmid, instance.loai)


@router.get("/{instance_id}/logs", response_model=list[AuditOutput])
def logs(instance_id: int, offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_instance(db, instance_id, user)
    return list(db.scalars(select(AuditLog).where(AuditLog.resource == f"instance:{instance_id}").order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)))


@router.post("/{instance_id}/start", response_model=InstanceOutput)
def start(instance_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return perform_action(db, user, instance_id, "start")


@router.post("/{instance_id}/stop", response_model=InstanceOutput)
def stop(instance_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return perform_action(db, user, instance_id, "stop")


@router.post("/{instance_id}/reboot", response_model=InstanceOutput)
def reboot(instance_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return perform_action(db, user, instance_id, "reboot")


@router.delete("/{instance_id}", response_model=InstanceOutput)
def delete(instance_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return perform_action(db, user, instance_id, "delete")
