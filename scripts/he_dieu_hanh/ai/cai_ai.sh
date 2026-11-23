#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Cài môi trường train AI trong VM Ubuntu 24.04: driver NVIDIA bản mở, PyTorch CUDA, JupyterLab; dọn cloud-init để đóng template
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
cloud-init status --wait >/dev/null || true
apt-get update -q
DRV=$(apt-cache search --names-only '^nvidia-driver-[0-9]+-open$' | awk '{print $1}' | sort -t- -k3 -n | tail -1)
echo "driver: $DRV"
apt-get install -y -q --no-install-recommends "$DRV" "nvidia-utils-$(echo "${DRV#nvidia-driver-}" | sed "s/-open$//")" python3-venv python3-pip build-essential git htop nvtop tmux
python3 -m venv /opt/ai
/opt/ai/bin/pip install -q --upgrade pip
/opt/ai/bin/pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
/opt/ai/bin/pip install -q jupyterlab numpy pandas scikit-learn matplotlib transformers datasets accelerate
cat > /etc/profile.d/tbt-ai.sh <<'P'
export PATH=/opt/ai/bin:$PATH
P
cat > /etc/update-motd.d/60-tbt-ai <<'M'
#!/bin/sh
echo ""
echo " TBT Cloud - May chu AI (GPU NVIDIA RTX 5060 8 GB)"
echo "  nvidia-smi                          xem GPU"
echo "  python -c 'import torch; print(torch.cuda.is_available())'"
echo "  jupyter lab --no-browser --port 8888 roi mo duong ham: ssh -L 8888:localhost:8888 ..."
echo ""
M
chmod +x /etc/update-motd.d/60-tbt-ai
/opt/ai/bin/python -c "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda)"
apt-get clean
cloud-init clean --logs --machine-id --seed
rm -f /etc/ssh/ssh_host_*
systemd-run --on-active=3 sh -c "userdel -rf tbtthu; truncate -s0 /etc/machine-id; poweroff"
