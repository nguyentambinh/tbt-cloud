# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("allocation_locks", sa.Column("id", sa.Integer(), primary_key=True))
    op.bulk_insert(sa.table("allocation_locks", sa.column("id", sa.Integer())), [{"id": 1}])
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(254), nullable=False, unique=True), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", sa.String(10), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("role IN ('user', 'admin')", name="ck_user_role"))
    op.create_table("plans", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ten", sa.String(100), nullable=False, unique=True), sa.Column("vcpu", sa.Integer(), nullable=False), sa.Column("ram_mb", sa.Integer(), nullable=False), sa.Column("disk_gb", sa.Integer(), nullable=False), sa.Column("gia_theo_gio", sa.Numeric(18, 2), nullable=False), sa.CheckConstraint("vcpu > 0 AND ram_mb > 0 AND disk_gb > 0 AND gia_theo_gio > 0", name="ck_plan_resources"))
    op.create_table("nodes", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ten", sa.String(100), nullable=False, unique=True), sa.Column("api_url", sa.String(255), nullable=False), sa.Column("token_id", sa.String(255), nullable=False), sa.Column("token_secret", sa.Text(), nullable=False), sa.Column("mesh_ip", sa.String(45), nullable=False, unique=True), sa.Column("proxmox_node", sa.String(100), nullable=False), sa.Column("storage", sa.String(100), nullable=False), sa.Column("bridge", sa.String(100), nullable=False), sa.Column("vm_template_id", sa.Integer(), nullable=True), sa.Column("lxc_template_id", sa.Integer(), nullable=True), sa.Column("vm_disk", sa.String(20), nullable=False), sa.Column("trang_thai", sa.String(10), nullable=False), sa.Column("total_vcpu", sa.Integer(), nullable=False), sa.Column("total_ram_mb", sa.Integer(), nullable=False), sa.Column("total_disk_gb", sa.Integer(), nullable=False), sa.Column("used_vcpu", sa.Integer(), nullable=False), sa.Column("used_ram_mb", sa.Integer(), nullable=False), sa.Column("used_disk_gb", sa.Integer(), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True), sa.CheckConstraint("trang_thai IN ('online', 'offline')", name="ck_node_status"), sa.CheckConstraint("total_vcpu >= 0 AND total_ram_mb >= 0 AND total_disk_gb >= 0 AND used_vcpu >= 0 AND used_ram_mb >= 0 AND used_disk_gb >= 0", name="ck_node_resources"))
    op.create_table("instances", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ten", sa.String(63), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("node_id", sa.Integer(), sa.ForeignKey("nodes.id"), nullable=False), sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False), sa.Column("vmid", sa.Integer(), nullable=False), sa.Column("loai", sa.String(3), nullable=False), sa.Column("trang_thai", sa.String(15), nullable=False), sa.Column("ip", sa.String(45), nullable=True), sa.Column("ssh_port", sa.Integer(), nullable=True, unique=True), sa.Column("vcpu", sa.Integer(), nullable=False), sa.Column("ram_mb", sa.Integer(), nullable=False), sa.Column("disk_gb", sa.Integer(), nullable=False), sa.Column("gia_theo_gio", sa.Numeric(18, 2), nullable=False), sa.Column("paid_until", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("node_id", "vmid", name="uq_instance_node_vmid"), sa.CheckConstraint("loai IN ('vm', 'lxc')", name="ck_instance_type"), sa.CheckConstraint("trang_thai IN ('provisioning', 'running', 'stopped', 'suspended', 'error', 'deleted')", name="ck_instance_status"), sa.CheckConstraint("ssh_port IS NULL OR (ssh_port >= 1024 AND ssh_port <= 65535)", name="ck_instance_port"))
    op.create_index("ix_instances_user_id", "instances", ["user_id"])
    op.create_index("ix_instances_node_id", "instances", ["node_id"])
    op.create_table("wallets", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True), sa.Column("balance", sa.Numeric(18, 2), nullable=False), sa.CheckConstraint("balance >= 0", name="ck_wallet_balance"))
    op.create_table("transactions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("wallet_id", sa.Integer(), sa.ForeignKey("wallets.id"), nullable=False), sa.Column("instance_id", sa.Integer(), sa.ForeignKey("instances.id"), nullable=True), sa.Column("amount", sa.Numeric(18, 2), nullable=False), sa.Column("kind", sa.String(10), nullable=False), sa.Column("idempotency_key", sa.String(150), nullable=False, unique=True), sa.Column("description", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("kind IN ('topup', 'usage')", name="ck_transaction_kind"))
    op.create_index("ix_transactions_wallet_id", "transactions", ["wallet_id"])
    op.create_table("audit_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True), sa.Column("action", sa.String(60), nullable=False), sa.Column("resource", sa.String(100), nullable=False), sa.Column("detail", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("transactions")
    op.drop_table("wallets")
    op.drop_table("instances")
    op.drop_table("nodes")
    op.drop_table("plans")
    op.drop_table("users")
    op.drop_table("allocation_locks")
