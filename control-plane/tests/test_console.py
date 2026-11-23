# Nguyễn Tâm Bình - 2324801030003
import asyncio
import ssl
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from starlette.websockets import WebSocketDisconnect

from app.config import get_settings
from app.security import create_access_token
from app.services.console import console_tls


class FakeUpstream:
    def __init__(self):
        self.messages = []
        self.queue = asyncio.Queue()
        self.closed = False
        self.recv = AsyncMock(return_value="OK")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def send(self, data):
        self.messages.append(data)
        if len(self.messages) > 1:
            await self.queue.put(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        data = await self.queue.get()
        if data is None:
            raise StopAsyncIteration
        return data


@pytest.fixture
def console_mock(monkeypatch, mock_proxmox):
    factory, proxmox = mock_proxmox
    monkeypatch.setattr("app.services.console.ProxmoxClient", factory)
    proxmox.termproxy.return_value = {"port": 5900, "ticket": "test-ticket+/=", "user": "cloud@pve"}
    upstream = FakeUpstream()
    connect = MagicMock(return_value=upstream)
    monkeypatch.setattr("app.services.console.connect", connect)
    return proxmox, upstream, connect


@pytest.mark.parametrize("role", ["user", "admin"])
def test_console_auth_termproxy_and_bidirectional_relay(client, seed, instance, console_mock, role):
    proxmox, upstream, connect = console_mock
    token = create_access_token(seed[role].id)
    with client.websocket_connect(f"/api/v1/instances/{instance.id}/console?token={token}") as websocket:
        websocket.send_text("0:4:ls\r\n")
        assert websocket.receive_text() == "0:4:ls\r\n"
        websocket.send_text("1:100:30:")
        assert websocket.receive_text() == "1:100:30:"
        websocket.send_bytes(b"0:1:a")
        assert websocket.receive_bytes() == b"0:1:a"
    proxmox.termproxy.assert_called_once_with(instance.vmid)
    uri = urlsplit(connect.call_args.args[0])
    assert uri.scheme == "wss" and uri.netloc == "100.64.0.1:8006"
    assert uri.path == f"/api2/json/nodes/pve/qemu/{instance.vmid}/vncwebsocket"
    assert parse_qs(uri.query) == {"port": ["5900"], "vncticket": ["test-ticket+/="]}
    assert connect.call_args.kwargs["additional_headers"] == {"Authorization": "PVEAPIToken=cloud@pve!control=dummy-token"}
    assert connect.call_args.kwargs["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert upstream.messages[0] == "cloud@pve:test-ticket+/=\n"
    assert upstream.closed


@pytest.mark.parametrize("kind", ["missing", "invalid", "expired", "other", "nonexistent", "wrong-type"])
def test_console_rejects_bad_identity_before_upstream(client, seed, instance, console_mock, kind):
    proxmox, upstream, connect = console_mock
    settings = get_settings()
    token = create_access_token(seed["other"].id) if kind == "other" else "invalid-token"
    if kind in {"expired", "wrong-type", "nonexistent"}:
        now = datetime.now(timezone.utc)
        token = jwt.encode({"sub": str(99999 if kind == "nonexistent" else seed["user"].id), "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1) if kind == "expired" else now + timedelta(hours=1), "iss": settings.jwt_issuer, "type": "refresh" if kind == "wrong-type" else "access"}, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    suffix = "" if kind == "missing" else f"?token={token}"
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/api/v1/instances/{instance.id}/console{suffix}"):
            pass
    assert error.value.code == 1008
    connect.assert_not_called()
    proxmox.termproxy.assert_not_called()


@pytest.mark.parametrize("state, actual, loai", [("stopped", "stopped", "vm"), ("running", "stopped", "vm"), ("suspended", "running", "vm"), ("running", "running", "lxc")])
def test_console_rejects_nonrunning_and_lxc(client, db, seed, instance, console_mock, state, actual, loai):
    proxmox, upstream, connect = console_mock
    instance.trang_thai, instance.loai = state, loai
    db.commit()
    proxmox.get_status.return_value = actual
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/api/v1/instances/{instance.id}/console?token={create_access_token(seed['user'].id)}"):
            pass
    assert error.value.code == 1008
    proxmox.termproxy.assert_not_called()


def test_console_upstream_failure_hides_secrets(client, seed, instance, console_mock):
    proxmox, upstream, connect = console_mock
    connect.side_effect = OSError("dummy-token secret-ticket")
    with client.websocket_connect(f"/api/v1/instances/{instance.id}/console?token={create_access_token(seed['user'].id)}") as websocket:
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_text()
    assert error.value.code == 1011
    assert "dummy-token" not in error.value.reason and "secret-ticket" not in error.value.reason


def test_console_requires_login_acknowledgement(client, seed, instance, console_mock):
    proxmox, upstream, connect = console_mock
    upstream.recv.return_value = "ticket-secret DENIED"
    with client.websocket_connect(f"/api/v1/instances/{instance.id}/console?token={create_access_token(seed['user'].id)}") as websocket:
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_text()
    assert error.value.code == 1011 and "ticket-secret" not in error.value.reason and upstream.closed


def test_console_upstream_disconnect_closes_client(client, seed, instance, console_mock):
    proxmox, upstream, connect = console_mock
    upstream.queue.put_nowait(None)
    with client.websocket_connect(f"/api/v1/instances/{instance.id}/console?token={create_access_token(seed['user'].id)}") as websocket:
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_text()
    assert error.value.code == 1000 and upstream.closed


def test_console_tls_false_and_custom_ca(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "proxmox_verify_ssl", "false")
    assert console_tls().verify_mode == ssl.CERT_NONE and not console_tls().check_hostname
    create_context = MagicMock(return_value="context")
    monkeypatch.setattr("app.services.console.ssl.create_default_context", create_context)
    monkeypatch.setattr(settings, "proxmox_verify_ssl", "/private/node-ca.pem")
    assert console_tls() == "context"
    create_context.assert_called_once_with(cafile="/private/node-ca.pem")
