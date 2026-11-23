# Nguyễn Tâm Bình - 2324801030003
import asyncio
import os
import ssl
from urllib.parse import quote, urlencode, urlsplit

import anyio
from fastapi import HTTPException, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool
from websockets.asyncio.client import connect

from app.config import get_settings
from app.dependencies import current_user
from app.models import AuditLog
from app.security import decrypt_secret
from app.services.instances import owned_instance
from app.services.proxmox_client import ProxmoxClient


def prepare_console(db, instance_id, token):
    user = current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db)
    instance = owned_instance(db, instance_id, user)
    if instance.loai != "vm":
        raise HTTPException(status_code=400, detail="Console web cho LXC hiện chưa được hỗ trợ.")
    if instance.trang_thai != "running":
        raise HTTPException(status_code=409, detail="Chỉ có thể mở console khi máy chủ đang chạy.")
    client = ProxmoxClient(instance.node)
    if client.get_status(instance.vmid, instance.loai) != "running":
        raise HTTPException(status_code=409, detail="Chỉ có thể mở console khi máy chủ đang chạy.")
    proxy = client.termproxy(instance.vmid)
    port = int(proxy["port"])
    if not 1 <= port <= 65535:
        raise ValueError("Cổng console không hợp lệ.")
    node = instance.node
    parsed = urlsplit(node.api_url)
    query = urlencode({"port": port, "vncticket": proxy["ticket"]})
    uri = f"wss://{parsed.netloc}/api2/json/nodes/{quote(node.proxmox_node, safe='')}/qemu/{instance.vmid}/vncwebsocket?{query}"
    authorization = f"PVEAPIToken={node.token_id}={decrypt_secret(node.token_secret)}"
    login = f"{proxy.get('user', node.token_id.split('!')[0])}:{proxy['ticket']}\n"
    db.add(AuditLog(user_id=user.id, action="instance.console", resource=f"instance:{instance.id}"))
    db.commit()
    return uri, authorization, login


def console_tls():
    value = get_settings().proxmox_verify_ssl.strip()
    if value.lower() == "false":
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    cafile = (os.environ.get("REQUESTS_CA_BUNDLE") or None) if value.lower() == "true" else value
    return ssl.create_default_context(cafile=cafile)


async def relay_console(websocket, upstream):
    async def to_proxmox():
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            data = message.get("text") if message.get("text") is not None else message.get("bytes")
            if data is not None:
                await upstream.send(data)

    async def to_client():
        async for data in upstream:
            if isinstance(data, bytes):
                await websocket.send_bytes(data)
            else:
                await websocket.send_text(data)

    tasks = [asyncio.create_task(to_proxmox()), asyncio.create_task(to_client())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        with anyio.CancelScope(shield=True):
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


async def open_console(websocket, db, instance_id, token):
    try:
        if not token:
            raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.")
        uri, authorization, login = await run_in_threadpool(prepare_console, db, instance_id, token)
    except HTTPException as error:
        await websocket.close(code=1008 if error.status_code < 500 else 1011, reason=error.detail)
        return
    except Exception:
        await websocket.close(code=1011, reason="Chưa thể mở console. Vui lòng thử lại.")
        return
    await websocket.accept()
    try:
        async with connect(uri, additional_headers={"Authorization": authorization}, ssl=console_tls(), proxy=None, open_timeout=get_settings().proxmox_timeout, close_timeout=3, max_size=1048576) as upstream:
            await upstream.send(login)
            acknowledgement = await asyncio.wait_for(upstream.recv(), timeout=get_settings().proxmox_timeout)
            if acknowledgement not in {"OK", b"OK"}:
                raise ValueError("Node chưa xác nhận console.")
            await relay_console(websocket, upstream)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011, reason="Kết nối console bị gián đoạn. Vui lòng thử lại.")
        except (RuntimeError, WebSocketDisconnect):
            pass
        return
    try:
        await websocket.close(code=1000)
    except (RuntimeError, WebSocketDisconnect):
        pass
