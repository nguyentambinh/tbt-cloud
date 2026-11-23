#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Cài vendor-data cloud-init cho VM Linux: root đăng nhập SSH bằng mật khẩu (Proxmox gắn qua cicustom vendor=local:snippets/tbt-vendor.yaml)
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
grep -A3 '^dir: local' /etc/pve/storage.cfg | grep -q snippets || { echo "Storage local chưa bật nội dung snippets: thêm snippets vào dòng content của local" >&2; exit 1; }
install -D -m 0644 "$DIR/tbt-vendor.yaml" /var/lib/vz/snippets/tbt-vendor.yaml
echo "XONG /var/lib/vz/snippets/tbt-vendor.yaml"
