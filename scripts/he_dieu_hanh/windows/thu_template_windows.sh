#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Thử template Windows: clone, cloud-init đặt mật khẩu tbtadmin + IP tĩnh, chờ RDP 3389, đọc log cloudbase-init rồi xóa máy thử
set -u
TPL=$1; VMID=$2; IP=$3; DISK=${4:-}
PW="Thu$(openssl rand -hex 6)Aa1"
qm clone "$TPL" "$VMID" --name "thu-win-$VMID" >/dev/null
[ -n "$DISK" ] && qm resize "$VMID" scsi0 "${DISK}G" >/dev/null
qm set "$VMID" --ciuser tbtadmin --cipassword "$PW" --ipconfig0 "ip=$IP/24,gw=10.10.10.1" --nameserver 1.1.1.1 >/dev/null
qm start "$VMID"; T0=$(date +%s); KQ="RDP KHONG MO"
for i in $(seq 1 90); do timeout 3 bash -c "</dev/tcp/$IP/3389" 2>/dev/null && { KQ="RDP 3389 mo sau $(( $(date +%s)-T0 ))s"; break; }; sleep 10; done
echo "$TPL -> $KQ"; sleep 60
for i in 1 2 3 4 5 6; do xfreerdp3 /v:$IP /u:tbtadmin /p:"$PW" /cert:ignore /auth-only >/dev/null 2>&1 && { echo "DANG NHAP RDP tbtadmin: THANH CONG"; break; }; [ $i = 6 ] && echo "DANG NHAP RDP tbtadmin: THAT BAI"; sleep 20; done
echo "screendump /tmp/thu-$VMID.ppm" | qm monitor "$VMID" >/dev/null
qm stop "$VMID" >/dev/null
F=$(pvesm path "$(qm config "$VMID" | grep -oE '^scsi0: [^,]+' | cut -d' ' -f2)")
modprobe nbd max_part=8; qemu-nbd -r -c /dev/nbd1 "$F"; sleep 2; mkdir -p /mnt/thu-$VMID
P=$(lsblk -lnbo NAME,SIZE,TYPE /dev/nbd1 | awk '$3=="part"' | sort -k2 -n | tail -1 | cut -d' ' -f1)
mount -t ntfs3 -o ro /dev/$P /mnt/thu-$VMID && grep -hiE "createuser|setuserpassword|networkconfig|sethostname|Extending volume|Plugins execution done"  "/mnt/thu-$VMID/Program Files/Cloudbase Solutions/Cloudbase-Init/log/cloudbase-init.log" | grep -v "already done" | cut -c1-200 | head -30
cd /; umount /mnt/thu-$VMID; qemu-nbd -d /dev/nbd1 >/dev/null
qm destroy "$VMID" --purge >/dev/null
