# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, false, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class AllocationLock(Base):
    __tablename__ = "allocation_locks"
    id: Mapped[int] = mapped_column(primary_key=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="ck_user_role"), Index("uq_users_username_lower", text("lower(username)"), unique=True))
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    ho_ten: Mapped[str | None] = mapped_column(String(80))
    username: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), default="user")
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    thong_bao_da_doc: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    wallet: Mapped["Wallet"] = relationship(back_populates="user", uselist=False)


class PendingRegistration(Base):
    __tablename__ = "pending_registrations"
    __table_args__ = (CheckConstraint("failed_attempts >= 0 AND failed_attempts <= 5", name="ck_registration_attempts"), CheckConstraint("send_count >= 1 AND send_count <= 5", name="ck_registration_send_count"))
    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    ho_ten: Mapped[str] = mapped_column(String(80))
    username: Mapped[str] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    send_count: Mapped[int] = mapped_column(Integer)


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (CheckConstraint("vcpu > 0 AND ram_mb > 0 AND disk_gb > 0 AND gia_theo_gio > 0", name="ck_plan_resources"), CheckConstraint("dich_vu IN ('vps', 'postgres', 'webapp')", name="ck_plan_service"), CheckConstraint("gpu >= 0 AND gpu <= 8", name="ck_plan_gpu"))
    id: Mapped[int] = mapped_column(primary_key=True)
    ten: Mapped[str] = mapped_column(String(100), unique=True)
    dich_vu: Mapped[str] = mapped_column(String(10), default="vps", server_default="vps")
    mo_ta: Mapped[str] = mapped_column(String(160), default="", server_default="")
    vcpu: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    disk_gb: Mapped[int] = mapped_column(Integer)
    gia_theo_gio: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    gpu: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Node(Base):
    __tablename__ = "nodes"
    __table_args__ = (CheckConstraint("trang_thai IN ('online', 'offline')", name="ck_node_status"), CheckConstraint("total_vcpu >= 0 AND total_ram_mb >= 0 AND total_disk_gb >= 0 AND used_vcpu >= 0 AND used_ram_mb >= 0 AND used_disk_gb >= 0", name="ck_node_resources"))
    id: Mapped[int] = mapped_column(primary_key=True)
    ten: Mapped[str] = mapped_column(String(100), unique=True)
    api_url: Mapped[str] = mapped_column(String(255))
    token_id: Mapped[str] = mapped_column(String(255))
    token_secret: Mapped[str] = mapped_column(Text)
    mesh_ip: Mapped[str] = mapped_column(String(45), unique=True)
    proxmox_node: Mapped[str] = mapped_column(String(100))
    storage: Mapped[str] = mapped_column(String(100), default="local-lvm")
    bridge: Mapped[str] = mapped_column(String(100), default="vmbr0")
    vm_template_id: Mapped[int | None] = mapped_column(Integer)
    lxc_template_id: Mapped[int | None] = mapped_column(Integer)
    paas_template_id: Mapped[int | None] = mapped_column(Integer)
    vm_disk: Mapped[str] = mapped_column(String(20), default="scsi0")
    trang_thai: Mapped[str] = mapped_column(String(10), default="offline")
    total_vcpu: Mapped[int] = mapped_column(Integer, default=0)
    total_ram_mb: Mapped[int] = mapped_column(Integer, default=0)
    total_disk_gb: Mapped[int] = mapped_column(Integer, default=0)
    used_vcpu: Mapped[int] = mapped_column(Integer, default=0)
    used_ram_mb: Mapped[int] = mapped_column(Integer, default=0)
    used_disk_gb: Mapped[int] = mapped_column(Integer, default=0)
    cpu_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    measured_ram_mb: Mapped[int | None] = mapped_column(Integer)
    measured_disk_gb: Mapped[int | None] = mapped_column(Integer)
    ipv6_prefix: Mapped[str | None] = mapped_column(String(64))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notify_offline: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    os_templates: Mapped[list["NodeOSTemplate"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    gpus: Mapped[list["NodeGPU"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class OSImage(Base):
    __tablename__ = "os_images"
    __table_args__ = (CheckConstraint("ho IN ('linux', 'windows')", name="ck_os_family"), CheckConstraint("ket_noi IN ('ssh', 'rdp')", name="ck_os_connection"), CheckConstraint("min_ram_mb > 0 AND min_disk_gb > 0", name="ck_os_resources"))
    id: Mapped[int] = mapped_column(primary_key=True)
    ma: Mapped[str] = mapped_column(String(30), unique=True)
    ten: Mapped[str] = mapped_column(String(100))
    ho: Mapped[str] = mapped_column(String(10))
    min_ram_mb: Mapped[int] = mapped_column(Integer)
    min_disk_gb: Mapped[int] = mapped_column(Integer)
    ket_noi: Mapped[str] = mapped_column(String(3))
    thu_tu: Mapped[int] = mapped_column(Integer)
    chi_gpu: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class NodeGPU(Base):
    __tablename__ = "node_gpus"
    __table_args__ = (UniqueConstraint("node_id", "pci_id", name="uq_node_gpu_pci"), CheckConstraint("vram_mb > 0", name="ck_node_gpu_vram"))
    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    pci_id: Mapped[str] = mapped_column(String(32))
    ten: Mapped[str] = mapped_column(String(120))
    vram_mb: Mapped[int] = mapped_column(Integer)


class NodeOSTemplate(Base):
    __tablename__ = "node_os_templates"
    __table_args__ = (UniqueConstraint("node_id", "os_image_id", name="uq_node_os_template"), CheckConstraint("template_id >= 100 AND template_id <= 999999999", name="ck_os_template_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    os_image_id: Mapped[int] = mapped_column(ForeignKey("os_images.id"))
    template_id: Mapped[int] = mapped_column(Integer)
    os_image: Mapped[OSImage] = relationship(lazy="selectin")

    @property
    def os_ma(self):
        return self.os_image.ma


class Instance(Base):
    __tablename__ = "instances"
    __table_args__ = (UniqueConstraint("node_id", "vmid", name="uq_instance_node_vmid"), CheckConstraint("loai IN ('vm', 'lxc')", name="ck_instance_type"), CheckConstraint("trang_thai IN ('provisioning', 'running', 'stopped', 'suspended', 'error', 'deleted')", name="ck_instance_status"), CheckConstraint("ssh_port IS NULL OR (ssh_port >= 1024 AND ssh_port <= 65535)", name="ck_instance_port"), CheckConstraint("dich_vu IN ('vps', 'postgres', 'webapp')", name="ck_instance_service"), CheckConstraint("app_port IS NULL OR (app_port >= 1024 AND app_port <= 65535)", name="ck_instance_app_port"), Index("uq_instance_gpu_active", "gpu_id", unique=True, postgresql_where=text("gpu_id IS NOT NULL AND trang_thai NOT IN ('deleted', 'error')"), sqlite_where=text("gpu_id IS NOT NULL AND trang_thai NOT IN ('deleted', 'error')")))
    id: Mapped[int] = mapped_column(primary_key=True)
    ten: Mapped[str] = mapped_column(String(63))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    os_image_id: Mapped[int | None] = mapped_column(ForeignKey("os_images.id"))
    gpu_id: Mapped[int | None] = mapped_column(ForeignKey("node_gpus.id"))
    vmid: Mapped[int] = mapped_column(Integer)
    loai: Mapped[str] = mapped_column(String(3))
    dich_vu: Mapped[str] = mapped_column(String(10), default="vps", server_default="vps")
    app_port: Mapped[int | None] = mapped_column(Integer, unique=True)
    app_config_encrypted: Mapped[str | None] = mapped_column(Text)
    trang_thai: Mapped[str] = mapped_column(String(15), default="provisioning")
    ip: Mapped[str | None] = mapped_column(String(45))
    ipv6: Mapped[str | None] = mapped_column(String(45))
    ssh_port: Mapped[int | None] = mapped_column(Integer, unique=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    cloud_user: Mapped[str | None] = mapped_column(String(31))
    ssh_public_key: Mapped[str | None] = mapped_column(Text)
    template_id: Mapped[int | None] = mapped_column(Integer)
    ip_cidr: Mapped[str | None] = mapped_column(String(18))
    gateway: Mapped[str | None] = mapped_column(String(15))
    vcpu: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    disk_gb: Mapped[int] = mapped_column(Integer)
    gia_theo_gio: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    paid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    node: Mapped[Node] = relationship()
    plan: Mapped[Plan] = relationship()
    os_image: Mapped[OSImage | None] = relationship(lazy="selectin")
    gpu: Mapped[NodeGPU | None] = relationship(lazy="selectin")

    @property
    def ket_noi(self):
        return self.os_image.ket_noi if self.os_image else "ssh"


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (CheckConstraint("balance >= 0", name="ck_wallet_balance"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    user: Mapped[User] = relationship(back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (CheckConstraint("kind IN ('topup', 'usage', 'adjustment')", name="ck_transaction_kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"), index=True)
    instance_id: Mapped[int | None] = mapped_column(ForeignKey("instances.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    kind: Mapped[str] = mapped_column(String(10))
    idempotency_key: Mapped[str] = mapped_column(String(150), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(60))
    resource: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("status IN ('pending', 'paid', 'cancelled', 'expired', 'failed')", name="ck_payment_status"), CheckConstraint("amount > 0 AND order_code > 0", name="ck_payment_amount"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_code: Mapped[int] = mapped_column(BigInteger, unique=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    checkout_url: Mapped[str] = mapped_column(Text)
    qr_code: Mapped[str] = mapped_column(Text)
    payment_link_id: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), unique=True)


class Notification(Base):
    __tablename__ = "notifications"
    key: Mapped[str] = mapped_column(String(150), primary_key=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0)
    pending: Mapped[bool] = mapped_column(Boolean, default=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    subject: Mapped[str] = mapped_column(String(255))
    details: Mapped[str] = mapped_column(Text)
