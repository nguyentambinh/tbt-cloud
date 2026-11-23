# Nguyễn Tâm Bình - 2324801030003
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.dependencies import current_user, tenant_user
from app.models import Payment, Transaction, User
from app.schemas import PaymentOutput, PayosCancelInput, PayosInput, TopupInput, TransactionOutput, WalletOutput
from app.services.billing import get_wallet, topup
from app.services import payos

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/balance", response_model=WalletOutput)
def balance(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return get_wallet(db, user.id)


@router.post("/topup", response_model=WalletOutput)
def virtual_topup(data: TopupInput, db: Session = Depends(get_db), user: User = Depends(tenant_user)):
    if not get_settings().virtual_topup_enabled:
        raise HTTPException(status_code=403, detail="Nạp ví ảo đang tắt. Quản trị viên cần bật chế độ mô phỏng.")
    if data.request_id.startswith("payos-"):
        raise HTTPException(status_code=422, detail="Mã yêu cầu này dành riêng cho cổng thanh toán.")
    wallet = topup(db, user.id, data.amount, data.request_id)
    db.commit()
    return wallet


@router.get("/transactions", response_model=list[TransactionOutput])
def history(offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    wallet = get_wallet(db, user.id)
    return list(db.scalars(select(Transaction).where(Transaction.wallet_id == wallet.id).order_by(Transaction.id.desc()).offset(offset).limit(limit)))


@router.post("/payos", response_model=PaymentOutput, status_code=201)
def create_payos(data: PayosInput, request: Request, db: Session = Depends(get_db), user: User = Depends(tenant_user)):
    return payos.create_payment(db, user, data.amount, origin=str(request.base_url))


@router.get("/payos", response_model=list[PaymentOutput])
def list_payos(offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    payos.require_configured()
    return list(db.scalars(select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc(), Payment.id.desc()).offset(offset).limit(limit)))


@router.get("/payos/{order_code}", response_model=PaymentOutput)
def get_payos(order_code: int = Path(gt=0, le=9223372036854775807), db: Session = Depends(get_db), user: User = Depends(current_user)):
    payos.require_configured()
    return payos.refresh_payment(db, payos.owned_payment(db, order_code, user))


@router.post("/payos/{order_code}/cancel", response_model=PaymentOutput)
def cancel_payos(order_code: int = Path(gt=0, le=9223372036854775807), data: PayosCancelInput | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    payos.require_configured()
    return payos.cancel_payment(db, payos.owned_payment(db, order_code, user, owner_only=True), (data or PayosCancelInput()).cancellationReason)
