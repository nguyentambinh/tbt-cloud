# Nguyễn Tâm Bình - 2324801030003
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

from app.config import get_settings
from app.db import Base


def test_initial_migration_matches_models_and_downgrades(tmp_path, monkeypatch):
    url = "sqlite+pysqlite:///" + (tmp_path / "migration.sqlite").as_posix()
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT id FROM allocation_locks")) == 1
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    engine.dispose()
    command.downgrade(config, "base")
    engine = create_engine(url)
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()


def test_access_migration_preserves_existing_instances(tmp_path, monkeypatch, instance):
    url = "sqlite+pysqlite:///" + (tmp_path / "existing.sqlite").as_posix()
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0001_initial")
    engine = create_engine(url)
    old_table = Table("instances", MetaData(), autoload_with=engine)
    values = {column.name: getattr(instance, column.name) for column in old_table.columns}
    with engine.begin() as connection:
        connection.execute(old_table.insert().values(**values))
    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(url)
    new_table = Table("instances", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        row = connection.execute(select(new_table)).mappings().one()
        assert row["id"] == instance.id and row["vmid"] == instance.vmid and row["trang_thai"] == "running"
        assert all(row[name] is None for name in ("password_encrypted", "cloud_user", "ssh_public_key", "template_id", "ip_cidr", "gateway"))
    engine.dispose()
    command.downgrade(config, "0001_initial")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT vmid FROM instances")) == instance.vmid
    assert "password_encrypted" not in {column["name"] for column in inspect(engine).get_columns("instances")}
    engine.dispose()
    command.downgrade(config, "base")
    engine = create_engine(url)
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()


def test_payos_migration_preserves_wallet_transactions_and_node(tmp_path, monkeypatch, seed):
    url = "sqlite+pysqlite:///" + (tmp_path / "payos.sqlite").as_posix()
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0002_instance_access")
    engine = create_engine(url)
    node_table = Table("nodes", MetaData(), autoload_with=engine)
    values = {column.name: getattr(seed["node"], column.name) for column in node_table.columns}
    with engine.begin() as connection:
        connection.execute(node_table.insert().values(**values))
        connection.execute(text("INSERT INTO users (id,email,password_hash,role,created_at) VALUES (1,'migration@example.com','unused','user',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO wallets (id,user_id,balance) VALUES (1,1,12345)"))
        connection.execute(text("INSERT INTO transactions (id,wallet_id,amount,kind,idempotency_key,description,created_at) VALUES (1,1,12345,'topup','old-request','Nạp ví ảo',CURRENT_TIMESTAMP)"))
    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT balance FROM wallets WHERE id=1")) == 12345
        assert connection.scalar(text("SELECT idempotency_key FROM transactions WHERE id=1")) == "old-request"
        assert connection.scalar(text("SELECT notify_offline FROM nodes")) == 0
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    engine.dispose()
    command.downgrade(config, "0002_instance_access")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT balance FROM wallets WHERE id=1")) == 12345
        assert connection.scalar(text("SELECT kind FROM transactions WHERE id=1")) == "topup"
    assert "payments" not in inspect(engine).get_table_names() and "notifications" not in inspect(engine).get_table_names()
    engine.dispose()
