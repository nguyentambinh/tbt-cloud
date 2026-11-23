# Nguyễn Tâm Bình - 2324801030003
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from requests.exceptions import Timeout

from app.config import get_settings
from app.security import decrypt_secret, encrypt_secret
from app.services.proxmox_client import ProxmoxClient, ProxmoxError


@pytest.fixture
def proxmox(monkeypatch, seed):
    api = MagicMock()
    constructor = MagicMock(return_value=api)
    monkeypatch.setattr("app.services.proxmox_client.ProxmoxAPI", constructor)
    client = ProxmoxClient(seed["node"])
    api.nodes.return_value.tasks.return_value.status.get.return_value = {"status": "stopped", "exitstatus": "OK"}
    return client, api, constructor


def test_token_encrypted_and_tls_enabled(seed, proxmox):
    client, api, constructor = proxmox
    assert seed["node"].token_secret != "dummy-token"
    assert decrypt_secret(seed["node"].token_secret) == "dummy-token"
    assert encrypt_secret("dummy-token") != seed["node"].token_secret
    options = constructor.call_args.kwargs
    assert options["verify_ssl"] is True
    assert options["timeout"] == get_settings().proxmox_timeout
    assert options["user"] == "cloud@pve"
    assert options["token_name"] == "control"


def test_timeout_never_exposes_original_error(proxmox):
    client, api, constructor = proxmox
    client.endpoint.status.get.side_effect = Timeout("token-secret-in-original-error")
    with pytest.raises(ProxmoxError) as error:
        client.check_connection()
    assert error.value.status_code == 502
    assert "token-secret" not in error.value.detail


def test_node_measured_resources_distinct_from_allocations(proxmox):
    client, api, constructor = proxmox
    client.endpoint.status.get.return_value = {"cpuinfo": {"cpus": 8}, "cpu": .2534, "memory": {"total": 16 * 1048576, "used": 4 * 1048576}}
    client.endpoint.storage.return_value.status.get.return_value = {"total": 20 * 1073741824, "used": 2 * 1073741824}
    api.cluster.resources.get.return_value = [{"node": client.node.proxmox_node, "maxcpu": 2, "maxmem": 8 * 1048576, "maxdisk": 10 * 1073741824}]
    result = client.get_node_resources()
    assert result["cpu_percent"] == 25.34 and result["measured_ram_mb"] == 4 and result["measured_disk_gb"] == 2
    assert result["used_vcpu"] == 2 and result["used_ram_mb"] == 8 and result["used_disk_gb"] == 10


def test_clone_waits_for_task(proxmox):
    client, api, constructor = proxmox
    guest = client.endpoint.qemu.return_value
    guest.config.get.return_value = {"template": 1}
    guest.clone.post.return_value = "UPID:clone"
    client.clone_template(9000, 101, "server-1", "vm")
    guest.clone.post.assert_called_once_with(newid=101, full=1, storage="local-lvm", name="server-1")
    client.endpoint.tasks.assert_called_with("UPID:clone")


def test_failed_task_never_treated_as_success(proxmox):
    client, api, constructor = proxmox
    client.endpoint.tasks.return_value.status.get.return_value = {"status": "stopped", "exitstatus": "ERROR secret"}
    client.endpoint.qemu.return_value.status.start.post.return_value = "UPID:start"
    with pytest.raises(ProxmoxError) as error:
        client.start(101, "vm")
    assert "secret" not in error.value.detail


def test_task_timeout_is_bounded(proxmox, monkeypatch):
    client, api, constructor = proxmox
    clock = iter([0, get_settings().proxmox_task_timeout + 1])
    monkeypatch.setattr("app.services.proxmox_client.monotonic", lambda: next(clock))
    client.endpoint.qemu.return_value.status.start.post.return_value = "UPID:slow-task"
    with pytest.raises(ProxmoxError) as error:
        client.start(101, "vm")
    assert "thời gian chờ" in error.value.detail


def test_vmid_ignores_used_vm_lxc_and_database_reservations(proxmox):
    client, api, constructor = proxmox
    api.cluster.resources.get.return_value = [{"vmid": 100}, {"vmid": 102}]
    assert client.find_free_vmid([101]) == 103


def test_vm_cloud_init_and_disk_resize(proxmox):
    client, api, constructor = proxmox
    guest = client.endpoint.qemu.return_value
    guest.config.get.return_value = {"scsi0": "local-lvm:vm-101-disk-0,size=8G"}
    guest.config.put.return_value = None
    guest.resize.put.return_value = None
    plan = SimpleNamespace(vcpu=2, ram_mb=1024, disk_gb=10)
    client.configure_cloud_init(101, "vm", plan, "ubuntu", "ssh-ed25519 key", "10.0.0.2/24", "10.0.0.1")
    values = guest.config.put.call_args.kwargs
    assert values["ciuser"] == "ubuntu"
    assert values["sshkeys"] == "ssh-ed25519%20key"
    assert values["ipconfig0"] == "ip=10.0.0.2/24,gw=10.0.0.1"
    guest.resize.put.assert_called_once_with(disk="scsi0", size="10G")


def test_lxc_requires_hook_and_uses_native_network(proxmox):
    client, api, constructor = proxmox
    guest = client.endpoint.lxc.return_value
    guest.config.get.return_value = {"rootfs": "local-lvm:vm-101-disk-0,size=8G"}
    plan = SimpleNamespace(vcpu=1, ram_mb=512, disk_gb=8)
    with pytest.raises(ProxmoxError):
        client.configure_cloud_init(101, "lxc", plan, "root", "ssh-ed25519 key")
    guest.config.get.return_value["hookscript"] = "local:snippets/control-plane-lxc-hook.sh"
    guest.config.put.return_value = None
    client.configure_cloud_init(101, "lxc", plan, "root", "ssh-ed25519 key")
    values = guest.config.put.call_args.kwargs
    assert "ip=dhcp" in values["net0"]
    assert values["description"].startswith("control-plane:")
    assert "ciuser" not in values
    assert "ssh-public-keys" not in values


def test_vm_password_and_cloudinit_regeneration(proxmox):
    client, api, constructor = proxmox
    guest = client.endpoint.qemu.return_value
    guest.config.get.return_value = {"scsi0": "local-lvm:disk,size=8G"}
    guest.config.put.return_value = "UPID:config"
    guest.cloudinit.put.return_value = "UPID:cloudinit"
    client.configure_cloud_init(101, "vm", SimpleNamespace(vcpu=1, ram_mb=512, disk_gb=8), "ubuntu", "ssh-ed25519 key", password="GeneratedPassword123")
    assert guest.config.put.call_args.kwargs["cipassword"] == "GeneratedPassword123"
    client.set_password(101, "ubuntu", "ReplacementPassword123")
    guest.config.put.assert_called_with(ciuser="ubuntu", cipassword="ReplacementPassword123")
    guest.cloudinit.put.assert_called_once_with()
    client.endpoint.tasks.assert_called_with("UPID:cloudinit")


@pytest.mark.parametrize("loai", ["vm", "lxc"])
def test_rrd_and_current_status_normalization(proxmox, loai):
    client, api, constructor = proxmox
    guest = client.endpoint.qemu.return_value if loai == "vm" else client.endpoint.lxc.return_value
    guest.rrddata.get.return_value = [{"time": 2, "cpu": 0.25, "mem": 100, "maxmem": 512, "netin": 0, "netout": 2, "diskread": 3, "diskwrite": 4}, {"time": 1}]
    result = client.get_stats(101, loai, "week")
    guest.rrddata.get.assert_called_once_with(timeframe="week", cf="AVERAGE")
    assert result[0] == dict(time=1, cpu=None, mem_used=None, mem_total=None, netin=None, netout=None, diskread=None, diskwrite=None)
    assert result[1] == dict(time=2, cpu=25, mem_used=100, mem_total=512, netin=0, netout=2, diskread=3, diskwrite=4)
    guest.status.current.get.return_value = {"cpu": 0.25, "mem": 100, "uptime": 20}
    assert client.get_status_now(101, loai) == {"cpu": 25, "mem": 100, "uptime": 20}


def test_termproxy_serial_and_template_name(proxmox):
    client, api, constructor = proxmox
    guest = client.endpoint.qemu.return_value
    guest.termproxy.post.return_value = {"port": 5900, "ticket": "fake-ticket", "user": "cloud@pve"}
    assert client.termproxy(101)["port"] == 5900
    guest.termproxy.post.assert_called_once_with(serial="serial0")
    guest.config.get.return_value = {"description": "Debian 13 cloud-init"}
    assert client.get_template_name(9000, "vm") == "Debian 13 cloud-init"


@pytest.mark.parametrize("method, args", [("get_stats", (101, "vm", "hour")), ("get_status_now", (101, "vm")), ("set_password", (101, "ubuntu", "Password123")), ("termproxy", (101,))])
def test_management_upstream_error_is_sanitized(proxmox, method, args):
    client, api, constructor = proxmox
    guest = client.endpoint.qemu.return_value
    guest.rrddata.get.side_effect = Timeout("secret-upstream")
    guest.status.current.get.side_effect = Timeout("secret-upstream")
    guest.config.put.side_effect = Timeout("secret-upstream")
    guest.termproxy.post.side_effect = Timeout("secret-upstream")
    with pytest.raises(ProxmoxError) as error:
        getattr(client, method)(*args)
    assert "secret-upstream" not in error.value.detail


def test_ip_falls_back_to_sdn_ipam(proxmox):
    client, api, constructor = proxmox
    client.endpoint.qemu.return_value.agent.return_value.get.side_effect = Timeout()
    api.cluster.sdn.ipams.return_value.status.get.return_value = [{"vmid": 999, "ip": "10.0.0.9"}, {"vmid": 101, "ip": "10.0.0.2"}]
    assert client.get_ip(101, "vm") == "10.0.0.2"


def test_vm_cloud_init_public_ipv6(proxmox):
    client, api, constructor = proxmox
    guest = client.endpoint.qemu.return_value
    guest.config.get.return_value = {"scsi0": "local-lvm:vm-101-disk-0,size=8G"}
    guest.config.put.return_value = None
    client.configure_cloud_init(101, "vm", SimpleNamespace(vcpu=1, ram_mb=1024, disk_gb=8, ipv6="2402:800:639e:f77c::101"), "root", None)
    assert guest.config.put.call_args.kwargs["ipconfig0"] == "ip=dhcp,ip6=2402:800:639e:f77c::101/128,gw6=fe80::1"
