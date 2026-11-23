# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0003_payos_notify"
down_revision = "0002_instance_access"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nodes", sa.Column("notify_offline", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("payments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("order_code", sa.BigInteger(), nullable=False, unique=True), sa.Column("amount", sa.BigInteger(), nullable=False), sa.Column("status", sa.String(10), nullable=False), sa.Column("checkout_url", sa.Text(), nullable=False), sa.Column("qr_code", sa.Text(), nullable=False), sa.Column("payment_link_id", sa.String(100), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True), sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True, unique=True), sa.CheckConstraint("status IN ('pending', 'paid', 'cancelled', 'expired', 'failed')", name="ck_payment_status"), sa.CheckConstraint("amount > 0 AND order_code > 0", name="ck_payment_amount"))
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_table("notifications", sa.Column("key", sa.String(150), primary_key=True), sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True), sa.Column("count", sa.Integer(), nullable=False), sa.Column("pending", sa.Boolean(), nullable=False), sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False), sa.Column("subject", sa.String(255), nullable=False), sa.Column("details", sa.Text(), nullable=False))


def downgrade():
    op.drop_table("notifications")
    op.drop_table("payments")
    op.drop_column("nodes", "notify_offline")
