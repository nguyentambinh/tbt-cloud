# Nguyễn Tâm Bình - 2324801030003
from fastapi import HTTPException

from app.config import get_settings


def disk_capacity(node):
    # Đĩa thin: cấp vượt theo tỉ lệ, luôn chừa dung lượng trống thật tối thiểu
    return node.total_disk_gb * get_settings().disk_overcommit


def fits(node, plan):
    settings = get_settings()
    real_free = node.total_disk_gb - (getattr(node, "measured_disk_gb", None) if getattr(node, "measured_disk_gb", None) is not None else node.used_disk_gb)
    return node.trang_thai == "online" and node.total_vcpu - node.used_vcpu >= plan.vcpu and node.total_ram_mb - node.used_ram_mb >= plan.ram_mb and disk_capacity(node) - node.used_disk_gb >= plan.disk_gb and real_free >= settings.disk_reserve_gb


def select_node(nodes, plan, strategy="best-fit", loai="vm", dich_vu="vps", os_image=None):
    if strategy not in {"best-fit", "least-loaded"}:
        raise ValueError("Chiến lược điều phối không hợp lệ.")
    if os_image is not None and dich_vu == "vps" and loai == "vm":
        eligible = [node for node in nodes if any(mapping.os_image_id == os_image.id for mapping in node.os_templates) and fits(node, plan)]
    else:
        eligible = [node for node in nodes if getattr(node, "paas_template_id" if dich_vu != "vps" else "vm_template_id" if loai == "vm" else "lxc_template_id", None) and fits(node, plan)]
    if not eligible:
        if os_image is not None:
            raise HTTPException(status_code=503, detail=f"Chưa có node sẵn sàng cho {os_image.ten} và đủ tài nguyên cho gói này.")
        raise HTTPException(status_code=503, detail="Chưa có node trực tuyến đủ tài nguyên cho cấu hình này.")

    def score(node):
        remaining = ((node.total_vcpu - node.used_vcpu - plan.vcpu) / node.total_vcpu, (node.total_ram_mb - node.used_ram_mb - plan.ram_mb) / node.total_ram_mb, (disk_capacity(node) - node.used_disk_gb - plan.disk_gb) / disk_capacity(node))
        return (sum(remaining) if strategy == "best-fit" else -min(remaining), node.id)

    return min(eligible, key=score)
