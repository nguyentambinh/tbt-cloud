# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0002_instance_access"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("instances", sa.Column("password_encrypted", sa.Text(), nullable=True))
    op.add_column("instances", sa.Column("cloud_user", sa.String(31), nullable=True))
    op.add_column("instances", sa.Column("ssh_public_key", sa.Text(), nullable=True))
    op.add_column("instances", sa.Column("template_id", sa.Integer(), nullable=True))
    op.add_column("instances", sa.Column("ip_cidr", sa.String(18), nullable=True))
    op.add_column("instances", sa.Column("gateway", sa.String(15), nullable=True))


def downgrade():
    for column in ("gateway", "ip_cidr", "template_id", "ssh_public_key", "cloud_user", "password_encrypted"):
        op.drop_column("instances", column)
