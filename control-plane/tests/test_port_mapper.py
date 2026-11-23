# Nguyễn Tâm Bình - 2324801030003
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import Instance
from app.services.port_mapper import allocate_ssh_port, release_ssh_port


def another(db, instance, vmid):
    value = Instance(ten=f"server-{vmid}", user_id=instance.user_id, node_id=instance.node_id, plan_id=instance.plan_id, vmid=vmid, loai="vm", vcpu=1, ram_mb=512, disk_gb=10, gia_theo_gio=instance.gia_theo_gio)
    db.add(value)
    db.flush()
    return value


def test_unique_ports_and_exhaustion(db, instance):
    first = allocate_ssh_port(db, instance, 22000, 22001)
    second = another(db, instance, 102)
    assert allocate_ssh_port(db, second, 22000, 22001) != first
    assert allocate_ssh_port(db, instance, 22000, 22001) == first
    with pytest.raises(HTTPException) as error:
        allocate_ssh_port(db, another(db, instance, 103), 22000, 22001)
    assert error.value.status_code == 503


def test_port_reused_only_after_delete(db, instance):
    allocate_ssh_port(db, instance, 22000, 22000)
    with pytest.raises(ValueError):
        release_ssh_port(db, instance)
    instance.trang_thai = "deleted"
    release_ssh_port(db, instance)
    second = another(db, instance, 102)
    assert allocate_ssh_port(db, second, 22000, 22000) == 22000


def test_database_guards_duplicate_ports(db, instance):
    instance.ssh_port = 22000
    second = another(db, instance, 102)
    second.ssh_port = 22000
    with pytest.raises(IntegrityError):
        db.flush()


def test_invalid_range(db, instance):
    with pytest.raises(ValueError):
        allocate_ssh_port(db, instance, 23000, 22000)
