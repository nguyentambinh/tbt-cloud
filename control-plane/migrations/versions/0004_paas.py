# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0004_paas"
down_revision = "0003_payos_notify"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nodes", sa.Column("paas_template_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("instances") as batch:
        batch.add_column(sa.Column("dich_vu", sa.String(10), nullable=False, server_default="vps"))
        batch.add_column(sa.Column("app_port", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("app_config_encrypted", sa.Text(), nullable=True))
        batch.create_unique_constraint("uq_instances_app_port", ["app_port"])
        batch.create_check_constraint("ck_instance_service", "dich_vu IN ('vps', 'postgres', 'webapp')")
        batch.create_check_constraint("ck_instance_app_port", "app_port IS NULL OR (app_port >= 1024 AND app_port <= 65535)")


def downgrade():
    with op.batch_alter_table("instances") as batch:
        batch.drop_constraint("ck_instance_app_port", type_="check")
        batch.drop_constraint("ck_instance_service", type_="check")
        batch.drop_constraint("uq_instances_app_port", type_="unique")
        batch.drop_column("app_config_encrypted")
        batch.drop_column("app_port")
        batch.drop_column("dich_vu")
    op.drop_column("nodes", "paas_template_id")
