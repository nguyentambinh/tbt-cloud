# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0006_os_images"
down_revision = "0005_plan_catalog"
branch_labels = None
depends_on = None

IMAGES = [
    ("debian13", "Debian 13", "linux", 512, 10, "ssh", 1),
    ("ubuntu2404", "Ubuntu 24.04 LTS", "linux", 1024, 10, "ssh", 2),
    ("ubuntu2604", "Ubuntu 26.04 LTS", "linux", 1024, 10, "ssh", 3),
    ("centos10", "CentOS Stream 10", "linux", 1024, 10, "ssh", 4),
    ("kali", "Kali Linux", "linux", 2048, 25, "ssh", 5),
    ("winserver2022", "Windows Server 2022", "windows", 2048, 40, "rdp", 6),
    ("windows11", "Windows 11", "windows", 4096, 64, "rdp", 7),
]


def upgrade():
    op.create_table("os_images", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ma", sa.String(30), nullable=False, unique=True), sa.Column("ten", sa.String(100), nullable=False), sa.Column("ho", sa.String(10), nullable=False), sa.Column("min_ram_mb", sa.Integer(), nullable=False), sa.Column("min_disk_gb", sa.Integer(), nullable=False), sa.Column("ket_noi", sa.String(3), nullable=False), sa.Column("thu_tu", sa.Integer(), nullable=False), sa.CheckConstraint("ho IN ('linux', 'windows')", name="ck_os_family"), sa.CheckConstraint("ket_noi IN ('ssh', 'rdp')", name="ck_os_connection"), sa.CheckConstraint("min_ram_mb > 0 AND min_disk_gb > 0", name="ck_os_resources"))
    op.create_table("node_os_templates", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("node_id", sa.Integer(), sa.ForeignKey("nodes.id"), nullable=False), sa.Column("os_image_id", sa.Integer(), sa.ForeignKey("os_images.id"), nullable=False), sa.Column("template_id", sa.Integer(), nullable=False), sa.UniqueConstraint("node_id", "os_image_id", name="uq_node_os_template"), sa.CheckConstraint("template_id >= 100 AND template_id <= 999999999", name="ck_os_template_id"))
    with op.batch_alter_table("instances") as batch:
        batch.add_column(sa.Column("os_image_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_instance_os_image", "os_images", ["os_image_id"], ["id"])
    images = sa.table("os_images", sa.column("ma", sa.String), sa.column("ten", sa.String), sa.column("ho", sa.String), sa.column("min_ram_mb", sa.Integer), sa.column("min_disk_gb", sa.Integer), sa.column("ket_noi", sa.String), sa.column("thu_tu", sa.Integer))
    op.bulk_insert(images, [dict(zip((column.name for column in images.columns), values)) for values in IMAGES])
    connection = op.get_bind()
    connection.execute(sa.text("INSERT INTO node_os_templates (node_id, os_image_id, template_id) SELECT nodes.id, os_images.id, nodes.vm_template_id FROM nodes CROSS JOIN os_images WHERE nodes.vm_template_id IS NOT NULL AND os_images.ma='debian13'"))
    connection.execute(sa.text("UPDATE instances SET os_image_id=(SELECT id FROM os_images WHERE ma='debian13') WHERE loai='vm' AND dich_vu='vps'"))
    plans = sa.table("plans", sa.column("ten", sa.String), sa.column("dich_vu", sa.String), sa.column("vcpu", sa.Integer), sa.column("ram_mb", sa.Integer), sa.column("disk_gb", sa.Integer), sa.column("gia_theo_gio", sa.Numeric), sa.column("mo_ta", sa.String))
    for values in [("Windows Tiêu chuẩn", "vps", 2, 4096, 64, 2500, "Máy Windows làm việc, học tập"), ("Windows Hiệu năng", "vps", 4, 8192, 80, 4500, "Windows chạy phần mềm nặng")]:
        row = dict(zip((column.name for column in plans.columns), values))
        connection.execute(plans.insert().from_select(list(row), sa.select(*(sa.literal(value) for value in row.values())).where(~sa.exists(sa.select(1).select_from(plans).where(plans.c.ten == row["ten"])))))


def downgrade():
    with op.batch_alter_table("instances") as batch:
        batch.drop_constraint("fk_instance_os_image", type_="foreignkey")
        batch.drop_column("os_image_id")
    op.drop_table("node_os_templates")
    op.drop_table("os_images")
