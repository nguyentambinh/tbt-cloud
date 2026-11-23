# Nguyễn Tâm Bình - 2324801030003
import json
from functools import wraps
from ipaddress import ip_address
from time import monotonic, sleep
from urllib.parse import quote, urlsplit

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from requests.exceptions import RequestException

from app.config import get_settings
from app.security import decrypt_secret


class ProxmoxError(HTTPException):
    def __init__(self, detail="Không thể thực hiện yêu cầu trên node. Vui lòng thử lại hoặc liên hệ quản trị viên."):
        super().__init__(status_code=502, detail=detail)


def safe_call(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ProxmoxError:
            raise
        except (ResourceException, RequestException, OSError, ValueError, KeyError, TypeError, InvalidToken, IndexError):
            raise ProxmoxError() from None
    return wrapped


class ProxmoxClient:
    @safe_call
    def __init__(self, node):
        self.node = node
        self.settings = get_settings()
        parsed = urlsplit(node.api_url)
        user, token_name = node.token_id.split("!", 1)
        self.api = ProxmoxAPI(parsed.hostname, user=user, token_name=token_name, token_value=decrypt_secret(node.token_secret), port=parsed.port or 8006, verify_ssl=self._verify(), timeout=self.settings.proxmox_timeout, backend="https")
        self.endpoint = self.api.nodes(node.proxmox_node)

    def _verify(self):
        value = self.settings.proxmox_verify_ssl.strip()
        return {"true": True, "false": False}.get(value.lower(), value)

    def _guest(self, vmid, loai):
        if loai not in {"vm", "lxc"}:
            raise ValueError("Loại instance không hợp lệ.")
        return self.endpoint.qemu(vmid) if loai == "vm" else self.endpoint.lxc(vmid)

    def _wait(self, task):
        if not isinstance(task, str) or not task.startswith("UPID:"):
            raise ProxmoxError("Node không xác nhận tác vụ. Vui lòng liên hệ quản trị viên.")
        deadline = monotonic() + self.settings.proxmox_task_timeout
        while monotonic() < deadline:
            status = self.endpoint.tasks(task).status.get()
            if status.get("status") == "stopped":
                if status.get("exitstatus") != "OK":
                    raise ProxmoxError("Tác vụ trên node chưa thành công. Vui lòng liên hệ quản trị viên.")
                return
            sleep(0.5)
        raise ProxmoxError("Node phản hồi quá thời gian chờ. Quản trị viên cần kiểm tra trạng thái tác vụ.")

    @safe_call
    def check_connection(self):
        self.endpoint.status.get()
        return True

    @safe_call
    def find_free_vmid(self, reserved=()):
        used = {int(item["vmid"]) for item in self.api.cluster.resources.get(type="vm")} | set(reserved)
        vmid = next((candidate for candidate in range(100, 1000000) if candidate not in used), None)
        if vmid is None:
            raise ProxmoxError("Node đã hết mã định danh instance khả dụng.")
        return vmid

    @safe_call
    def clone_template(self, template_id, vmid, ten, loai):
        template = self._guest(template_id, loai)
        if int(template.config.get().get("template", 0)) != 1:
            raise ProxmoxError("Template của node chưa được cấu hình đúng.")
        options = {"newid": vmid, "full": 1, "storage": self.node.storage, "name" if loai == "vm" else "hostname": ten}
        self._wait(template.clone.post(**options))

    @safe_call
    def configure_cloud_init(self, vmid, loai, plan, cloud_user, ssh_key, ip_cidr=None, gateway=None, password=None, smbios_serial=None, gpu_pci=None, vendor=None):
        guest = self._guest(vmid, loai)
        config = guest.config.get()
        disk = self.node.vm_disk if loai == "vm" else "rootfs"
        volume = str(config.get(disk, ""))
        size_field = next((field[5:] for field in volume.split(",") if field.startswith("size=")), "")
        if not size_field:
            raise ProxmoxError("Template chưa khai báo dung lượng đĩa hệ thống.")
        units = {"K": 1 / 1048576, "M": 1 / 1024, "G": 1, "T": 1024}
        current_gb = float(size_field[:-1]) * units[size_field[-1].upper()]
        if plan.disk_gb < current_gb:
            raise ProxmoxError("Dung lượng gói nhỏ hơn đĩa hệ thống của template.")
        options = {"cores": plan.vcpu, "memory": plan.ram_mb, "onboot": 1}
        if loai == "vm":
            options.update(sockets=1, ciuser=cloud_user, ipconfig0=f"ip={ip_cidr or 'dhcp'}" + (f",gw={gateway}" if gateway else "") + (f",ip6={plan.ipv6}/128,gw6=fe80::1" if getattr(plan, "ipv6", None) else ""), net0=f"virtio,bridge={self.node.bridge},firewall=1")
            if ssh_key:
                options["sshkeys"] = quote(ssh_key, safe="")
            if smbios_serial is not None:
                options["smbios1"] = f"serial={smbios_serial},base64=1"
            if password is not None:
                options["cipassword"] = password
            if vendor:
                options["cicustom"] = f"vendor={vendor}"
            if gpu_pci:
                # Tên mapping (Mapping.Use) cho token thường; địa chỉ PCI thô chỉ root được gắn
                options["hostpci0"] = f"{gpu_pci},pcie=1" if ":" in gpu_pci else f"mapping={gpu_pci},pcie=1"
        else:
            if cloud_user != "root":
                raise ProxmoxError("LXC chỉ hỗ trợ tài khoản root từ template.")
            if not config.get("hookscript"):
                raise ProxmoxError("Template LXC cần cài hook cấp khóa SSH trước khi tạo instance.")
            options["net0"] = f"name=eth0,bridge={self.node.bridge},ip={ip_cidr or 'dhcp'},firewall=1" + (f",gw={gateway}" if gateway else "")
            options["description"] = "control-plane:" + json.dumps({"cloud_user": cloud_user, "ssh_public_key": ssh_key}, ensure_ascii=True)
        result = guest.config.put(**options)
        if isinstance(result, str) and result.startswith("UPID:"):
            self._wait(result)
        if plan.disk_gb > current_gb:
            result = guest.resize.put(disk=disk, size=f"{plan.disk_gb}G")
            if isinstance(result, str) and result.startswith("UPID:"):
                self._wait(result)

    @safe_call
    def set_password(self, vmid, cloud_user, password):
        guest = self._guest(vmid, "vm")
        result = guest.config.put(ciuser=cloud_user, cipassword=password)
        if isinstance(result, str) and result.startswith("UPID:"):
            self._wait(result)
        result = guest.cloudinit.put()
        if isinstance(result, str) and result.startswith("UPID:"):
            self._wait(result)

    @safe_call
    def get_template_name(self, template_id, loai):
        config = self._guest(template_id, loai).config.get()
        description = str(config.get("description") or "").strip().splitlines()
        return description[0].strip() if description else str(config.get("name") or config.get("hostname") or "Chưa xác định")

    @safe_call
    def get_stats(self, vmid, loai, timeframe):
        if timeframe not in {"hour", "day", "week"}:
            raise ValueError("Khoảng thời gian không hợp lệ.")
        rows = self._guest(vmid, loai).rrddata.get(timeframe=timeframe, cf="AVERAGE")
        return [{"time": row["time"], "cpu": float(row["cpu"]) * 100 if row.get("cpu") is not None else None, "mem_used": row.get("mem"), "mem_total": row.get("maxmem"), "netin": row.get("netin"), "netout": row.get("netout"), "diskread": row.get("diskread"), "diskwrite": row.get("diskwrite")} for row in sorted(rows, key=lambda row: row["time"])]

    @safe_call
    def get_status_now(self, vmid, loai):
        status = self._guest(vmid, loai).status.current.get()
        return {"cpu": float(status.get("cpu", 0)) * 100, "mem": int(status.get("mem", 0)), "uptime": int(status.get("uptime", 0))}

    @safe_call
    def termproxy(self, vmid):
        return self._guest(vmid, "vm").termproxy.post(serial="serial0")

    @safe_call
    def start(self, vmid, loai):
        self._wait(self._guest(vmid, loai).status.start.post())

    @safe_call
    def stop(self, vmid, loai):
        if self.get_status(vmid, loai) == "running":
            self._wait(self._guest(vmid, loai).status.stop.post())

    @safe_call
    def reboot(self, vmid, loai):
        self._wait(self._guest(vmid, loai).status.reboot.post())

    @safe_call
    def delete(self, vmid, loai):
        guests = self.endpoint.qemu.get() + self.endpoint.lxc.get()
        if not any(int(guest["vmid"]) == vmid for guest in guests):
            return
        self.stop(vmid, loai)
        self._wait(self._guest(vmid, loai).delete(purge=1))

    @safe_call
    def get_status(self, vmid, loai):
        return self._guest(vmid, loai).status.current.get()["status"]

    @safe_call
    def get_ip(self, vmid, loai):
        guest = self._guest(vmid, loai)
        addresses = []
        try:
            if loai == "vm":
                interfaces = guest.agent("network-get-interfaces").get().get("result", [])
                addresses = [item.get("ip-address", "") for interface in interfaces for item in interface.get("ip-addresses", []) if interface.get("name") != "lo"]
            else:
                interfaces = guest.interfaces.get()
                addresses = [interface.get("inet", "").split("/")[0] for interface in interfaces if interface.get("name") != "lo"]
        except Exception:
            addresses = []
        if not addresses:
            # Guest chưa có agent: lấy địa chỉ DHCP đã cấp từ IPAM của Proxmox SDN
            try:
                addresses = [str(item.get("ip", "")) for item in self.api.cluster.sdn.ipams("pve").status.get() if str(item.get("vmid", "")) == str(vmid)]
            except Exception:
                addresses = []
        for value in addresses:
            try:
                address = ip_address(value)
            except ValueError:
                continue
            if address.version == 4 and not address.is_loopback and not address.is_link_local and not address.is_unspecified:
                return str(address)
        return None

    @safe_call
    def get_node_resources(self):
        status = self.endpoint.status.get()
        storage = self.endpoint.storage(self.node.storage).status.get()
        guests = [item for item in self.api.cluster.resources.get(type="vm") if item.get("node") == self.node.proxmox_node and not item.get("template")]
        measured = {"cpu_percent": round(float(status["cpu"]) * 100, 2) if status.get("cpu") is not None else None, "measured_ram_mb": int(status["memory"]["used"] // 1048576), "measured_disk_gb": int((storage["used"] + 1073741823) // 1073741824)}
        return {**measured, "total_vcpu": int(status["cpuinfo"]["cpus"]), "total_ram_mb": int(status["memory"]["total"] // 1048576), "total_disk_gb": int(storage["total"] // 1073741824), "used_vcpu": sum(int(item.get("maxcpu", 0)) for item in guests), "used_ram_mb": max(int(status["memory"]["used"] // 1048576), sum(int(item.get("maxmem", 0) // 1048576) for item in guests)), "used_disk_gb": max(int((storage["used"] + 1073741823) // 1073741824), sum(int((item.get("maxdisk", 0) + 1073741823) // 1073741824) for item in guests))}
