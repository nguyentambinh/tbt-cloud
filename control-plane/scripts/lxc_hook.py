# Nguyễn Tâm Bình - 2324801030003
import json
import subprocess
import sys


def main():
    vmid, phase = sys.argv[1:3]
    if phase != "post-start":
        return
    if not vmid.isdigit():
        raise ValueError("VMID không hợp lệ.")
    result = subprocess.run(["pct", "config", vmid], check=True, capture_output=True, text=True, timeout=15)
    description = next((line.removeprefix("description: ") for line in result.stdout.splitlines() if line.startswith("description: control-plane:")), None)
    if description is None:
        return
    payload = json.loads(description.removeprefix("control-plane:"))
    if payload["cloud_user"] != "root":
        raise ValueError("Tài khoản LXC không được hỗ trợ.")
    key = payload["ssh_public_key"]
    if not key.startswith(("ssh-", "ecdsa-")) or "\n" in key or "\r" in key or len(key) > 8192:
        raise ValueError("Khóa SSH không hợp lệ.")
    script = "import os,pathlib,sys; p=pathlib.Path('/root/.ssh'); p.mkdir(mode=0o700,exist_ok=True); os.chmod(p,0o700); f=p/'authorized_keys'; f.unlink(missing_ok=True); f.write_text(sys.argv[1]+'\\n'); os.chmod(f,0o600)"
    subprocess.run(["pct", "exec", vmid, "--", "python3", "-c", script, key], check=True, timeout=30)


if __name__ == "__main__":
    main()
