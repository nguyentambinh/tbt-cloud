# Nguyễn Tâm Bình - 2324801030003
import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import tenant_user
from app.models import User
from app.schemas import InputModel
from app.services.advisor import suggest

router = APIRouter(prefix="/ai", tags=["ai"])
MAX_FILE = 8 * 1024 * 1024


class AdviceInput(InputModel):
    mo_ta: str = Field(default="", max_length=4000)
    tep_ten: str | None = Field(default=None, max_length=200)
    tep_base64: str | None = Field(default=None, max_length=MAX_FILE * 4 // 3 + 8)


@router.post("/goi-y")
def advise(data: AdviceInput, db: Session = Depends(get_db), user: User = Depends(tenant_user)):
    content = None
    if data.tep_base64:
        if not data.tep_ten:
            raise HTTPException(status_code=422, detail="Thiếu tên tệp đính kèm.")
        try:
            content = base64.b64decode(data.tep_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=422, detail="Tệp đính kèm bị lỗi khi tải lên. Hãy chọn lại tệp.") from None
        if len(content) > MAX_FILE:
            raise HTTPException(status_code=413, detail="Tệp lớn hơn 8 MB. Hãy chọn tệp nhỏ hơn.")
    return suggest(db, user, data.mo_ta, data.tep_ten, content)
