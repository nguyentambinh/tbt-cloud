# Nguyễn Tâm Bình - 2324801030003
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from ipaddress import ip_address, ip_interface
from typing import Literal
from urllib.parse import urlsplit

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.serialization import load_ssh_public_key
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegistrationEmail(InputModel):
    email: EmailStr = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()


class RegisterInput(RegistrationEmail):
    ho_ten: str = Field(min_length=2, max_length=80)
    username: str = Field(min_length=3, max_length=30)
    password: SecretStr = Field(min_length=8, max_length=128)
    password_confirm: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("ho_ten", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return unicodedata.normalize("NFC", value).strip() if isinstance(value, str) else value

    @field_validator("ho_ten")
    @classmethod
    def validate_name(cls, value):
        if not all(character.isalpha() or character == " " for character in value):
            raise ValueError("Họ và tên chỉ gồm chữ và khoảng trắng.")
        return value

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        return value.lower() if isinstance(value, str) else value

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):
        if not re.fullmatch(r"[a-z][a-z0-9._]{2,29}", value):
            raise ValueError("Tên tài khoản cần 3 - 30 ký tự, bắt đầu bằng chữ, chỉ gồm a-z, 0-9, dấu chấm và gạch dưới.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        password = value.get_secret_value()
        if any(character.isspace() for character in password) or not (any(character.isupper() for character in password) and any(character.islower() for character in password) and any(character in "0123456789" for character in password) and any(not character.isalnum() and not character.isspace() for character in password)):
            raise ValueError("Mật khẩu cần chữ hoa, chữ thường, số, ký tự đặc biệt và không có khoảng trắng.")
        return value

    @model_validator(mode="after")
    def confirm_password(self):
        if self.password.get_secret_value() != self.password_confirm.get_secret_value():
            raise ValueError("Xác nhận mật khẩu chưa khớp.")
        return self


class RegistrationVerify(RegistrationEmail):
    code: SecretStr = Field(min_length=6, max_length=6)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value):
        if not re.fullmatch(r"[0-9]{6}", value.get_secret_value()):
            raise ValueError("Mã xác nhận gồm 6 chữ số.")
        return value


class RegistrationOutput(BaseModel):
    email_masked: str
    detail: str = "Đã gửi mã xác nhận. Vui lòng kiểm tra hộp thư."
    resend_after: int = 60
    expires_in: int = 600


class LoginInput(InputModel):
    # Đăng nhập nhận email hoặc tên đăng nhập ngắn của tài khoản có sẵn; quy tắc chặt chỉ áp cho đăng ký
    email: str = Field(min_length=1, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_login(cls, value):
        return value.strip().lower()


class UserOutput(OutputModel):
    id: int
    email: str
    ho_ten: str | None = None
    username: str | None = None
    role: str
    is_blocked: bool = False
    created_at: datetime


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PlanInput(InputModel):
    ten: str = Field(min_length=1, max_length=100)
    dich_vu: Literal["vps", "postgres", "webapp"] = "vps"
    mo_ta: str = Field(default="", max_length=160)
    vcpu: int = Field(gt=0, le=256)
    ram_mb: int = Field(ge=128, le=1048576)
    disk_gb: int = Field(gt=0, le=100000)
    gia_theo_gio: Decimal = Field(gt=0, le=100000000, max_digits=18, decimal_places=2)
    gpu: int = Field(default=0, ge=0, le=8)

    @model_validator(mode="after")
    def validate_service_disk(self):
        if self.dich_vu != "vps" and self.disk_gb < 10:
            raise ValueError("Gói dịch vụ PostgreSQL và ứng dụng web cần ít nhất 10 GB ổ đĩa.")
        return self


class PlanOutput(PlanInput, OutputModel):
    id: int


class NodeInput(InputModel):
    ten: str = Field(min_length=1, max_length=100)
    api_url: str = Field(max_length=255)
    token_id: str = Field(pattern=r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+![A-Za-z0-9._-]+$", max_length=255)
    token_secret: SecretStr = Field(min_length=1, max_length=255)
    mesh_ip: str
    proxmox_node: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.-]{0,99}$")
    storage: str = Field(default="local-lvm", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,99}$")
    bridge: str = Field(default="vmbr0", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,99}$")
    vm_template_id: int | None = Field(default=None, ge=100, le=999999999)
    lxc_template_id: int | None = Field(default=None, ge=100, le=999999999)
    paas_template_id: int | None = Field(default=None, ge=100, le=999999999)
    vm_disk: str = Field(default="scsi0", pattern=r"^(scsi|virtio|sata)[0-9]+$")

    @field_validator("api_url")
    @classmethod
    def validate_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("URL Proxmox phải có dạng https://host:8006.")
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("Cổng Proxmox không hợp lệ.")
        return value.rstrip("/")

    @field_validator("mesh_ip")
    @classmethod
    def validate_mesh(cls, value):
        return str(ip_address(value))


class OSTemplateInput(InputModel):
    os_ma: str = Field(pattern=r"^[a-z0-9]{1,30}$")
    template_id: int = Field(strict=True, ge=100, le=999999999)


class OSTemplateOutput(OSTemplateInput, OutputModel):
    pass


class OSImageOutput(OutputModel):
    id: int
    ma: str
    ten: str
    ho: str
    min_ram_mb: int
    min_disk_gb: int
    ket_noi: str
    thu_tu: int
    chi_gpu: bool = False
    san_sang: bool
    so_node: int


class NodeOutput(OutputModel):
    id: int
    ten: str
    api_url: str
    mesh_ip: str
    proxmox_node: str
    storage: str
    bridge: str
    vm_template_id: int | None
    lxc_template_id: int | None
    paas_template_id: int | None
    vm_disk: str
    trang_thai: str
    total_vcpu: int
    total_ram_mb: int
    total_disk_gb: int
    used_vcpu: int
    used_ram_mb: int
    used_disk_gb: int
    last_seen_at: datetime | None
    os_templates: list[OSTemplateOutput] = Field(default_factory=list)


class NodeMapOutput(OutputModel):
    id: int
    ten: str
    proxmox_node: str
    online: bool
    last_seen_at: datetime | None
    total_vcpu: int
    total_ram_mb: int
    total_disk_gb: int
    used_vcpu: int
    used_ram_mb: int
    used_disk_gb: int


class InstanceInput(InputModel):
    ten: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
    plan_id: int = Field(gt=0)
    loai: Literal["vm", "lxc"] = "vm"
    dich_vu: Literal["vps", "postgres", "webapp"] = "vps"
    os_ma: str | None = Field(default=None, pattern=r"^[a-z0-9]{1,30}$")
    repo_url: str | None = Field(default=None, max_length=300)
    branch: str = Field(default="main", pattern=r"^[A-Za-z0-9._/-]{1,100}$")
    cloud_user: str | None = Field(default=None, pattern=r"^[a-z_][a-z0-9_-]{0,30}$")
    ssh_public_key: str | None = Field(default=None, min_length=30, max_length=8192)
    ip_cidr: str | None = None
    gateway: str | None = None
    strategy: Literal["best-fit", "least-loaded"] | None = None

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, value):
        if value is None:
            return value
        if not re.fullmatch(r"https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", value) or re.search(r"%(?![0-9A-Fa-f]{2})", value):
            raise ValueError("Kho Git phải là địa chỉ HTTPS hợp lệ.")
        parsed = urlsplit(value)
        if not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.port == 0:
            raise ValueError("Kho Git phải dùng HTTPS và không chứa tài khoản hay mật khẩu.")
        return value

    @field_validator("ssh_public_key")
    @classmethod
    def validate_ssh_key(cls, value):
        if value is None:
            return value
        if "\n" in value or "\r" in value:
            raise ValueError("Chỉ chấp nhận một khóa SSH công khai.")
        try:
            load_ssh_public_key(value.encode())
        except (ValueError, TypeError, UnsupportedAlgorithm):
            raise ValueError("Khóa SSH công khai không hợp lệ.") from None
        return value

    @model_validator(mode="after")
    def validate_network(self):
        if self.dich_vu != "vps" or self.loai != "vm":
            if "os_ma" in self.model_fields_set:
                raise HTTPException(status_code=422, detail="Chỉ chọn hệ điều hành cho VPS loại VM. LXC dùng Debian 13; dịch vụ PaaS dùng hệ điều hành có sẵn.")
        else:
            self.os_ma = self.os_ma or "debian13"
        if self.os_ma in {"winserver2022", "windows11"}:
            self.cloud_user = "tbtadmin"
            self.ssh_public_key = None
        else:
            self.cloud_user = self.cloud_user or "root"
            if self.loai == "lxc" and not self.ssh_public_key:
                raise HTTPException(status_code=422, detail="Container LXC đăng nhập bằng khóa SSH, hãy nhập khóa SSH công khai.")
        if self.dich_vu != "vps" and self.loai != "vm":
            raise ValueError("Dịch vụ PostgreSQL và ứng dụng web cần dùng máy ảo VM.")
        if self.dich_vu == "webapp" and not self.repo_url:
            raise ValueError("Hãy nhập địa chỉ HTTPS của kho Git công khai.")
        if self.gateway and not self.ip_cidr:
            raise ValueError("Cần địa chỉ IP tĩnh khi khai báo gateway.")
        if self.ip_cidr:
            interface = ip_interface(self.ip_cidr)
            if interface.version != 4 or "/" not in self.ip_cidr:
                raise ValueError("IP tĩnh phải là địa chỉ IPv4/CIDR.")
            self.ip_cidr = str(interface)
            if self.gateway and ip_address(self.gateway) not in interface.network:
                raise ValueError("Gateway phải thuộc cùng mạng với instance.")
        if self.loai == "lxc" and self.cloud_user != "root":
            raise ValueError("Template LXC sử dụng tài khoản root; hãy đặt cloud_user=root.")
        return self


class InstanceOutput(OutputModel):
    id: int
    ten: str
    user_id: int
    node_id: int
    plan_id: int
    vmid: int
    loai: str
    dich_vu: str
    os_image_id: int | None
    ket_noi: str
    app_port: int | None
    trang_thai: str
    ip: str | None
    ipv6: str | None = None
    ssh_port: int | None
    vcpu: int
    ram_mb: int
    disk_gb: int
    gia_theo_gio: Decimal
    paid_until: datetime | None
    created_at: datetime


class TopupInput(InputModel):
    amount: Decimal = Field(gt=0, le=10000000, max_digits=12, decimal_places=2)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")


class PayosInput(InputModel):
    amount: int = Field(strict=True, gt=0)


class PayosCancelInput(InputModel):
    cancellationReason: str = Field(default="Khách hàng hủy đơn nạp tiền", min_length=1, max_length=255)


class PaymentOutput(OutputModel):
    order_code: int
    amount: int
    checkout_url: str
    qr_code: str
    status: str


class PasswordInput(InputModel):
    password: SecretStr | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if value is not None and any(ord(c) < 32 or ord(c) == 127 for c in value.get_secret_value()):
            raise ValueError("Mật khẩu không được chứa ký tự điều khiển.")
        return value


class ReinstallInput(InputModel):
    os_ma: str | None = Field(default=None, pattern=r"^[a-z0-9]{1,30}$")
    plan_id: int | None = Field(default=None, gt=0)


class CredentialsOutput(OutputModel):
    username: str
    password: str | None
    ssh_host: str
    ipv6: str | None = None
    ssh_port: int | None
    ket_noi: str
    host: str
    port: int | None
    dia_chi: str


class InstanceDetailOutput(InstanceOutput):
    ten_he_dieu_hanh: str
    gpu: str | None = None
    node_ten: str
    tong_chi_phi: Decimal
    ngay_tao: datetime


class StatsPoint(OutputModel):
    time: float
    cpu: float | None
    mem_used: float | None
    mem_total: float | None
    netin: float | None
    netout: float | None
    diskread: float | None
    diskwrite: float | None


class StatusOutput(OutputModel):
    cpu: float
    mem: int
    uptime: int


class WalletOutput(OutputModel):
    balance: Decimal


class TransactionOutput(OutputModel):
    id: int
    instance_id: int | None
    amount: Decimal
    kind: str
    description: str
    created_at: datetime


class AuditOutput(OutputModel):
    id: int
    user_id: int | None
    action: str
    resource: str
    detail: str
    created_at: datetime


class NodeGPUInput(InputModel):
    pci_id: str = Field(pattern=r"^([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}(\.[0-7])?|[a-z][a-z0-9_-]{1,31})$")
    ten: str = Field(min_length=1, max_length=120)
    vram_mb: int = Field(gt=0, le=1048576)


class NodeGPUOutput(NodeGPUInput, OutputModel):
    id: int
    dang_dung: bool = False
