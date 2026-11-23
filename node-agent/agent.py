# Nguyễn Tâm Bình - 2324801030003
import asyncio
import ipaddress
import json
import logging
import os
import re
import shlex
import signal
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("node-agent")
CHAIN = "VPS_SSH"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("API không được chuyển hướng yêu cầu xác thực.")


def private_host(host):
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def fetch_ports(api_url, token, node, scope="node"):
    parsed = urllib.parse.urlsplit(api_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("API_URL phải là địa chỉ HTTP(S) hợp lệ.")
    if parsed.scheme == "http" and not private_host(parsed.hostname):
        raise ValueError("HTTP chỉ dùng cho địa chỉ API trong mạng nội bộ.")
    base = api_url.rstrip("/")
    endpoint = base + ("/agent/ports" if base.endswith("/api/v1") else "/api/v1/agent/ports")
    request = urllib.request.Request(endpoint + "?" + urllib.parse.urlencode({"node": node, **({"scope": "all"} if scope == "all" else {})}), headers={"X-Agent-Token": token})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
        data = response.read(2097153)
    if len(data) > 2097152:
        raise ValueError("Danh sách cổng vượt giới hạn.")
    rows = json.loads(data)
    if not isinstance(rows, list):
        raise ValueError("Danh sách cổng không hợp lệ.")
    ports = {}
    for row in rows:
        port, vmid = row["ssh_port"], row["vmid"]
        target_port = row.get("target_port", 22)
        if type(target_port) is not int or target_port not in {22, 80, 3389, 5432}:
            raise ValueError("Cổng đích của dịch vụ không hợp lệ.")
        address = ipaddress.ip_address(row["ip"])
        if type(port) is not int or not 1024 <= port <= 65535 or type(vmid) is not int or vmid < 100 or address.version != 4 or address.is_loopback or address.is_unspecified or address.is_multicast or port in ports:
            raise ValueError("Thông tin ánh xạ cổng không hợp lệ.")
        ports[port] = (str(address), target_port)
    return ports


def api_endpoint(api_url, path):
    parsed = urllib.parse.urlsplit(api_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("API_URL phải là địa chỉ HTTP(S) hợp lệ.")
    if parsed.scheme == "http" and not private_host(parsed.hostname):
        raise ValueError("HTTP chỉ dùng cho địa chỉ API trong mạng nội bộ.")
    base = api_url.rstrip("/")
    return base + (path if base.endswith("/api/v1") else "/api/v1" + path)


class IPv6Routes:
    # Mỗi VPS một IPv6 công cộng trong prefix /64 của WAN: route /128 vào bridge VPS, node trả lời NDP thay VPS
    GATEWAY = "fe80::1/64"

    def __init__(self, wan, bridge):
        for name in (wan, bridge):
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", name):
                raise ValueError("Giao diện mạng không hợp lệ.")
        self.wan, self.bridge = wan, bridge

    def ip(self, *args, check=True):
        result = subprocess.run(["ip", "-6", *args], capture_output=True, text=True, timeout=15)
        if check and result.returncode != 0:
            raise RuntimeError("Chưa thể đồng bộ định tuyến IPv6.")
        return result

    def prefix(self):
        rows = json.loads(self.ip("-j", "addr", "show", "dev", self.wan, "scope", "global").stdout or "[]")
        for row in rows:
            for item in row.get("addr_info", []):
                if item.get("family") == "inet6" and item.get("prefixlen") == 64 and not item.get("temporary") and not item.get("deprecated"):
                    network = ipaddress.IPv6Network(f"{item['local']}/64", strict=False)
                    if network.is_global:
                        return str(network)
        return None

    def report(self, api_url, token, node, prefix):
        body = json.dumps({"prefix": prefix}).encode()
        request = urllib.request.Request(api_url_ipv6(api_url) + "?" + urllib.parse.urlencode({"node": node}), data=body, method="POST", headers={"X-Agent-Token": token, "Content-Type": "application/json"})
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
            rows = json.loads(response.read(262145))
        if not isinstance(rows, list):
            raise ValueError("Danh sách IPv6 không hợp lệ.")
        network = ipaddress.IPv6Network(prefix) if prefix else None
        return {str(ipaddress.IPv6Address(row["ipv6"])) for row in rows if network and ipaddress.IPv6Address(row["ipv6"]) in network}

    def sync(self, addresses):
        self.ip("addr", "replace", self.GATEWAY, "dev", self.bridge, "nodad")
        routes = {row["dst"] for row in json.loads(self.ip("-j", "route", "show", "dev", self.bridge, "proto", "static").stdout or "[]") if row.get("dst", "").count(":") >= 2 and "/" not in row.get("dst", "")}
        proxies = {row["dst"] for row in json.loads(self.ip("-j", "neigh", "show", "proxy", "dev", self.wan).stdout or "[]") if "dst" in row}
        for address in routes - addresses:
            self.ip("route", "del", f"{address}/128", "dev", self.bridge, check=False)
        for address in proxies - addresses:
            self.ip("neigh", "del", "proxy", address, "dev", self.wan, check=False)
        for address in addresses:
            self.ip("route", "replace", f"{address}/128", "dev", self.bridge, "proto", "static")
            self.ip("neigh", "replace", "proxy", address, "dev", self.wan)


def api_url_ipv6(api_url):
    return api_endpoint(api_url, "/agent/ipv6")


class NatRules:
    def __init__(self, interface, mesh_interface=None):
        for name in filter(None, (interface, mesh_interface)):
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", name):
                raise ValueError("Giao diện mạng không hợp lệ.")
        self.interface = interface
        self.mesh_interface = mesh_interface

    def run(self, *args, check=True):
        result = subprocess.run(["iptables", "-w", "5", "-t", "nat", *args], capture_output=True, text=True, timeout=15)
        if check and result.returncode != 0:
            raise RuntimeError("Chưa thể đồng bộ luật chuyển cổng SSH.")
        return result

    def sync(self, ports):
        current = self.run("-S", CHAIN, check=False)
        if current.returncode != 0:
            self.run("-N", CHAIN)
            current = self.run("-S", CHAIN)
        jump = ("-i", self.interface, "-p", "tcp", "-j", CHAIN)
        if self.run("-C", "PREROUTING", *jump, check=False).returncode != 0:
            self.run("-A", "PREROUTING", *jump)
        if self.mesh_interface:
            # VPS ở node khác trả lời qua mesh nên đổi nguồn thành địa chỉ mesh của node biên
            masquerade = ("-o", self.mesh_interface, "-m", "conntrack", "--ctstate", "DNAT", "-j", "MASQUERADE")
            if self.run("-C", "POSTROUTING", *masquerade, check=False).returncode != 0:
                self.run("-A", "POSTROUTING", *masquerade)
        rules = [tuple(shlex.split(line)[2:]) for line in current.stdout.splitlines() if line.startswith(f"-A {CHAIN} ")]
        desired = [("-p", "tcp", "-m", "tcp", "--dport", str(port), "-j", "DNAT", "--to-destination", f"{ip}:{target_port}") for port, (ip, target_port) in sorted(ports.items())]
        remaining = list(desired)
        for rule in rules:
            if rule in remaining:
                remaining.remove(rule)
            else:
                self.run("-D", CHAIN, *rule)
        for rule in remaining:
            self.run("-A", CHAIN, *rule)


class IPv6Listeners:
    def __init__(self):
        self.servers = {}
        self.connections = {}

    async def forward(self, port, ip, reader, writer, target_port=22):
        task = asyncio.current_task()
        self.connections.setdefault(port, set()).add(task)
        remote = None
        pumps = []
        try:
            upstream_reader, remote = await asyncio.wait_for(asyncio.open_connection(ip, target_port), timeout=10)

            async def pump(source, target):
                while True:
                    data = await source.read(65536)
                    if not data:
                        if target.can_write_eof():
                            target.write_eof()
                        return
                    target.write(data)
                    await target.drain()

            pumps = [asyncio.create_task(pump(reader, remote)), asyncio.create_task(pump(upstream_reader, writer))]
            await asyncio.gather(*pumps)
        except (OSError, asyncio.TimeoutError):
            pass
        finally:
            for pending in pumps:
                pending.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)
            for stream in (writer, remote):
                if stream is not None:
                    stream.close()
                    try:
                        await stream.wait_closed()
                    except OSError:
                        pass
            self.connections.get(port, set()).discard(task)

    async def remove(self, port):
        destination, server = self.servers.pop(port)
        server.close()
        await server.wait_closed()
        tasks = list(self.connections.pop(port, set()))
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def sync(self, ports):
        for port, (destination, server) in list(self.servers.items()):
            if ports.get(port) != destination:
                await self.remove(port)
        for port, destination in sorted(ports.items()):
            if port in self.servers:
                continue
            listener = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            try:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                listener.setblocking(False)
                listener.bind(("::", port))
                server = await asyncio.start_server(lambda reader, writer, p=port, target=destination: self.forward(p, target[0], reader, writer, target[1]), sock=listener)
            except BaseException:
                listener.close()
                raise
            self.servers[port] = (destination, server)


async def run_agent():
    api_url = os.environ["API_URL"]
    token = os.environ["AGENT_TOKEN"]
    node = os.environ["NODE_NAME"]
    if len(token.encode()) < 32 or not node:
        raise ValueError("Cần AGENT_TOKEN ít nhất 32 byte và NODE_NAME.")
    scope = os.environ.get("PORTS_SCOPE", "node")
    if scope not in {"node", "all"}:
        raise ValueError("PORTS_SCOPE chỉ nhận node hoặc all.")
    nat = NatRules(os.environ.get("WAN_IFACE", "wlo1"), os.environ.get("MESH_IFACE") if scope == "all" else None)
    listeners = IPv6Listeners()
    ipv6 = IPv6Routes(os.environ.get("WAN_IFACE", "wlo1"), os.environ["VPS_IPV6_BRIDGE"]) if os.environ.get("VPS_IPV6_BRIDGE") else None
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopping.set)
    try:
        while not stopping.is_set():
            try:
                ports = await asyncio.to_thread(fetch_ports, api_url, token, node, scope)
                await asyncio.to_thread(nat.sync, ports)
                await listeners.sync(ports)
            except Exception:
                logger.error("Chưa đồng bộ được cổng SSH; sẽ thử lại sau 30 giây.")
            if ipv6:
                try:
                    prefix = await asyncio.to_thread(ipv6.prefix)
                    addresses = await asyncio.to_thread(ipv6.report, api_url, token, node, prefix)
                    await asyncio.to_thread(ipv6.sync, addresses)
                except Exception:
                    logger.error("Chưa đồng bộ được IPv6 của VPS; sẽ thử lại sau 30 giây.")
            try:
                await asyncio.wait_for(stopping.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
    finally:
        await listeners.sync({})
        try:
            await asyncio.to_thread(nat.sync, {})
        except Exception:
            logger.error("Chưa thu hồi được luật chuyển cổng SSH.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        asyncio.run(run_agent())
    except Exception:
        logger.error("Node-agent chưa thể khởi động. Vui lòng kiểm tra cấu hình.")
        raise SystemExit(1) from None
