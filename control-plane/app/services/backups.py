# Nguyễn Tâm Bình - 2324801030003
import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.engine import make_url

from app.config import get_settings

NAME = re.compile(r"^[0-9]{8}T[0-9]{12}-[a-f0-9]{32}\.dump$")


def root():
    directory = Path(get_settings().backup_dir)
    if directory.is_symlink():
        raise HTTPException(status_code=503, detail="Thư mục sao lưu chưa an toàn. Hãy kiểm tra cấu hình.")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory.resolve()


@contextmanager
def operation():
    lock = root() / ".operation.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Một thao tác sao lưu hoặc khôi phục đang chạy. Hãy chờ rồi tải lại.") from None
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)


def backup_path(name):
    if not NAME.fullmatch(name):
        raise HTTPException(status_code=404, detail="Không tìm thấy bản sao lưu.")
    path = root() / name
    metadata = path.with_suffix(".json")
    if path.is_symlink() or metadata.is_symlink() or not path.is_file() or not metadata.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy bản sao lưu.")
    return path


def listing():
    items = []
    for path in root().glob("*.dump"):
        if not NAME.fullmatch(path.name) or path.is_symlink():
            continue
        metadata = path.with_suffix(".json")
        try:
            if metadata.is_symlink() or metadata.stat().st_size > 4096:
                continue
            data = json.loads(metadata.read_text(encoding="utf-8"))
            items.append({"name": path.name, "created_at": data["created_at"], "created_by": data["created_by"], "size": path.stat().st_size, "safety": data.get("safety", False)})
        except (OSError, ValueError, KeyError):
            continue
    return sorted(items, key=lambda row: row["name"], reverse=True)


def run_postgres(command, path):
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "postgresql" or not url.database:
        raise HTTPException(status_code=503, detail="Sao lưu và khôi phục chỉ khả dụng khi cấu hình PostgreSQL.")
    from urllib.parse import quote
    host = url.host or "localhost"
    host = f"[{host}]" if ":" in host else host
    connection = f"postgresql://{quote(url.username or '', safe='')}@{host}:{url.port or 5432}/{quote(url.database, safe='')}"
    args = [command, f"--dbname={connection}", "--no-password"]
    args += ["--format=custom", f"--file={path}"] if command == "pg_dump" else ["--clean", "--if-exists", "--exit-on-error", "--single-transaction", str(path)]
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP") if key in os.environ}
    env.update({"PGPASSWORD": url.password or "", "PGCONNECT_TIMEOUT": "10", "PGSSLMODE": url.query.get("sslmode", "prefer")})
    try:
        subprocess.run(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=get_settings().backup_timeout, shell=False)
    except (OSError, subprocess.SubprocessError):
        raise HTTPException(status_code=503, detail="Chưa hoàn tất thao tác CSDL. Hãy kiểm tra quyền thư mục và công cụ PostgreSQL trên máy chủ.") from None


def create(actor_id, safety=False):
    now = datetime.now(timezone.utc)
    name = now.strftime("%Y%m%dT%H%M%S%f") + "-" + uuid4().hex + ".dump"
    path = root() / name
    metadata = path.with_suffix(".json")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        run_postgres("pg_dump", path)
        if path.stat().st_size == 0:
            raise HTTPException(status_code=503, detail="Bản sao lưu rỗng. Chưa thể dùng để khôi phục.")
        with metadata.open("x", encoding="utf-8") as stream:
            json.dump({"created_at": now.isoformat(), "created_by": actor_id, "safety": safety}, stream)
        os.chmod(metadata, 0o600)
    except Exception:
        path.unlink(missing_ok=True)
        metadata.unlink(missing_ok=True)
        raise
    return next(row for row in listing() if row["name"] == name)


def prune(protected=()):
    rows = listing()
    remaining = len(rows)
    removed = []
    for row in reversed(rows):
        if remaining <= get_settings().backup_keep:
            break
        if row["name"] in protected:
            continue
        remove(row["name"])
        removed.append(row["name"])
        remaining -= 1
    return removed


def remove(name):
    path = backup_path(name)
    path.unlink()
    path.with_suffix(".json").unlink()


def invalidate_sessions():
    path = root() / ".auth-epoch"
    if path.is_symlink():
        raise HTTPException(status_code=503, detail="Chưa thể thu hồi phiên đăng nhập. Hãy kiểm tra thư mục sao lưu.")
    temporary = root() / (".auth-" + uuid4().hex)
    temporary.write_text(str(int(time.time())), encoding="ascii")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
