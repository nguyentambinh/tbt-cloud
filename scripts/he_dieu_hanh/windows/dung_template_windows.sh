#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Cài Windows tự động từ ISO Evaluation (OVMF, Secure Boot, TPM 2.0, virtio), cloudbase-init tự cấu hình mỗi máy clone, đóng thành template
# Dùng: dung_template_windows.sh <win11|ws2022>   (chạy trong thư mục chứa autounattend.xml.in và các tệp đi kèm)
set -euo pipefail
MA=$1; STORAGE=${2:-local}; BRIDGE=${3:-vpsnet0}; ISO=/var/lib/vz/template/iso
case $MA in
  win11)  VMID=9020; TEN="Windows 11 Enterprise Evaluation"; WINISO=win11-eval.iso; INDEX=1; DRV=w11; DISK=64 ;;
  ws2022) VMID=9021; TEN="Windows Server 2022 Standard Evaluation"; WINISO=winserver2022-eval.iso; INDEX=2; DRV=2k22; DISK=40 ;;
  *) echo "ma khong hop le: $MA" >&2; exit 2 ;;
esac
if qm status "$VMID" >/dev/null 2>&1; then echo "$VMID da co, bo qua"; exit 0; fi
HERE=$(cd "$(dirname "$0")" && pwd); WORK=$(mktemp -d)
BUILDPW=$(openssl rand -hex 10)Aa1!
sed -e "s/@INDEX@/$INDEX/" -e "s/@DRV@/$DRV/g" -e "s/@BUILDPW@/$BUILDPW/g" "$HERE/autounattend.xml.in" > "$WORK/autounattend.xml"
cp "$HERE/tbt-setup.ps1" "$HERE/cloudbase-init.conf" "$HERE/CloudbaseInitSetup_Stable_x64.msi" "$WORK/"
genisoimage -quiet -J -r -V TBTANSWER -o "$ISO/tbt-answer-$MA.iso" "$WORK"; rm -rf "$WORK"

qm create "$VMID" --name "tpl-$MA" --description "$TEN" --machine q35 --bios ovmf --ostype win11 --cpu host --cores 4 --memory 4096 \
  --efidisk0 "$STORAGE:1,efitype=4m,pre-enrolled-keys=1" --tpmstate0 "$STORAGE:1,version=v2.0" --scsihw virtio-scsi-single \
  --scsi0 "$STORAGE:$DISK,discard=on" --net0 "virtio,bridge=$BRIDGE,link_down=1" --serial0 socket --agent enabled=1 \
  --ide0 "local:iso/$WINISO,media=cdrom" --ide1 "local:iso/virtio-win.iso,media=cdrom" --ide3 "local:iso/tbt-answer-$MA.iso,media=cdrom" --boot "order=scsi0;ide0"
qm start "$VMID"
for i in $(seq 1 8); do qm sendkey "$VMID" ret >/dev/null 2>&1 || true; sleep 1; done
T0=$(date +%s)
while qm status "$VMID" | grep -q running; do
  [ $(( $(date +%s) - T0 )) -gt 5400 ] && { echo "QUA 90 PHUT, dung lai de kiem tra" >&2; exit 4; }
  sleep 20
done
echo "cai xong sau $(( $(date +%s) - T0 ))s"
qm set "$VMID" --delete ide0,ide1,ide3 >/dev/null
qm set "$VMID" --net0 "virtio,bridge=$BRIDGE" --ide2 "$STORAGE:cloudinit" --citype configdrive2 --ipconfig0 ip=dhcp --boot order=scsi0 --agent enabled=1 --memory 4096 --cores 2 >/dev/null
qm template "$VMID"
rm -f "$ISO/tbt-answer-$MA.iso"
echo "XONG $VMID $TEN"
