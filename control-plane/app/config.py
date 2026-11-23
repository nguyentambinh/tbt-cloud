# Nguyễn Tâm Bình - 2324801030003
from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True)

    app_name: str = "Distributed Cloud Control API"
    web_dir: str = ""
    database_url: str
    jwt_secret: SecretStr
    fernet_key: SecretStr
    jwt_expire_minutes: int = Field(default=60, ge=1, le=1440)
    jwt_issuer: str = "distributed-cloud"
    ssh_port_start: int = Field(default=22000, ge=1024, le=65535)
    ssh_port_end: int = Field(default=22999, ge=1024, le=65535)
    app_port_start: int = Field(default=23000, ge=1024, le=65535)
    app_port_end: int = Field(default=23999, ge=1024, le=65535)
    gateway_host: str = "localhost"
    scheduler_strategy: str = "best-fit"
    proxmox_timeout: float = Field(default=10, gt=0, le=60)
    disk_overcommit: float = Field(default=1.5, ge=1, le=4)
    disk_reserve_gb: int = Field(default=10, ge=0, le=1000)
    gemini_api_key: SecretStr | None = None
    gemini_model: str = Field(default="gemini-3.5-flash-lite", pattern=r"^[a-z0-9.-]{3,60}$")
    ai_daily_limit: int = Field(default=30, ge=1, le=1000)
    gemini_fallback_models: str = "gemini-2.5-flash"
    gemini_retry_seconds: float = Field(default=1.5, ge=0, le=10)
    gemini_timeout: float = Field(default=20, gt=0, le=120)
    gemini_budget: float = Field(default=30, gt=0, le=300)
    anthropic_api_key: SecretStr | None = None
    claude_model: str = Field(default="claude-sonnet-5-5", pattern=r"^claude-[a-z0-9.-]{3,60}$")
    cloud_init_vendor: str = Field(default="local:snippets/tbt-vendor.yaml", pattern=r"^([A-Za-z0-9_.-]+:snippets/[A-Za-z0-9_.-]+)?$")  # rỗng: không gắn vendor-data
    proxmox_task_timeout: float = Field(default=180, gt=0, le=600)
    proxmox_verify_ssl: str = "true"  # "true", "false" hoặc đường dẫn tệp CA của node
    workers_enabled: bool = False
    cors_origins: list[str] = []
    virtual_topup_enabled: bool = False
    agent_token: SecretStr | None = None
    payos_client_id: SecretStr | None = None
    payos_api_key: SecretStr | None = None
    payos_checksum_key: SecretStr | None = None
    payos_return_url: str = ""
    payos_cancel_url: str = ""
    payos_min_amount: int = Field(default=10000, gt=0)
    payos_max_amount: int = Field(default=5000000, gt=0)
    notify_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password_file: str = ""
    notify_to: str = ""
    notify_dedup_minutes: int = Field(default=30, ge=1)
    backup_dir: str = "/opt/cloud/backups"
    backup_keep: int = Field(default=10, ge=2, le=100)
    backup_timeout: int = Field(default=120, ge=10, le=600)

    @field_validator("payos_min_amount", "payos_max_amount", "notify_enabled", "smtp_host", "smtp_port", "notify_dedup_minutes", mode="before")
    @classmethod
    def empty_uses_default(cls, value, info):
        return cls.model_fields[info.field_name].default if value == "" else value

    @model_validator(mode="after")
    def validate_settings(self):
        if len(self.jwt_secret.get_secret_value().encode()) < 32 or self.jwt_secret.get_secret_value().lower().startswith(("replace-", "change-")):
            raise ValueError("JWT_SECRET phải có ít nhất 32 byte.")
        Fernet(self.fernet_key.get_secret_value().encode())
        if self.agent_token is not None and len(self.agent_token.get_secret_value().encode()) < 32:
            raise ValueError("AGENT_TOKEN phải có ít nhất 32 byte khi được cấu hình.")
        if self.ssh_port_start > self.ssh_port_end:
            raise ValueError("Khoảng cổng SSH không hợp lệ.")
        if self.app_port_start > self.app_port_end:
            raise ValueError("Khoảng cổng dịch vụ không hợp lệ.")
        if self.scheduler_strategy not in {"best-fit", "least-loaded"}:
            raise ValueError("Chiến lược điều phối không hợp lệ.")
        if self.payos_min_amount > self.payos_max_amount:
            raise ValueError("Khoảng tiền nạp payOS không hợp lệ.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
