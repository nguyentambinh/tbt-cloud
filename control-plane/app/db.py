# Nguyễn Tâm Bình - 2324801030003
from functools import lru_cache

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory():
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db():
    with get_session_factory()() as db:
        yield db


def lock_control_plane(db):
    from app.models import AllocationLock

    if db.bind.dialect.name == "sqlite" and not db.connection().connection.driver_connection.in_transaction:
        db.execute(text("BEGIN IMMEDIATE"))
    if db.scalar(select(AllocationLock).where(AllocationLock.id == 1).with_for_update()) is None:
        raise RuntimeError("Cần chạy Alembic migration trước khi sử dụng API.")
