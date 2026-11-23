#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Thử template: clone tạm, cloud-init đặt user + khóa SSH + IP tĩnh, chờ SSH, in thông tin hệ điều hành rồi xóa máy tạm
set -u
TPL=$1; VMID=$2; IP=$3; DISK=${4:-10}
qm clone "$TPL" "$VMID" --name "thu-os-$VMID" --full 0 >/dev/null
qm resize "$VMID" scsi0 "${DISK}G" >/dev/null 2>&1
qm set "$VMID" --ciuser tbtthu --sshkeys /root/.ssh/id_rsa.pub --ipconfig0 "ip=$IP/24,gw=10.10.10.1" --nameserver 1.1.1.1 --memory 2048 >/dev/null
qm start "$VMID"
T0=$(date +%s); KQ="KHONG SSH DUOC"
for i in $(seq 1 60); do
  if ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 tbtthu@$IP 'grep PRETTY_NAME /etc/os-release; df -h / | tail -1; curl -s -m 5 -o /dev/null -w "internet %{http_code}" https://deb.debian.org' 2>/dev/null > /tmp/kq_$VMID; then KQ="SSH OK sau $(( $(date +%s)-T0 ))s: $(tr '\n' ' ' < /tmp/kq_$VMID)"; break; fi
  sleep 5
done
echo "$TPL -> $KQ"
qm stop "$VMID" >/dev/null 2>&1; qm destroy "$VMID" --purge >/dev/null 2>&1
