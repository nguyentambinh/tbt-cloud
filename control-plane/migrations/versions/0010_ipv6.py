# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0010_ipv6"
down_revision = "0009_gpu"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("ipv6_prefix", sa.String(64), nullable=True))
    with op.batch_alter_table("instances") as batch:
        batch.add_column(sa.Column("ipv6", sa.String(45), nullable=True))


def downgrade():
    with op.batch_alter_table("instances") as batch:
        batch.drop_column("ipv6")
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("ipv6_prefix")
