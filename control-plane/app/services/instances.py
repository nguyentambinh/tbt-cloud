# Nguyễn Tâm Bình - 2324801030003
import base64
import ipaddress
import json
import re
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from ipaddress import ip_interface
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import func, select

from app.config import get_settings
from app.db import lock_control_plane
from app.models import AuditLog, Instance, Node, OSImage, Plan, Transaction
from app.schemas import InstanceOutput
from app.security import decrypt_secret, encrypt_secret, generate_login_password, generate_vps_password
from app.services.billing import charge_due_hours, charge_hour, get_wallet
from app.services.gpu import busy_gpu_ids, free_gpus
from app.services.port_mapper import allocate_app_port, allocate_ssh_port, release_app_port, release_ssh_port
from app.services.proxmox_client import ProxmoxClient, ProxmoxError
from app.services.scheduler import fits, select_node
from app.services import notify


def owned_instance(db, instance_id, user):
    instance = db.get(Instance, instance_id, populate_existing=True)
    if instance is None or instance.trang_thai == "deleted" or (user.role != "admin" and instance.user_id != user.id):
        raise HTTPException(status_code=404, detail="Không tìm thấy máy chủ ảo.")
    return instance


def default_name(db, user):
    base = re.sub(r"[^a-z0-9-]+", "-", (user.username or user.email.split("@")[0]).lower()).strip("-")[:50].strip("-") or "vps"
    used = set(db.scalars(select(Instance.ten).where(Instance.user_id == user.id)))
    number = 1
    while f"{base}-{number}" in used:
        number += 1
    return f"{base}-{number}"


def login_password(windows=False):
    return generate_login_password()


def assign_ipv6(node, instance):
    # VPS Linux trên node có prefix công cộng: địa chỉ riêng <prefix>::<vmid>, agent trên node định tuyến và trả lời NDP
    instance.ipv6 = None
    if not node.ipv6_prefix or instance.loai != "vm" or instance.ket_noi == "rdp":
        return
    network = ipaddress.IPv6Network(node.ipv6_prefix)
    instance.ipv6 = str(network.network_address + int(str(instance.vmid), 16))


def cloud_init_vendor(instance):
    return None if instance.loai != "vm" or instance.ket_noi == "rdp" else get_settings().cloud_init_vendor or None


def create_instance(db, user, data):
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Quản trị viên không thể thuê dịch vụ. Hãy dùng tài khoản khách hàng.")
    lock_control_plane(db)
    plan = db.get(Plan, data.plan_id)
    if plan is None or not plan.active:
        raise HTTPException(status_code=404, detail="Không tìm thấy gói cấu hình.")
    if plan.dich_vu != data.dich_vu:
        raise HTTPException(status_code=422, detail="Gói này dành cho dịch vụ khác.")
    image = db.scalar(select(OSImage).where(OSImage.ma == data.os_ma)) if data.dich_vu == "vps" and data.loai == "vm" else None
    if data.dich_vu == "vps" and data.loai == "vm":
        if image is None:
            raise HTTPException(status_code=422, detail="Hệ điều hành chưa có trong danh mục.")
        if plan.ram_mb < image.min_ram_mb:
            ram = f"{image.min_ram_mb / 1024:g} GB" if image.min_ram_mb >= 1024 else f"{image.min_ram_mb} MB"
            raise HTTPException(status_code=422, detail=f"Gói {plan.ten} chưa đủ RAM cho {image.ten}, cần tối thiểu {ram}.")
        if plan.disk_gb < image.min_disk_gb:
            raise HTTPException(status_code=422, detail=f"Gói {plan.ten} chưa đủ ổ đĩa cho {image.ten}, cần tối thiểu {image.min_disk_gb} GB.")
    if plan.gpu and not (image and image.chi_gpu):
        raise HTTPException(status_code=422, detail="Gói có GPU dùng hệ điều hành Ubuntu 24.04 + CUDA + PyTorch.")
    if image is not None and image.chi_gpu and not plan.gpu:
        raise HTTPException(status_code=422, detail="Hệ điều hành này chỉ dùng cho gói máy chủ AI có GPU.")
    if get_wallet(db, user.id).balance < plan.gia_theo_gio:
        raise HTTPException(status_code=402, detail="Ví cần đủ số dư cho ít nhất một giờ sử dụng.")
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=120)
    nodes = list(db.scalars(select(Node).where(Node.last_seen_at >= cutoff, Node.last_seen_at <= datetime.now(timezone.utc)).execution_options(populate_existing=True)))
    if plan.gpu:
        busy = busy_gpu_ids(db)
        nodes = [item for item in nodes if len(free_gpus(db, item, busy)) >= plan.gpu]
        if not nodes:
            raise HTTPException(status_code=409, detail="GPU đang được dùng hết, vui lòng thử lại sau.")
    node = select_node(nodes, plan, data.strategy or get_settings().scheduler_strategy, data.loai, data.dich_vu, os_image=image)
    ip = str(ip_interface(data.ip_cidr).ip) if data.ip_cidr else None
    if ip and db.scalar(select(Instance.id).where(Instance.node_id == node.id, Instance.ip == ip, Instance.trang_thai != "deleted")):
        raise HTTPException(status_code=409, detail="Địa chỉ IP đã được cấp trên node này.")
    client = ProxmoxClient(node)
    reserved = list(db.scalars(select(Instance.vmid).where(Instance.node_id == node.id)))
    vmid = client.find_free_vmid(reserved)
    password = login_password(image is not None and image.ho == "windows") if data.loai == "vm" else None
    data.ten = data.ten or default_name(db, user)
    template_id = node.paas_template_id if data.dich_vu != "vps" else node.vm_template_id if data.loai == "vm" else node.lxc_template_id
    if image is not None:
        template_id = next(mapping.template_id for mapping in node.os_templates if mapping.os_image_id == image.id)
    app_config = None
    if data.dich_vu == "postgres":
        app_config = {"kind": "postgres", "db": "app", "user": "app", "password": generate_vps_password()}
    elif data.dich_vu == "webapp":
        app_config = {"kind": "webapp", "repo": data.repo_url, "branch": data.branch}
    instance = Instance(ten=data.ten, user_id=user.id, node_id=node.id, plan_id=plan.id, vmid=vmid, loai=data.loai, dich_vu=data.dich_vu, app_config_encrypted=encrypt_secret(json.dumps(app_config)) if app_config else None, trang_thai="provisioning", ip=ip, vcpu=plan.vcpu, ram_mb=plan.ram_mb, disk_gb=plan.disk_gb, gia_theo_gio=plan.gia_theo_gio, password_encrypted=encrypt_secret(password) if password else None, cloud_user=data.cloud_user, ssh_public_key=data.ssh_public_key, template_id=template_id, ip_cidr=data.ip_cidr, gateway=data.gateway)
    db.add(instance)
    instance.os_image = image
    if plan.gpu:
        instance.gpu = free_gpus(db, node)[0]
    db.flush()
    assign_ipv6(node, instance)
    allocate_ssh_port(db, instance)
    if data.dich_vu != "vps":
        allocate_app_port(db, instance)
    node.used_vcpu += plan.vcpu
    node.used_ram_mb += plan.ram_mb
    node.used_disk_gb += plan.disk_gb
    db.add(AuditLog(user_id=user.id, action="instance.reserve", resource=f"instance:{instance.id}"))
    db.commit()
    lock_control_plane(db)
    try:
        client.clone_template(template_id, vmid, data.ten, data.loai)
        client.configure_cloud_init(vmid, data.loai, instance, data.cloud_user, data.ssh_public_key, data.ip_cidr, data.gateway, password=password, gpu_pci=instance.gpu.pci_id if instance.gpu else None, vendor=cloud_init_vendor(instance), **({"smbios_serial": smbios_serial(instance)} if app_config else {}))
        if not charge_hour(db, instance, reset_period=True):
            instance.trang_thai = "stopped"
            db.commit()
            raise HTTPException(status_code=402, detail="Máy đã được tạo nhưng ví không còn đủ số dư để khởi động.")
        client.start(vmid, data.loai)
    except ProxmoxError:
        db.rollback()
        lock_control_plane(db)
        instance = db.get(Instance, instance.id, populate_existing=True)
        instance.trang_thai = "error"
        db.add(AuditLog(user_id=user.id, action="instance.provision_failed", resource=f"instance:{instance.id}", detail="Cần kiểm tra node trước khi thu hồi tài nguyên"))
        notify.instance_event(db, instance, "provision_failed", "Lỗi tạo VPS")
        db.commit()
        raise
    instance.trang_thai = "running"
    refresh_ip(client, instance)
    db.add(AuditLog(user_id=user.id, action="instance.create", resource=f"instance:{instance.id}"))
    notify.instance_event(db, instance, "create", "Tạo VPS thành công")
    db.commit()
    return instance


def smbios_serial(instance):
    if not instance.app_config_encrypted:
        raise HTTPException(status_code=409, detail="Dịch vụ chưa lưu đủ cấu hình. Hãy liên hệ quản trị viên.")
    return base64.b64encode(decrypt_secret(instance.app_config_encrypted).encode()).decode()


def service_info(instance):
    if instance.dich_vu == "vps":
        raise HTTPException(status_code=404, detail="Máy chủ VPS không có thông tin kết nối dịch vụ PaaS.")
    if not instance.app_config_encrypted:
        raise HTTPException(status_code=409, detail="Dịch vụ chưa lưu đủ cấu hình. Hãy liên hệ quản trị viên.")
    config = json.loads(decrypt_secret(instance.app_config_encrypted))
    host = get_settings().gateway_host
    address = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return {"dich_vu": instance.dich_vu, "host": host, "port": instance.app_port, "url": f"http://{address}:{instance.app_port}" if instance.dich_vu == "webapp" else None, "connection_string": f"postgresql://{quote(config['user'], safe='')}:{quote(config['password'], safe='')}@{address}:{instance.app_port}/{quote(config['db'], safe='')}" if instance.dich_vu == "postgres" else None, "repo_url": config.get("repo"), "branch": config.get("branch")}


def refresh_ip(client, instance):
    try:
        instance.ip = client.get_ip(instance.vmid, instance.loai) or instance.ip
    except ProxmoxError:
        pass


def credentials(instance):
    host = get_settings().gateway_host
    address = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return {"username": instance.cloud_user or ("tbtadmin" if instance.ket_noi == "rdp" else "root"), "password": decrypt_secret(instance.password_encrypted) if instance.password_encrypted else None, "ssh_host": host, "ipv6": instance.ipv6, "ssh_port": instance.ssh_port, "ket_noi": instance.ket_noi, "host": host, "port": instance.ssh_port, "dia_chi": f"{address}:{instance.ssh_port}" if instance.ssh_port else address}


def instance_detail(db, instance):
    client = ProxmoxClient(instance.node)
    template_id = instance.template_id or (instance.node.vm_template_id if instance.loai == "vm" else instance.node.lxc_template_id)
    result = InstanceOutput.model_validate(instance).model_dump()
    result.update(gpu=f"{instance.gpu.ten} {instance.gpu.vram_mb // 1024} GB" if instance.gpu and instance.trang_thai not in ("deleted", "error") else None, ten_he_dieu_hanh=instance.os_image.ten if instance.os_image else "Debian 13" if instance.loai == "lxc" else client.get_template_name(template_id, instance.loai) if template_id else "Chưa xác định", node_ten=instance.node.ten, tong_chi_phi=-db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.instance_id == instance.id, Transaction.kind == "usage", Transaction.amount < 0)), ngay_tao=instance.created_at, trang_thai=client.get_status(instance.vmid, instance.loai))
    return result


def node_without(node, instance):
    # Tài nguyên node khi bỏ phần máy đang dùng, để xét gói mới khi cài lại
    measured = getattr(node, "measured_disk_gb", None)
    return SimpleNamespace(trang_thai="online", total_vcpu=node.total_vcpu, total_ram_mb=node.total_ram_mb, total_disk_gb=node.total_disk_gb, used_vcpu=node.used_vcpu - instance.vcpu, used_ram_mb=node.used_ram_mb - instance.ram_mb, used_disk_gb=node.used_disk_gb - instance.disk_gb, measured_disk_gb=None if measured is None else measured - instance.disk_gb)


def reinstall_choices(db, instance):
    if instance.dich_vu != "vps" or instance.loai != "vm":
        return [], []
    gpu = instance.gpu is not None
    images = sorted((mapping.os_image for mapping in instance.node.os_templates if mapping.os_image.chi_gpu == gpu), key=lambda image: (image.thu_tu, image.id))
    current = db.get(Plan, instance.plan_id)
    plans = [plan for plan in db.scalars(select(Plan).where(Plan.active.is_(True), Plan.dich_vu == "vps").order_by(Plan.gia_theo_gio, Plan.id)) if (plan.gpu > 0) == gpu and (not gpu or plan.gpu == (current.gpu if current else plan.gpu))]
    return images, plans


def reinstall_options(db, user, instance_id):
    instance = owned_instance(db, instance_id, user)
    images, plans = reinstall_choices(db, instance)
    spare = node_without(instance.node, instance)
    return {"os_ma": instance.os_image.ma if instance.os_image else None, "plan_id": instance.plan_id, "gia_theo_gio": instance.gia_theo_gio, "os": [{"ma": image.ma, "ten": image.ten, "ho": image.ho, "ket_noi": image.ket_noi, "min_ram_mb": image.min_ram_mb, "min_disk_gb": image.min_disk_gb} for image in images], "plans": [{"id": plan.id, "ten": plan.ten, "vcpu": plan.vcpu, "ram_mb": plan.ram_mb, "disk_gb": plan.disk_gb, "gpu": plan.gpu, "gia_theo_gio": plan.gia_theo_gio, "du_tai_nguyen": plan.id == instance.plan_id or fits(spare, plan)} for plan in plans]}


def apply_reinstall_target(db, user, instance, os_ma, plan_id):
    images, plans = reinstall_choices(db, instance)
    if not images:
        raise HTTPException(status_code=400, detail="Dịch vụ này chỉ cài lại được hệ điều hành đang dùng.")
    image = next((item for item in images if item.ma == os_ma), None) if os_ma else instance.os_image
    plan = next((item for item in plans if item.id == plan_id), None) if plan_id else db.get(Plan, instance.plan_id)
    if image is None or image not in images:
        raise HTTPException(status_code=422, detail="Hệ điều hành này chưa có trên máy chủ đang chạy dịch vụ của bạn.")
    if plan is None or (plan_id and plan not in plans):
        raise HTTPException(status_code=422, detail="Gói này không dùng được cho máy chủ hiện tại.")
    if plan.ram_mb < image.min_ram_mb or plan.disk_gb < image.min_disk_gb:
        raise HTTPException(status_code=422, detail=f"Gói {plan.ten} chưa đủ tài nguyên cho {image.ten}, cần tối thiểu {image.min_ram_mb} MB RAM và {image.min_disk_gb} GB ổ đĩa.")
    if plan.id != instance.plan_id and not fits(node_without(instance.node, instance), plan):
        raise HTTPException(status_code=409, detail=f"Máy chủ đang chạy dịch vụ của bạn không còn đủ tài nguyên cho gói {plan.ten}. Hãy chọn gói nhỏ hơn.")
    if plan.gia_theo_gio > instance.gia_theo_gio and get_wallet(db, user.id).balance < plan.gia_theo_gio:
        raise HTTPException(status_code=402, detail="Ví cần đủ số dư cho một giờ theo giá gói mới.")
    node = instance.node
    node.used_vcpu += plan.vcpu - instance.vcpu
    node.used_ram_mb += plan.ram_mb - instance.ram_mb
    node.used_disk_gb += plan.disk_gb - instance.disk_gb
    old_price = instance.gia_theo_gio
    instance.plan_id, instance.vcpu, instance.ram_mb, instance.disk_gb, instance.gia_theo_gio = plan.id, plan.vcpu, plan.ram_mb, plan.disk_gb, plan.gia_theo_gio
    instance.os_image = image
    instance.template_id = next(mapping.template_id for mapping in node.os_templates if mapping.os_image_id == image.id)
    if image.ket_noi == "rdp":
        instance.cloud_user, instance.ssh_public_key = "tbtadmin", None
    elif instance.cloud_user == "tbtadmin":
        instance.cloud_user = "root"
    return old_price


def maintain_instance(db, user, instance_id, action, password=None, os_ma=None, plan_id=None):
    lock_control_plane(db)
    instance = owned_instance(db, instance_id, user)
    if instance.trang_thai not in {"running", "stopped"}:
        raise HTTPException(status_code=409, detail="Máy chủ chưa sẵn sàng cho thao tác này. Vui lòng kiểm tra trạng thái và số dư.")
    if action == "password" and instance.loai == "lxc":
        raise HTTPException(status_code=400, detail="Đổi mật khẩu cho LXC hiện chưa được hỗ trợ.")
    if not instance.cloud_user or (action == "reinstall" and ((instance.ket_noi != "rdp" and not instance.ssh_public_key and not instance.password_encrypted) or not instance.template_id)):
        raise HTTPException(status_code=409, detail="Máy chủ chưa lưu đủ cấu hình đăng nhập để thực hiện thao tác. Vui lòng liên hệ quản trị viên.")
    client = ProxmoxClient(instance.node)
    serial = smbios_serial(instance) if action == "reinstall" and instance.dich_vu != "vps" else None
    if action == "reinstall":
        client.get_template_name(instance.template_id, instance.loai)
    paid = charge_due_hours(db, instance) if instance.trang_thai == "running" else charge_hour(db, instance, reset_period=True)
    if not paid:
        raise HTTPException(status_code=402, detail="Ví cần đủ số dư để khởi động máy chủ sau thao tác.")
    old_price = None
    if action == "reinstall" and (os_ma or plan_id):
        old_price = apply_reinstall_target(db, user, instance, os_ma, plan_id)
        client.get_template_name(instance.template_id, instance.loai)
    was_running = client.get_status(instance.vmid, instance.loai) == "running"
    windows = instance.ket_noi == "rdp"
    if password and windows and sum(any(test(c) for c in password) for test in (str.isupper, str.islower, str.isdigit, lambda c: not c.isalnum())) < 3:
        raise HTTPException(status_code=422, detail="Mật khẩu Windows cần ít nhất 3 trong 4 loại: chữ hoa, chữ thường, số, ký tự đặc biệt.")
    new_password = (password or login_password(windows)) if instance.loai == "vm" else None
    instance.trang_thai = "provisioning"
    if action == "reinstall":
        instance.ip = None
    db.add(AuditLog(user_id=user.id, action=f"instance.{action}_begin", resource=f"instance:{instance.id}", detail=f"{instance.os_image.ma if instance.os_image else ''} gói {instance.plan_id}, giá {old_price} → {instance.gia_theo_gio}/giờ" if old_price is not None else None))
    db.commit()
    lock_control_plane(db)
    try:
        if action == "reinstall":
            assign_ipv6(instance.node, instance)
            client.stop(instance.vmid, instance.loai)
            client.delete(instance.vmid, instance.loai)
            client.clone_template(instance.template_id, instance.vmid, instance.ten, instance.loai)
            client.configure_cloud_init(instance.vmid, instance.loai, instance, instance.cloud_user, instance.ssh_public_key, instance.ip_cidr, instance.gateway, password=new_password, gpu_pci=instance.gpu.pci_id if instance.gpu else None, vendor=cloud_init_vendor(instance), **({"smbios_serial": serial} if serial else {}))
        else:
            client.set_password(instance.vmid, instance.cloud_user, new_password)
        instance.password_encrypted = encrypt_secret(new_password) if new_password else None
        db.commit()
        lock_control_plane(db)
        if action == "password" and was_running:
            client.reboot(instance.vmid, instance.loai)
        else:
            client.start(instance.vmid, instance.loai)
        instance.ip = str(ip_interface(instance.ip_cidr).ip) if instance.ip_cidr else instance.ip
        refresh_ip(client, instance)
        instance.trang_thai = "running"
        db.add(AuditLog(user_id=user.id, action=f"instance.{action}", resource=f"instance:{instance.id}"))
        if action == "reinstall":
            notify.instance_event(db, instance, "reinstall", "Cài lại hệ điều hành thành công")
        db.commit()
    except ProxmoxError:
        db.rollback()
        lock_control_plane(db)
        instance = db.get(Instance, instance.id, populate_existing=True)
        instance.trang_thai = "error"
        db.add(AuditLog(user_id=user.id, action=f"instance.{action}_failed", resource=f"instance:{instance.id}", detail="Cần kiểm tra tác vụ trên node"))
        if action == "reinstall":
            notify.instance_event(db, instance, "reinstall_failed", "Lỗi cài lại hệ điều hành VPS")
        db.commit()
        raise
    return instance


def perform_action(db, user, instance_id, action):
    lock_control_plane(db)
    instance = owned_instance(db, instance_id, user)
    if instance.trang_thai == "provisioning":
        raise HTTPException(status_code=409, detail="Máy chủ đang được cấp phát. Vui lòng chờ hoàn tất.")
    if instance.trang_thai == "error" and action != "delete":
        raise HTTPException(status_code=409, detail="Máy chủ cần được quản trị viên kiểm tra hoặc xóa để tạo lại.")
    client = ProxmoxClient(instance.node)
    if action == "start":
        paid = charge_due_hours(db, instance) if instance.trang_thai == "running" else charge_hour(db, instance, reset_period=True)
        if not paid:
            raise HTTPException(status_code=402, detail="Số dư không đủ để khởi động máy chủ.")
        if client.get_status(instance.vmid, instance.loai) != "running":
            client.start(instance.vmid, instance.loai)
        instance.trang_thai = "running"
    elif action == "stop":
        if instance.trang_thai == "running" and not charge_due_hours(db, instance):
            instance.trang_thai = "suspended"
            notify.instance_event(db, instance, "suspended", "VPS bị dừng do hết tiền")
        client.stop(instance.vmid, instance.loai)
        if instance.trang_thai != "suspended":
            instance.trang_thai = "stopped"
    elif action == "reboot":
        if instance.trang_thai != "running":
            raise HTTPException(status_code=409, detail="Chỉ có thể khởi động lại máy đang chạy.")
        if not charge_due_hours(db, instance):
            raise HTTPException(status_code=402, detail="Số dư không đủ để khởi động lại máy chủ.")
        client.reboot(instance.vmid, instance.loai)
    elif action == "delete":
        if instance.trang_thai == "running":
            charge_due_hours(db, instance)
        client.delete(instance.vmid, instance.loai)
        instance.trang_thai = "deleted"
        release_ssh_port(db, instance)
        release_app_port(db, instance)
        node = instance.node
        node.used_vcpu = max(0, node.used_vcpu - instance.vcpu)
        node.used_ram_mb = max(0, node.used_ram_mb - instance.ram_mb)
        node.used_disk_gb = max(0, node.used_disk_gb - instance.disk_gb)
    else:
        raise ValueError("Thao tác không hợp lệ.")
    db.add(AuditLog(user_id=user.id, action=f"instance.{action}", resource=f"instance:{instance.id}"))
    if action == "delete":
        notify.instance_event(db, instance, "delete", "Xóa VPS thành công")
    db.commit()
    return instance
