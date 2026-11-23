# Nguyễn Tâm Bình - 2324801030003
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import admin_user
from app.models import AuditLog, Plan, User
from app.schemas import PlanInput, PlanOutput

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanOutput])
def list_plans(dich_vu: Literal["vps", "postgres", "webapp"] | None = None, db: Session = Depends(get_db)):
    query = select(Plan).where(Plan.active.is_(True))
    if dich_vu is not None:
        query = query.where(Plan.dich_vu == dich_vu)
    return list(db.scalars(query.order_by(Plan.gia_theo_gio, Plan.id)))


@router.post("", response_model=PlanOutput, status_code=201)
def create_plan(data: PlanInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    plan = Plan(**data.model_dump())
    db.add(plan)
    try:
        db.flush()
        db.add(AuditLog(user_id=user.id, action="plan.create", resource=f"plan:{plan.id}"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên gói cấu hình đã tồn tại.") from None
    return plan
