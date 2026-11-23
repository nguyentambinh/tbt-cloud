#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Dựng template 9030 máy chủ AI trên node có GPU: Ubuntu 24.04 + driver NVIDIA + PyTorch CUDA; GPU chỉ gắn vào máy khách khi thuê gói GPU
set -euo pipefail
VMID=9030; TMP=9039; IP=${1:-10.20.20.240}; GW=${2:-10.20.20.1}; STORAGE=${3:-local}; BRIDGE=${4:-vpsnet0}
DIR=/var/lib/vz/template/os; mkdir -p "$DIR"; cd "$DIR"
GOC=https://cloud-images.ubuntu.com/noble/current; TEP=noble-server-cloudimg-amd64.img
curl -fsSL -o "$TEP" "$GOC/$TEP"; curl -fsSL -o ai.sums "$GOC/SHA256SUMS"
[ "$(grep -E "\*?$TEP\$" ai.sums | cut -d' ' -f1)" = "$(sha256sum "$TEP" | cut -d' ' -f1)" ] || { echo "SHA256 sai" >&2; exit 3; }
qm create $TMP --name dung-ai --machine q35 --bios ovmf --efidisk0 "$STORAGE:1,efitype=4m,pre-enrolled-keys=0" --memory 8192 --cores 8 --cpu host --ostype l26 \
  --net0 "virtio,bridge=$BRIDGE" --scsihw virtio-scsi-single --serial0 socket --vga serial0 --agent enabled=1
qm importdisk $TMP "$TEP" "$STORAGE" --format raw >/dev/null
qm set $TMP --scsi0 "$(qm config $TMP | awk -F': ' '/^unused0/{print $2}'),discard=on" --boot order=scsi0 --ide2 "$STORAGE:cloudinit" \
  --ciuser tbtthu --sshkeys /root/.ssh/id_rsa.pub --ipconfig0 "ip=$IP/24,gw=$GW" --nameserver 1.1.1.1 >/dev/null
qm resize $TMP scsi0 30G >/dev/null
qm start $TMP
O="-o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5"
for i in $(seq 1 60); do ssh $O tbtthu@$IP true 2>/dev/null && break; sleep 5; done
scp $O -q /root/cai_ai.sh tbtthu@$IP:/tmp/
ssh $O tbtthu@$IP "sudo bash /tmp/cai_ai.sh" || true
for i in $(seq 1 60); do qm status $TMP | grep -q stopped && break; sleep 5; done
qm status $TMP | grep -q stopped || { echo "may dung chua tat" >&2; exit 4; }
qm clone $TMP $VMID --name tpl-ai-ubuntu2404 --full 1 >/dev/null
qm set $VMID --description "Ubuntu 24.04 + NVIDIA + PyTorch CUDA (may chu AI)" --memory 4096 --cores 2 --ipconfig0 ip=dhcp --delete ciuser,sshkeys,nameserver >/dev/null
qm template $VMID
qm destroy $TMP --purge >/dev/null
rm -f "$TEP" ai.sums
echo "XONG $VMID"
