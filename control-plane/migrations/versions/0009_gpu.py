# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0009_gpu"
down_revision = "0008_admin"
branch_labels = None
depends_on = None

AI_PLANS = [("AI Tiêu chuẩn", "vps", 6, 16384, 40, 9000, "Huấn luyện mô hình vừa, thử nghiệm học sâu", 1), ("AI Hiệu năng", "vps", 10, 24576, 40, 14000, "Fine-tune mô hình, chạy nhiều tác vụ GPU", 1)]


def upgrade():
    with op.batch_alter_table("plans") as batch:
        batch.add_column(sa.Column("gpu", sa.Integer(), nullable=False, server_default="0"))
        batch.create_check_constraint("ck_plan_gpu", "gpu >= 0 AND gpu <= 8")
    with op.batch_alter_table("os_images") as batch:
        batch.add_column(sa.Column("chi_gpu", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("node_gpus", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("node_id", sa.Integer(), sa.ForeignKey("nodes.id"), nullable=False), sa.Column("pci_id", sa.String(32), nullable=False), sa.Column("ten", sa.String(120), nullable=False), sa.Column("vram_mb", sa.Integer(), nullable=False), sa.UniqueConstraint("node_id", "pci_id", name="uq_node_gpu_pci"), sa.CheckConstraint("vram_mb > 0", name="ck_node_gpu_vram"))
    with op.batch_alter_table("instances") as batch:
        batch.add_column(sa.Column("gpu_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_instance_gpu", "node_gpus", ["gpu_id"], ["id"])
    op.create_index("uq_instance_gpu_active", "instances", ["gpu_id"], unique=True, postgresql_where=sa.text("gpu_id IS NOT NULL AND trang_thai NOT IN ('deleted', 'error')"), sqlite_where=sa.text("gpu_id IS NOT NULL AND trang_thai NOT IN ('deleted', 'error')"))
    connection = op.get_bind()
    images = sa.table("os_images", sa.column("ma", sa.String), sa.column("ten", sa.String), sa.column("ho", sa.String), sa.column("min_ram_mb", sa.Integer), sa.column("min_disk_gb", sa.Integer), sa.column("ket_noi", sa.String), sa.column("thu_tu", sa.Integer), sa.column("chi_gpu", sa.Boolean))
    if not connection.scalar(sa.select(sa.func.count()).select_from(images).where(images.c.ma == "ubuntu2404ai")):
        connection.execute(images.insert().values(ma="ubuntu2404ai", ten="Ubuntu 24.04 + CUDA + PyTorch", ho="linux", min_ram_mb=8192, min_disk_gb=30, ket_noi="ssh", thu_tu=8, chi_gpu=True))
    plans = sa.table("plans", sa.column("ten", sa.String), sa.column("dich_vu", sa.String), sa.column("vcpu", sa.Integer), sa.column("ram_mb", sa.Integer), sa.column("disk_gb", sa.Integer), sa.column("gia_theo_gio", sa.Numeric), sa.column("mo_ta", sa.String), sa.column("gpu", sa.Integer))
    for values in AI_PLANS:
        row = dict(zip((column.name for column in plans.columns), values))
        connection.execute(plans.insert().from_select(list(row), sa.select(*(sa.literal(value) for value in row.values())).where(~sa.exists(sa.select(1).select_from(plans).where(plans.c.ten == row["ten"])))))


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE plans SET active = false WHERE gpu > 0"))
    connection.execute(sa.text("DELETE FROM node_os_templates WHERE os_image_id IN (SELECT id FROM os_images WHERE ma = 'ubuntu2404ai')"))
    connection.execute(sa.text("DELETE FROM os_images WHERE ma = 'ubuntu2404ai' AND NOT EXISTS (SELECT 1 FROM instances WHERE instances.os_image_id = os_images.id)"))
    op.drop_index("uq_instance_gpu_active", table_name="instances")
    with op.batch_alter_table("instances") as batch:
        batch.drop_constraint("fk_instance_gpu", type_="foreignkey")
        batch.drop_column("gpu_id")
    op.drop_table("node_gpus")
    with op.batch_alter_table("os_images") as batch:
        batch.drop_column("chi_gpu")
    with op.batch_alter_table("plans") as batch:
        batch.drop_constraint("ck_plan_gpu", type_="check")
        batch.drop_column("gpu")
