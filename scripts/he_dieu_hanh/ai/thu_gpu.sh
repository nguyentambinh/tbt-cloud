#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Thử máy chủ AI: clone template, gắn GPU qua hostpci, kiểm nvidia-smi và PyTorch chạy trên GPU, rồi xóa máy thử
set -u
TPL=${1:-9030}; VMID=${2:-981}; IP=${3:-10.20.20.241}; GPU=${4:-0000:01:00}
qm clone $TPL $VMID --name thu-gpu >/dev/null
qm set $VMID --hostpci0 "$GPU,pcie=1" --memory 8192 --cores 8 --ciuser tbtthu --sshkeys /root/.ssh/id_rsa.pub --ipconfig0 "ip=$IP/24,gw=10.20.20.1" --nameserver 1.1.1.1 >/dev/null
qm resize $VMID scsi0 40G >/dev/null
qm start $VMID; T0=$(date +%s)
O="-o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5"
for i in $(seq 1 60); do ssh $O tbtthu@$IP true 2>/dev/null && break; sleep 5; done
echo "SSH sau $(( $(date +%s)-T0 ))s"
ssh $O tbtthu@$IP 'nvidia-smi --query-gpu=name,driver_version,memory.total,temperature.gpu --format=csv,noheader; /opt/ai/bin/python - <<P
import torch, time
print("cuda:", torch.cuda.is_available(), torch.cuda.get_device_name(0))
a = torch.randn(8192, 8192, device="cuda", dtype=torch.float16); b = torch.randn(8192, 8192, device="cuda", dtype=torch.float16)
torch.cuda.synchronize(); t = time.time()
for _ in range(50): c = a @ b
torch.cuda.synchronize(); dt = time.time() - t
print("nhan ma tran fp16 8192x8192 x50: %.2fs ~ %.1f TFLOPS" % (dt, 50 * 2 * 8192**3 / dt / 1e12))
x = torch.randn(4096, 4096); t = time.time(); [x @ x for _ in range(5)]; print("CPU fp32 4096 x5: %.2fs" % (time.time() - t))
P'
qm stop $VMID >/dev/null; qm destroy $VMID --purge >/dev/null; echo "da xoa may thu"
