# Nguyễn Tâm Bình - 2324801030003
from alembic import op
import sqlalchemy as sa

revision = "0005_plan_catalog"
down_revision = "0004_paas"
branch_labels = None
depends_on = None

CATALOG = [
    ("Nano", "vps", 1, 512, 10, 300, "Thử nghiệm, bot nhỏ, máy học Linux"),
    ("Lớn", "vps", 4, 4096, 30, 2000, "Ứng dụng web nhiều người dùng"),
    ("Rất lớn", "vps", 8, 8192, 40, 4000, "Biên dịch, xử lý dữ liệu"),
    ("Tối ưu CPU", "vps", 4, 2048, 20, 1500, "Tính toán nặng, ít bộ nhớ"),
    ("Tối ưu RAM", "vps", 2, 8192, 20, 2500, "Bộ nhớ đệm, phân tích dữ liệu"),
    ("CSDL Cơ bản", "postgres", 1, 1024, 10, 600, "Đồ án, ứng dụng thử"),
    ("CSDL Tiêu chuẩn", "postgres", 2, 2048, 20, 1200, "Ứng dụng chạy thật, vài chục kết nối"),
    ("CSDL Hiệu năng", "postgres", 4, 4096, 40, 2400, "Truy vấn nặng, dữ liệu lớn hơn"),
    ("Web Cơ bản", "webapp", 1, 1024, 10, 500, "Trang tĩnh, portfolio"),
    ("Web Tiêu chuẩn", "webapp", 2, 2048, 15, 1000, "Ứng dụng Node.js nhỏ"),
    ("Web Mở rộng", "webapp", 4, 4096, 20, 2000, "Ứng dụng nhiều truy cập"),
]


def upgrade():
    with op.batch_alter_table("plans") as batch:
        batch.add_column(sa.Column("dich_vu", sa.String(10), nullable=False, server_default="vps"))
        batch.add_column(sa.Column("mo_ta", sa.String(160), nullable=False, server_default=""))
        batch.create_check_constraint("ck_plan_service", "dich_vu IN ('vps', 'postgres', 'webapp')")
    plans = sa.table("plans", sa.column("ten", sa.String(100)), sa.column("dich_vu", sa.String(10)), sa.column("vcpu", sa.Integer), sa.column("ram_mb", sa.Integer), sa.column("disk_gb", sa.Integer), sa.column("gia_theo_gio", sa.Numeric(18, 2)), sa.column("mo_ta", sa.String(160)))
    connection = op.get_bind()
    for values in CATALOG:
        row = dict(zip((column.name for column in plans.columns), values))
        connection.execute(plans.insert().from_select(list(row), sa.select(*(sa.literal(value) for value in row.values())).where(~sa.exists(sa.select(1).select_from(plans).where(plans.c.ten == row["ten"])))))
    for name, description in (("Nhỏ", "Web cá nhân, môi trường học tập"), ("Vừa", "Ứng dụng nhỏ có cơ sở dữ liệu")):
        connection.execute(plans.update().where(plans.c.ten == name, plans.c.mo_ta == "").values(mo_ta=description))


def downgrade():
    with op.batch_alter_table("plans") as batch:
        batch.drop_constraint("ck_plan_service", type_="check")
        batch.drop_column("mo_ta")
        batch.drop_column("dich_vu")
