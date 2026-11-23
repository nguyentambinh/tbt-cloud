#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Dựng template VM cloud-init cho từng hệ điều hành Linux từ ảnh cloud chính thức (kiểm SHA256 trước khi nhập)
# Dùng: dung_template_os.sh <ma_os> [storage] [bridge]   ma_os: ubuntu2404 | ubuntu2604 | centos10 | kali
set -euo pipefail
MA=$1; STORAGE=${2:-local}; BRIDGE=${3:-vpsnet0}
DIR=/var/lib/vz/template/os; mkdir -p "$DIR"; cd "$DIR"

case $MA in
  ubuntu2404) VMID=9010; TEN="Ubuntu 24.04 LTS"; GOC=https://cloud-images.ubuntu.com/noble/current; TEP=noble-server-cloudimg-amd64.img; SUMS=SHA256SUMS ;;
  ubuntu2604) VMID=9011; TEN="Ubuntu 26.04 LTS"; GOC=https://cloud-images.ubuntu.com/resolute/current; TEP=resolute-server-cloudimg-amd64.img; SUMS=SHA256SUMS ;;
  centos10)   VMID=9012; TEN="CentOS Stream 10"; GOC=https://cloud.centos.org/centos/10-stream/x86_64/images; TEP=CentOS-Stream-GenericCloud-10-latest.x86_64.qcow2; SUMS=$TEP.SHA256SUM ;;
  kali)       VMID=9013; TEN="Kali Linux"; GOC=https://kali.download/cloud-images/current; TEP=$(curl -fsS "$GOC/" | grep -o 'kali-linux-[0-9.]*-cloud-genericcloud-amd64.tar.xz' | head -1); SUMS=SHA256SUMS ;;
  *) echo "ma_os khong hop le: $MA" >&2; exit 2 ;;
esac

if qm status "$VMID" >/dev/null 2>&1; then echo "$VMID da co, bo qua"; exit 0; fi

curl -fsSL -o "$TEP.part" "$GOC/$TEP" && mv "$TEP.part" "$TEP"
curl -fsSL -o "$MA.sums" "$GOC/$SUMS"
MONG=$(grep -E "[ *(]$TEP[) ]|$TEP\$" "$MA.sums" | grep -oE '[0-9a-f]{64}' | head -1)
THAT=$(sha256sum "$TEP" | cut -d' ' -f1)
[ -n "$MONG" ] && [ "$MONG" = "$THAT" ] || { echo "SHA256 sai: $TEP" >&2; exit 3; }

ANH=$TEP
if [[ $TEP == *.tar.xz ]]; then
  rm -rf "$MA.x"; mkdir "$MA.x"; tar -xJf "$TEP" -C "$MA.x"
  ANH=$(find "$MA.x" -type f \( -name '*.raw' -o -name '*.qcow2' -o -name '*.img' \) | head -1)
fi

qm create "$VMID" --name "tpl-$MA" --description "$TEN" --memory 1024 --cores 1 --cpu host --ostype l26 \
  --net0 "virtio,bridge=$BRIDGE" --scsihw virtio-scsi-single --serial0 socket --vga serial0 --agent enabled=1
qm importdisk "$VMID" "$ANH" "$STORAGE" --format raw >/dev/null
DISK=$(qm config "$VMID" | awk -F': ' '/^unused0/{print $2}')
qm set "$VMID" --scsi0 "$DISK,discard=on" --boot order=scsi0 --ide2 "$STORAGE:cloudinit" --ipconfig0 ip=dhcp
qm template "$VMID"
rm -rf "$MA.x" "$TEP" "$MA.sums"
echo "XONG $VMID $TEN"
