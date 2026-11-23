# Nguyễn Tâm Bình - 2324801030003
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.schemas import InputModel, PlanInput


class UserStateInput(InputModel):
    is_blocked: bool


class RoleInput(InputModel):
    role: Literal["user", "admin"]


class AdjustmentInput(InputModel):
    amount: Decimal = Field(ge=-100000000, le=100000000, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=3, max_length=200)
    request_id: str = Field(pattern=r"^[A-Za-z0-9-]{8,80}$")

    @field_validator("amount")
    @classmethod
    def nonzero_amount(cls, value):
        if not value:
            raise ValueError("Số tiền điều chỉnh phải khác không.")
        return value

    @field_validator("reason")
    @classmethod
    def reason_required(cls, value):
        if len(value.strip()) < 3 or any(ord(c) < 32 for c in value):
            raise ValueError("Cần ghi lý do điều chỉnh số dư.")
        return value.strip()


class AdminPlanInput(PlanInput):
    active: bool = True


class NodeEditInput(InputModel):
    ten: str = Field(min_length=1, max_length=100, pattern=r"^\S(?:[^\r\n]*\S)?$")
    proxmox_node: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.-]{0,99}$")
    storage: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,99}$")
    bridge: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,99}$")


class RestoreInput(InputModel):
    confirmation: Literal["KHOI PHUC"]
