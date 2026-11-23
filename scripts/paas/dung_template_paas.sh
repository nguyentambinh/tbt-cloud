#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Dựng template PaaS (VMID 9001) từ template Debian 13 cloud (9000) trên node Proxmox.
# Dùng: dung_template_paas.sh <thư mục chứa tbt-paas và tbt-paas.service>
set -euo pipefail
SRC=$1; ID=9001; KEY=/root/.ssh/id_rsa.pub
qm status $ID >/dev/null 2>&1 && { qm stop $ID >/dev/null 2>&1 || true; qm destroy $ID --purge >/dev/null; }
qm clone 9000 $ID --name tpl-paas --full 1 --storage local >/dev/null
qm set $ID --memory 2048 --cores 2 --ciuser root --sshkeys $KEY --ipconfig0 ip=dhcp --description "Debian 13 PaaS (PostgreSQL 17, nginx, Node.js)" >/dev/null
qm resize $ID scsi0 8G >/dev/null
qm start $ID
IP=""
for i in $(seq 1 60); do
  IP=$(pvesh get /cluster/sdn/ipams/pve/status --output-format json | python3 -c "import json,sys; print(next((r['ip'] for r in json.load(sys.stdin) if str(r.get('vmid'))=='$ID'), ''))")
  [ -n "$IP" ] && ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=5 root@$IP true 2>/dev/null && break
  sleep 5
done
echo "ip=$IP"
S="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes root@$IP"
scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $SRC/tbt-paas root@$IP:/usr/local/sbin/tbt-paas
scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $SRC/tbt-paas.service root@$IP:/etc/systemd/system/tbt-paas.service
$S 'set -e; cloud-init status --wait >/dev/null || true; export DEBIAN_FRONTEND=noninteractive; apt-get update -q; apt-get install -y -q postgresql nginx nodejs npm git qemu-guest-agent >/dev/null; systemctl disable --now postgresql nginx; chmod 755 /usr/local/sbin/tbt-paas; systemctl daemon-reload; systemctl enable tbt-paas; apt-get clean; rm -rf /var/lib/tbt-paas /var/log/tbt-paas.log; cloud-init clean --logs --seed; rm -f /root/.ssh/authorized_keys /etc/ssh/ssh_host_*; truncate -s 0 /etc/machine-id; psql --version; nginx -v; node --version; git --version; sync'
qm shutdown $ID --timeout 120
qm set $ID --delete sshkeys >/dev/null; qm set $ID --ciuser debian >/dev/null
qm template $ID
qm config $ID | grep -E "template|description|scsi0"
echo TEMPLATE-PAAS-XONG
