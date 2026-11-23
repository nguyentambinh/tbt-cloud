# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0011_thong_bao"
down_revision = "0010_ipv6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("thong_bao_da_doc", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("users", "thong_bao_da_doc")
