# Nguyễn Tâm Bình - 2324801030003
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.scheduler import select_node


def node(node_id, used=0, **overrides):
    values = {"id": node_id, "trang_thai": "online", "vm_template_id": 9000, "lxc_template_id": 9001, "total_vcpu": 8, "total_ram_mb": 8192, "total_disk_gb": 100, "used_vcpu": used, "used_ram_mb": used * 1024, "used_disk_gb": used * 10}
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("strategy, expected", [("best-fit", 2), ("least-loaded", 1)])
def test_strategy(strategy, expected):
    plan = SimpleNamespace(vcpu=2, ram_mb=1024, disk_gb=10)
    assert select_node([node(1, 1), node(2, 5)], plan, strategy).id == expected


@pytest.mark.parametrize("overrides", [{"trang_thai": "offline"}, {"used_vcpu": 8}, {"used_ram_mb": 8192}, {"used_disk_gb": 100}, {"vm_template_id": None}])
def test_excludes_unavailable_nodes(overrides):
    plan = SimpleNamespace(vcpu=1, ram_mb=512, disk_gb=10)
    with pytest.raises(HTTPException) as error:
        select_node([node(1, **overrides)], plan)
    assert error.value.status_code == 503


def test_exact_capacity_and_stable_tie():
    plan = SimpleNamespace(vcpu=8, ram_mb=8192, disk_gb=100)
    assert select_node([node(2), node(1)], plan).id == 1


def test_lxc_requires_its_own_template():
    plan = SimpleNamespace(vcpu=1, ram_mb=512, disk_gb=10)
    assert select_node([node(1, lxc_template_id=None), node(2, vm_template_id=None)], plan, loai="lxc").id == 2


def test_invalid_strategy():
    with pytest.raises(ValueError):
        select_node([], SimpleNamespace(), "random")


def test_thin_disk_overcommit_fits_large_plan():
    plan = SimpleNamespace(vcpu=2, ram_mb=4096, disk_gb=64)
    assert select_node([node(1, total_disk_gb=91, used_disk_gb=46, measured_disk_gb=47)], plan).id == 1


def test_real_free_disk_reserve_blocks():
    plan = SimpleNamespace(vcpu=1, ram_mb=512, disk_gb=10)
    with pytest.raises(HTTPException):
        select_node([node(1, total_disk_gb=91, used_disk_gb=20, measured_disk_gb=85)], plan)


def test_overcommit_ratio_one_is_strict(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "disk_overcommit", 1.0)
    plan = SimpleNamespace(vcpu=2, ram_mb=4096, disk_gb=64)
    with pytest.raises(HTTPException):
        select_node([node(1, total_disk_gb=91, used_disk_gb=46, measured_disk_gb=47)], plan)
