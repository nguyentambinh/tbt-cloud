#!/bin/bash
# Nguyễn Tâm Bình - 2324801030003
# Ubuntu 26.04: đặt tên card eth0 ngay từ kernel để cloud-init áp IP tĩnh mà không phải đổi tên card đang bận
set -e
cat > /etc/default/grub.d/99-tbt-ifnames.cfg <<'C'
GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT net.ifnames=0 biosdevname=0"
C
update-grub
grep -o 'linux.*vmlinuz[^\n]*' /boot/grub/grub.cfg | head -1
cloud-init clean --logs --machine-id --seed
rm -f /etc/ssh/ssh_host_*
systemd-run --on-active=3 sh -c "userdel -rf tbtthu; truncate -s0 /etc/machine-id; poweroff"
