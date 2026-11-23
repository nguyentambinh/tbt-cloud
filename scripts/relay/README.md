# Trạm chuyển tiếp IPv4 công cộng và IPv6 riêng cho VPS

Node ở nhà nằm sau CGNAT nên không mở cổng IPv4 vào được. Node tự nối WireGuard ra một VPS có IPv4 công cộng (trạm chuyển tiếp), trạm đẩy các cổng dịch vụ ngược về node. IPv6 thì nhà mạng cấp prefix /64 công cộng, nên mỗi VPS Linux nhận một địa chỉ IPv6 riêng, vào thẳng cổng 22.

## Sơ đồ

```
Internet (IPv4)                                   Internet (IPv6)
   │ TCP 22000-23999, 18000                           │ mọi cổng, SSH 22
   ▼                                                  ▼
VPS B 103.77.208.60 (ens192)                      Modem (prefix 2402:800:639e:f77c::/64)
   │ DNAT → 10.99.0.2, MASQUERADE                     │ NDP: node trả lời thay VPS (proxy NDP trên wlo1)
   │ wg-relay 10.99.0.1  ◄── UDP 51820 ──  wg-relay 10.99.0.2 (node pve-asus, tự nối ra, keepalive 25)
   ▼                                                  ▼
node pve-asus: chain VPS_SSH (node-agent)         route <prefix>::<vmid>/128 dev vpsnet0
   │ 220xx → VPS:22 / 3389, 230xx → VPS:5432 / 80     │ VPS: ip6 <prefix>::<vmid>/128, gw6 fe80::1
   │ 8000 → gateway CT 200 (web, API)                 ▼
   ▼                                              VPS (Linux)
VPS trên pve-asus (vpsnet0) hoặc pve-tin (qua mesh Tailscale/Headscale)
```

| Từ ngoài vào | Đi tới |
|---|---|
| `103.77.208.60:22000-22999` | SSH (Linux) hoặc RDP (Windows) của từng VPS |
| `103.77.208.60:23000-23999` | Cổng dịch vụ PaaS (PostgreSQL 5432, web 80) |
| `103.77.208.60:18000` | Web TBT Cloud (gateway CT 200, cổng 8000) |
| `[<prefix>::<vmid>]:mọi cổng` | Thẳng vào VPS Linux, SSH cổng 22 |

## Tệp cấu hình

- `wg-relay-vpsb.conf` → `/etc/wireguard/wg-relay.conf` trên VPS B.
- `wg-relay-node.conf` → `/etc/wireguard/wg-relay.conf` trên node nhà.
- Khóa riêng nằm ở `/etc/wireguard/relay.key` (quyền 600), `PostUp` nạp bằng `wg set %i private-key`, nên tệp cấu hình không chứa khóa riêng.
- Mọi luật iptables nằm trong `PostUp` / `PostDown` của interface: bật là có, `systemctl stop wg-quick@wg-relay` là gỡ sạch. Hai bên chạy `systemctl enable --now wg-quick@wg-relay` nên tự lên lại sau khởi động.
- Node: `/etc/systemd/network/25-wlo1.network` có `IPv6AcceptRA=yes` (giữ IPv6 của node khi bật chuyển tiếp), `IPv6ProxyNDP=yes`; `/etc/sysctl.d/99-vps-nat.conf` có `net.ipv6.conf.all.forwarding = 1`.
- node-agent đọc `VPS_IPV6_BRIDGE=vpsnet0` trong `/etc/control-plane/node-agent.env`: mỗi 30 giây báo prefix lên `POST /api/v1/agent/ipv6`, nhận danh sách địa chỉ VPS, giữ `fe80::1` trên bridge, route /128 và proxy NDP.

## Lệnh kiểm tra

```
# trạng thái tunnel (trên B hoặc node)
wg show wg-relay                       # latest handshake < 2 phút
ping -c3 10.99.0.1                     # từ node
iptables -t nat -S TBT_RELAY           # trên B: luật DNAT
# từ máy bất kỳ ngoài Internet
ssh -p 220xx root@103.77.208.60
ssh root@<ipv6 của VPS>
curl -I http://103.77.208.60:18000/
# IPv6 trên node
ip -6 route show dev vpsnet0 proto static
ip -6 neigh show proxy dev wlo1
journalctl -u node-agent -n 20
```

## Thêm cổng mới

Thêm luật DNAT vào `TBT_RELAY` trên B (ví dụ chuyển 25565 về node):

```
iptables -t nat -A TBT_RELAY -p tcp --dport 25565 -j DNAT --to-destination 10.99.0.2
```

Muốn giữ qua khởi động lại thì thêm cùng lệnh vào dòng `PostUp` tạo `TBT_RELAY` trong `/etc/wireguard/wg-relay.conf` rồi `systemctl restart wg-quick@wg-relay`. Trên node, cổng phải có luật trong chain `VPS_SSH` (node-agent tự tạo cho cổng đã cấp trong control plane). Dải 22000 - 23999 đã chuyển sẵn, cổng mới cấp trong dải này không cần sửa B.

## Giới hạn

- IPv4 dùng chung một địa chỉ nên vẫn cần `-p`; SSH không cổng chỉ có qua IPv6.
- Prefix IPv6 do nhà mạng cấp có thể đổi khi modem quay số lại. node-agent tự báo prefix mới, máy tạo hoặc cài lại sau đó nhận địa chỉ mới; máy cũ cần cài lại.
- VPS chỉ có IPv6 trên node bật `VPS_IPV6_BRIDGE` (pve-asus). Máy Windows dùng RDP qua IPv4.
- Người dùng ở mạng chưa có IPv6 thì dùng đường IPv4 qua trạm.
