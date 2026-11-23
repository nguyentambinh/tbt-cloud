# Nguyễn Tâm Bình - 2324801030003
import re

from alembic import op
import sqlalchemy as sa

revision = "0007_dang_ky_xac_nhan"
down_revision = "0006_os_images"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("ho_ten", sa.String(80), nullable=True))
        batch.add_column(sa.Column("username", sa.String(30), nullable=True))
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)
    connection = op.get_bind()
    assigned = set()
    for user_id, email in connection.execute(sa.text("SELECT id, email FROM users ORDER BY id")).all():
        username = email.lower()
        if re.fullmatch(r"[a-z][a-z0-9._]{2,29}", username) and username not in assigned:
            connection.execute(sa.text("UPDATE users SET username=:username WHERE id=:id"), {"username": username, "id": user_id})
            assigned.add(username)
    op.create_table("pending_registrations", sa.Column("email", sa.String(254), primary_key=True), sa.Column("ho_ten", sa.String(80), nullable=False), sa.Column("username", sa.String(30), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("code_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("failed_attempts", sa.Integer(), nullable=False), sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False), sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("send_count", sa.Integer(), nullable=False), sa.CheckConstraint("failed_attempts >= 0 AND failed_attempts <= 5", name="ck_registration_attempts"), sa.CheckConstraint("send_count >= 1 AND send_count <= 5", name="ck_registration_send_count"))


def downgrade():
    op.drop_table("pending_registrations")
    op.drop_index("uq_users_username_lower", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("username")
        batch.drop_column("ho_ten")
