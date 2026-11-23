# Nguyễn Tâm Bình - 2324801030003
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_node_map_admin_only(client, headers, seed):
    assert client.get("/api/v1/public/map").status_code == 404
    assert client.get("/api/v1/nodes/map").status_code == 401
    assert client.get("/api/v1/nodes/map", headers=headers["user"]).status_code == 403
    result = client.get("/api/v1/nodes/map", headers=headers["admin"])
    assert result.status_code == 200 and result.json()[0]["online"] is True
    assert set(result.json()[0]) == {"id", "ten", "proxmox_node", "online", "last_seen_at", "total_vcpu", "total_ram_mb", "total_disk_gb", "used_vcpu", "used_ram_mb", "used_disk_gb"}
    for secret in ("api_url", "token", "mesh_ip", "100.64.0.1", "dummy-token"):
        assert secret not in result.text
    assert client.get("/api/v1/plans").status_code == 200
    assert client.post("/api/v1/plans", json={}).status_code == 401


@pytest.mark.parametrize("state,age,expected", [("online", 121, False), ("offline", 1, False), ("online", None, False), ("online", 30, True), ("online", -30, False)])
def test_map_heartbeat(client, db, headers, seed, state, age, expected):
    node = seed["node"]
    node.trang_thai = state
    node.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=age) if age is not None else None
    db.commit()
    assert client.get("/api/v1/nodes/map", headers=headers["admin"]).json()[0]["online"] is expected


def test_spa_assets_fallback_and_boundaries(tmp_path, monkeypatch):
    root = tmp_path / "web"
    root.mkdir()
    (root / "index.html").write_text("<html>TBT Cloud</html>", encoding="utf-8")
    (root / "main.dart.js").write_text("void 0", encoding="utf-8")
    (root / ".env").write_text("hidden", encoding="utf-8")
    monkeypatch.setattr(get_settings(), "web_dir", str(root))
    with TestClient(create_app()) as client:
        for path in ("/", "/may-chu/12", "/thanh-toan/ket-qua?orderCode=123"):
            response = client.get(path)
            assert response.status_code == 200
            assert "TBT Cloud" in response.text
            assert response.headers["cache-control"] == "no-cache"
        assert client.head("/may-chu").status_code == 200
        asset = client.get("/main.dart.js")
        assert asset.text == "void 0"
        assert asset.headers["cache-control"] == "no-cache"
        for path in ("/api/unknown", "/docs/unknown", "/openapi.json/unknown", "/redoc/unknown", "/health/unknown", "/.env", "/%2e%2e/private"):
            assert client.get(path).status_code == 404
        assert client.get("/health").json() == {"status": "ok"}
        assert "openapi" in client.get("/openapi.json").json()


def test_spa_is_disabled_by_default(client):
    assert client.get("/may-chu").status_code == 404


def test_spa_rejects_missing_build(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "web_dir", str(tmp_path))
    with pytest.raises(ValueError, match="WEB_DIR"):
        create_app()


def test_spa_blocks_symlink_escape(tmp_path, monkeypatch):
    root = tmp_path / "web"
    root.mkdir()
    (root / "index.html").write_text("index", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    try:
        (root / "escape.txt").symlink_to(secret)
    except OSError:
        pytest.skip("Hệ điều hành không cấp quyền tạo symlink.")
    monkeypatch.setattr(get_settings(), "web_dir", str(root))
    with TestClient(create_app()) as client:
        assert client.get("/escape.txt").status_code == 404


def test_spa_rejects_index_symlink_escape(tmp_path, monkeypatch):
    root = tmp_path / "web"
    root.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    try:
        (root / "index.html").symlink_to(secret)
    except OSError:
        pytest.skip("Hệ điều hành không cấp quyền tạo symlink.")
    monkeypatch.setattr(get_settings(), "web_dir", str(root))
    with pytest.raises(ValueError, match="WEB_DIR"):
        create_app()
