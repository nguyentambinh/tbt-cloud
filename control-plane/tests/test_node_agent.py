# Nguyễn Tâm Bình - 2324801030003
import asyncio
import importlib.util
import json
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

spec = importlib.util.spec_from_file_location("node_agent", Path(__file__).resolve().parents[2] / "node-agent" / "agent.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


def test_nat_only_changes_owned_rules(monkeypatch):
    rules = []
    commands = []
    state = {"chain": False, "jump": False}

    def run(command, **kwargs):
        assert command[:5] == ["iptables", "-w", "5", "-t", "nat"]
        assert kwargs["timeout"] == 15 and "shell" not in kwargs
        args = command[5:]
        commands.append(args)
        result = SimpleNamespace(returncode=0, stdout="")
        if args[0] == "-S":
            result.returncode = 0 if state["chain"] else 1
            result.stdout = "\n".join("-A VPS_SSH " + " ".join(rule) for rule in rules)
        elif args[0] == "-N":
            assert args[1] == "VPS_SSH"
            state["chain"] = True
        elif args[0] == "-C":
            result.returncode = 0 if state["jump"] else 1
        elif args[1] == "PREROUTING":
            assert args == ["-A", "PREROUTING", "-i", "wlo1", "-p", "tcp", "-j", "VPS_SSH"]
            state["jump"] = True
        elif args[0] == "-A":
            assert args[1] == "VPS_SSH"
            rules.append(tuple(args[2:]))
        elif args[0] == "-D":
            assert args[1] == "VPS_SSH"
            rules.remove(tuple(args[2:]))
        else:
            pytest.fail(str(args))
        return result

    monkeypatch.setattr(agent.subprocess, "run", run)
    nat = agent.NatRules("wlo1")
    nat.sync({22000: ("10.0.0.2", 22), 22001: ("10.0.0.3", 22)})
    assert len(rules) == 2 and state == {"chain": True, "jump": True}
    commands.clear()
    nat.sync({22000: ("10.0.0.2", 22), 22001: ("10.0.0.3", 22)})
    assert all(command[0] in {"-S", "-C"} for command in commands)
    commands.clear()
    nat.sync({22000: ("10.0.0.4", 22), 22001: ("10.0.0.3", 22)})
    mutations = [command for command in commands if command[0] in {"-A", "-D"}]
    assert len(mutations) == 2 and all("22000" in command for command in mutations)
    nat.sync({})
    assert rules == []


def test_nat_invalid_interface_and_safe_error(monkeypatch):
    with pytest.raises(ValueError):
        agent.NatRules("eth0;id")
    monkeypatch.setattr(agent.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="secret-error", stderr="secret-error"))
    with pytest.raises(RuntimeError) as error:
        agent.NatRules("eth0").sync({})
    assert "secret" not in str(error.value)


def test_fetch_ports_header_node_and_validated_data(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps([{"ssh_port": 22000, "ip": "10.0.0.2", "vmid": 101}]).encode()
    opener = MagicMock()
    opener.open.return_value = response
    monkeypatch.setattr(agent.urllib.request, "build_opener", MagicMock(return_value=opener))
    for base in ("https://control.example", "https://control.example/api/v1"):
        assert agent.fetch_ports(base, "fake-token", "pve node") == {22000: ("10.0.0.2", 22)}
        request = opener.open.call_args.args[0]
        assert request.full_url == "https://control.example/api/v1/agent/ports?node=pve+node"
        assert request.get_header("X-agent-token") == "fake-token"
        assert opener.open.call_args.kwargs["timeout"] == 10


@pytest.mark.parametrize("rows", [[{"ssh_port": 22, "ip": "10.0.0.2", "vmid": 101}], [{"ssh_port": "22000", "ip": "10.0.0.2", "vmid": 101}], [{"ssh_port": 22000, "ip": "::1", "vmid": 101}], [{"ssh_port": 22000, "ip": "127.0.0.1", "vmid": 101}], [{"ssh_port": 22000, "ip": "10.0.0.2", "vmid": 101}] * 2, {"detail": "error"}])
def test_fetch_rejects_invalid_maps(monkeypatch, rows):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(rows).encode()
    opener = MagicMock()
    opener.open.return_value = response
    monkeypatch.setattr(agent.urllib.request, "build_opener", lambda *args: opener)
    with pytest.raises(ValueError):
        agent.fetch_ports("https://control.example", "fake-token", "pve")


def test_no_redirect_or_cleartext_api():
    with pytest.raises(ValueError):
        agent.fetch_ports("http://control.example", "fake-token", "pve")
    with pytest.raises(ValueError):
        agent.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.example")


def test_ipv6_listener_sync_reuses_and_replaces_only_changed_ports(monkeypatch):
    async def scenario():
        sockets = []
        servers = []

        def make_socket(*args):
            value = MagicMock()
            sockets.append(value)
            return value

        async def start_server(callback, sock):
            value = MagicMock()
            value.wait_closed = AsyncMock()
            servers.append(value)
            return value

        monkeypatch.setattr(agent.socket, "socket", make_socket)
        monkeypatch.setattr(agent.asyncio, "start_server", start_server)
        listeners = agent.IPv6Listeners()
        await listeners.sync({22000: ("10.0.0.2", 22), 22001: ("10.0.0.3", 22)})
        sockets[0].bind.assert_called_once_with(("::", 22000))
        sockets[0].setsockopt.assert_any_call(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        await listeners.sync({22000: ("10.0.0.2", 22), 22001: ("10.0.0.3", 22)})
        assert len(servers) == 2
        connection = asyncio.create_task(asyncio.Event().wait())
        listeners.connections[22000] = {connection}
        await listeners.sync({22000: ("10.0.0.4", 22), 22001: ("10.0.0.3", 22)})
        assert connection.cancelled() and len(servers) == 3
        servers[0].close.assert_called_once()
        servers[1].close.assert_not_called()
        await listeners.sync({})
        assert listeners.servers == {}
        servers[1].close.assert_called_once()
        servers[2].close.assert_called_once()

    asyncio.run(scenario())


def test_tcp_forward_copies_both_directions_and_closes(monkeypatch):
    async def scenario():
        reader = SimpleNamespace(read=AsyncMock(side_effect=[b"ssh-input", b""]))
        upstream_reader = SimpleNamespace(read=AsyncMock(side_effect=[b"ssh-output", b""]))
        writer = MagicMock(drain=AsyncMock(), wait_closed=AsyncMock())
        remote = MagicMock(drain=AsyncMock(), wait_closed=AsyncMock())
        connect = AsyncMock(return_value=(upstream_reader, remote))
        monkeypatch.setattr(agent.asyncio, "open_connection", connect)
        listeners = agent.IPv6Listeners()
        await listeners.forward(22000, "10.0.0.2", reader, writer)
        connect.assert_awaited_once_with("10.0.0.2", 22)
        remote.write.assert_called_once_with(b"ssh-input")
        writer.write.assert_called_once_with(b"ssh-output")
        writer.close.assert_called_once()
        remote.close.assert_called_once()
        assert not listeners.connections[22000]

    asyncio.run(scenario())


def test_nat_mesh_masquerade_added_once(monkeypatch):
    commands = []
    present = set()

    def run(command, **kwargs):
        args = command[5:]
        commands.append(args)
        result = SimpleNamespace(returncode=0, stdout="")
        if args[0] == "-C":
            result.returncode = 0 if tuple(args[1:]) in present else 1
        elif args[0] == "-A" and args[1] in {"PREROUTING", "POSTROUTING"}:
            present.add(tuple(args[1:]))
        return result

    monkeypatch.setattr(agent.subprocess, "run", run)
    nat = agent.NatRules("wlo1", "tailscale0")
    nat.sync({22000: ("10.20.20.5", 22)})
    nat.sync({22000: ("10.20.20.5", 22)})
    masquerade = ["-A", "POSTROUTING", "-o", "tailscale0", "-m", "conntrack", "--ctstate", "DNAT", "-j", "MASQUERADE"]
    assert commands.count(masquerade) == 1
    with pytest.raises(ValueError):
        agent.NatRules("wlo1", "ts0;id")


def test_fetch_ports_scope_all_query(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return b"[]"

    class Opener:
        def open(self, request, timeout):
            seen["url"] = request.full_url
            return Response()

    monkeypatch.setattr(agent.urllib.request, "build_opener", lambda *handlers: Opener())
    assert agent.fetch_ports("https://control.example", "fake-token", "pve-asus", "all") == {}
    assert seen["url"].endswith("/api/v1/agent/ports?node=pve-asus&scope=all")


@pytest.mark.parametrize("target", [22, 80, 3389, 5432, 23, "80", True, None])
def test_fetch_service_target_validation(monkeypatch, target):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps([{"ssh_port": 23000, "ip": "10.0.0.2", "vmid": 101, "target_port": target}]).encode()
    opener = MagicMock()
    opener.open.return_value = response
    monkeypatch.setattr(agent.urllib.request, "build_opener", lambda *args: opener)
    if type(target) is int and target in {22, 80, 3389, 5432}:
        assert agent.fetch_ports("https://control.example", "fake-token", "pve") == {23000: ("10.0.0.2", target)}
    else:
        with pytest.raises(ValueError):
            agent.fetch_ports("https://control.example", "fake-token", "pve")


@pytest.mark.parametrize("target", [80, 3389, 5432])
def test_nat_service_destination(monkeypatch, target):
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="")
    monkeypatch.setattr(agent.subprocess, "run", run)
    agent.NatRules("wlo1").sync({23000: ("10.0.0.2", target)})
    assert ["iptables", "-w", "5", "-t", "nat", "-A", "VPS_SSH", "-p", "tcp", "-m", "tcp", "--dport", "23000", "-j", "DNAT", "--to-destination", f"10.0.0.2:{target}"] in commands


@pytest.mark.parametrize("target", [80, 3389, 5432])
def test_ipv6_listener_service_destination_and_target_change(monkeypatch, target):
    async def scenario():
        callbacks, servers = [], []
        async def start(callback, sock):
            callbacks.append(callback)
            server = MagicMock(wait_closed=AsyncMock())
            servers.append(server)
            return server
        monkeypatch.setattr(agent.socket, "socket", lambda *args: MagicMock())
        monkeypatch.setattr(agent.asyncio, "start_server", start)
        connect = AsyncMock(side_effect=OSError("fixture"))
        monkeypatch.setattr(agent.asyncio, "open_connection", connect)
        listeners = agent.IPv6Listeners()
        await listeners.sync({23000: ("10.0.0.2", target)})
        writer = MagicMock(wait_closed=AsyncMock())
        await callbacks[0](MagicMock(), writer)
        connect.assert_awaited_once_with("10.0.0.2", target)
        await listeners.sync({23000: ("10.0.0.2", 22)})
        assert len(servers) == 2
        servers[0].close.assert_called_once()
        await listeners.sync({})
    asyncio.run(scenario())


def test_ipv6_routes_prefix_and_sync(monkeypatch):
    commands = []
    outputs = {
        ("-j", "addr", "show", "dev", "wlo1", "scope", "global"): json.dumps([{"addr_info": [{"family": "inet6", "local": "fd7a::2", "prefixlen": 128}, {"family": "inet6", "local": "2402:800:639e:f77c:aa41:f4ff:fe59:5b49", "prefixlen": 64}]}]),
        ("-j", "route", "show", "dev", "vpsnet0", "proto", "static"): json.dumps([{"dst": "2402:800:639e:f77c::100"}, {"dst": "fe80::/64"}]),
        ("-j", "neigh", "show", "proxy", "dev", "wlo1"): json.dumps([{"dst": "2402:800:639e:f77c::100"}]),
    }

    def run(command, **kwargs):
        assert command[:2] == ["ip", "-6"] and "shell" not in kwargs
        commands.append(tuple(command[2:]))
        return SimpleNamespace(returncode=0, stdout=outputs.get(tuple(command[2:]), ""), stderr="")

    monkeypatch.setattr(agent.subprocess, "run", run)
    routes = agent.IPv6Routes("wlo1", "vpsnet0")
    assert routes.prefix() == "2402:800:639e:f77c::/64"
    routes.sync({"2402:800:639e:f77c::113"})
    assert ("addr", "replace", "fe80::1/64", "dev", "vpsnet0", "nodad") in commands
    assert ("route", "del", "2402:800:639e:f77c::100/128", "dev", "vpsnet0") in commands and ("neigh", "del", "proxy", "2402:800:639e:f77c::100", "dev", "wlo1") in commands
    assert ("route", "replace", "2402:800:639e:f77c::113/128", "dev", "vpsnet0", "proto", "static") in commands and ("neigh", "replace", "proxy", "2402:800:639e:f77c::113", "dev", "wlo1") in commands
    with pytest.raises(ValueError):
        agent.IPv6Routes("wlo1; rm", "vpsnet0")
