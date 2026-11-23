# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0008_admin"
down_revision = "0007_dang_ky_xac_nhan"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_blocked", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("users", sa.Column("token_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plans", sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("nodes", sa.Column("cpu_percent", sa.Numeric(5, 2), nullable=True))
    op.add_column("nodes", sa.Column("measured_ram_mb", sa.Integer(), nullable=True))
    op.add_column("nodes", sa.Column("measured_disk_gb", sa.Integer(), nullable=True))
    with op.batch_alter_table("transactions") as batch:
        batch.drop_constraint("ck_transaction_kind", type_="check")
        batch.create_check_constraint("ck_transaction_kind", "kind IN ('topup', 'usage', 'adjustment')")


def downgrade():
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("measured_disk_gb")
        batch.drop_column("measured_ram_mb")
        batch.drop_column("cpu_percent")
    op.execute(sa.text("UPDATE transactions SET kind=CASE WHEN amount < 0 THEN 'usage' ELSE 'topup' END WHERE kind='adjustment'"))
    with op.batch_alter_table("transactions") as batch:
        batch.drop_constraint("ck_transaction_kind", type_="check")
        batch.create_check_constraint("ck_transaction_kind", "kind IN ('topup', 'usage')")
    with op.batch_alter_table("plans") as batch:
        batch.drop_column("active")
    op.drop_index("uq_users_username_lower", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("deleted_at")
        batch.drop_column("token_version")
        batch.drop_column("is_blocked")
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)
