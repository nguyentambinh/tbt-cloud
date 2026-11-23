# Nguyễn Tâm Bình - 2324801030003
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.gpu import gpu_summary

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/gpu")
def public_gpu(db: Session = Depends(get_db)):
    return gpu_summary(db)
