# Control API

Python 3.12, FastAPI, SQLAlchemy 2, Alembic và PostgreSQL. Mỗi node Proxmox VE độc lập có API token, storage và template riêng. API nằm tại `/api/v1`; OpenAPI tại `/docs`.

## Chạy cục bộ

Chạy các lệnh từ thư mục `control-plane/`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; from cryptography.fernet import Fernet; print('JWT_SECRET=' + secrets.token_urlsafe(48)); print('FERNET_KEY=' + Fernet.generate_key().decode())"
```

Điền hai khóa vừa tạo vào `.env`, sửa `DATABASE_URL` trỏ tới PostgreSQL đã tạo database. Giữ khóa Fernet ổn định để giải mã token đang lưu; sao lưu khóa ở nơi tách biệt với database. Không đưa `.env` lên Git. Giá trị mẫu Fernet cố ý không hợp lệ để buộc cấu hình trước khi chạy.

```powershell
alembic upgrade head
python -m scripts.create_admin admin@example.com
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mở terminal thứ hai, kích hoạt cùng môi trường rồi chạy worker:

```powershell
python -m app.workers
```

Chạy đúng một worker scheduler. Nếu dùng `WORKERS_ENABLED=true` để nhúng scheduler vào API, chạy Uvicorn với một process và không chạy worker riêng. Đồng bộ node mỗi 60 giây; tính tiền mỗi giờ. Worker phải chạy để theo dõi node và tính tiền.

Ví ảo phục vụ mô phỏng: đặt `VIRTUAL_TOPUP_ENABLED=true` để người dùng tự nạp tiền ảo. Tắt tùy chọn này khi không cần mô phỏng. `request_id` chống cộng tiền nhiều lần khi gửi lại cùng yêu cầu; cùng mã nhưng khác số tiền trả 409.

## Nạp tiền qua payOS

Chạy `alembic upgrade head` trước khi khởi động API/worker để tạo bảng `payments`, `notifications` và cờ theo dõi kết nối node trong migration `0003_payos_notify`. Điền `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY` của kênh thu và `PAYOS_RETURN_URL`, `PAYOS_CANCEL_URL` trong `.env`. Các khóa được xử lý bằng `SecretStr`; thiếu cấu hình, API payOS trả 503. Không đưa khóa vào mã nguồn hay nhật ký. `PAYOS_MIN_AMOUNT` mặc định 10.000, `PAYOS_MAX_AMOUNT` mặc định 5.000.000 VND; để trống dùng mặc định.

`POST /api/v1/billing/payos` nhận `{"amount":10000}`, trả `{order_code, amount, checkout_url, qr_code, status}`. Khách mở `checkout_url` hoặc quét nội dung `qr_code`; giao diện hỏi `GET /api/v1/billing/payos/{order_code}` để xác nhận. URL quay lại chỉ phục vụ điều hướng, không xác nhận tiền đã nhận. Hệ thống ký yêu cầu HMAC-SHA256, kiểm chữ ký phản hồi nếu có và đối chiếu mã đơn/số tiền. Khi payOS xác nhận `PAID` và đã nhận đủ tiền, API cộng ví trong cùng giao dịch với trạng thái đơn, audit và hàng đợi thông báo; khóa database và `request_id=payos-<order_code>` chống cộng trùng giữa API/worker. Tiền tố này dành riêng cho payOS, không dùng ở API nạp ví ảo.

`GET /api/v1/billing/payos?offset=0&limit=50` liệt kê đơn của người dùng đang đăng nhập, mới nhất trước (tối đa 200). Chủ đơn hoặc admin được hỏi trạng thái; chỉ chủ đơn được `POST /api/v1/billing/payos/{order_code}/cancel`, body tùy chọn `{"cancellationReason":"Không còn nhu cầu"}`. Đơn đã thanh toán được giữ nguyên khi gửi lại yêu cầu hủy; nếu payOS xác nhận vừa thanh toán trong lúc hủy thì tiền vẫn được đối soát vào ví. Worker hỏi các đơn pending mỗi 60 giây và đánh expired các đơn quá 24 giờ. Không cần webhook nên dùng được sau CGNAT.

## Thông báo Gmail

Đặt `NOTIFY_ENABLED=true`, `SMTP_USER` và `NOTIFY_TO` (nhiều địa chỉ cách nhau bằng dấu phẩy). `SMTP_HOST` mặc định `smtp.gmail.com`, `SMTP_PORT` mặc định `587`, luôn STARTTLS và kiểm chứng chỉ TLS. `SMTP_PASSWORD_FILE` trỏ tới tệp mật khẩu ứng dụng Gmail nằm ngoài mã nguồn, chỉ tài khoản chạy dịch vụ được đọc (quyền `0600` trên Linux). Mật khẩu được đọc lúc gửi và bỏ khoảng trắng/CRLF; hệ thống không nhận `SMTP_PASSWORD` trực tiếp từ `.env`. `NOTIFY_DEDUP_MINUTES` mặc định 30 phút; thông báo mặc định tắt.

API và worker có luồng gửi riêng, lấy hàng đợi đã commit trong bảng `notifications`; PostgreSQL khóa từng thông báo để nhiều process không gửi đồng thời cùng bản ghi. Request không chờ SMTP. Email HTML tiếng Việt chứa thời gian UTC+7, sự kiện và chi tiết, tự escape dữ liệu. Cùng khóa sự kiện đang chờ hoặc vừa gửi trong khoảng chống lặp chỉ tạo một thông báo. Thông báo chưa gửi được giữ qua lần khởi động lại; lỗi SMTP ghi một dòng an toàn và kết thúc lần gửi, sự kiện tiếp theo có thể thử lại. Việc gửi mail không làm rollback nghiệp vụ.

Thông báo gồm nạp tiền payOS, tạo/xóa/cài lại VPS, lỗi cấp phát/cài lại, VPS bị dừng vì hết tiền và node mất kết nối quá 120 giây/kết nối lại. Node lưu cờ trạng thái để không gửi lại mỗi phút, kể cả khi khoảng chống lặp đã hết. Admin gọi `POST /api/v1/admin/notify/test` để đưa mail thử vào hàng đợi (202); email thử cũng áp dụng chống lặp.

## API

Đăng ký bằng `POST /api/v1/auth/register`, đăng nhập bằng `POST /api/v1/auth/login`, body JSON `{"email":"user@example.com","password":"a-long-local-password"}`. Dùng `Authorization: Bearer <access_token>` cho API riêng tư. `GET /api/v1/plans` và `GET /api/v1/public/map` công khai để phục vụ trang giới thiệu; đăng ký chỉ tạo role `user`, tạo admin bằng lệnh cục bộ ở trên.

| Nhóm | Endpoint | Quyền |
|---|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | Đăng ký/đăng nhập công khai; `/me` cần JWT |
| Gói | `GET /plans`, `POST /plans` | Xem: công khai; tạo: admin |
| Bản đồ | `GET /public/map`, `GET /nodes/map` | Công khai và đã đăng nhập tương ứng; chỉ tên, mã node, tài nguyên và trạng thái |
| Instance | `GET/POST /instances`, `GET/DELETE /instances/{id}` | Chủ sở hữu hoặc admin; admin xem được toàn bộ |
| Nguồn điện | `POST /instances/{id}/start`, `/stop`, `/reboot` | Chủ sở hữu hoặc admin |
| Chi tiết VPS | `GET /instances/{id}/detail`, `/credentials`, `/logs` | Chủ sở hữu hoặc admin |
| Tài nguyên VPS | `GET /instances/{id}/stats?timeframe=hour`, `/status-now` | Chủ sở hữu hoặc admin |
| Cấu hình VPS | `POST /instances/{id}/password`, `/reinstall` | Chủ sở hữu hoặc admin |
| Console | `WS /instances/{id}/console?token=<JWT>` | Chủ sở hữu hoặc admin; VM đang chạy |
| Node-agent | `GET /agent/ports?node=<proxmox_node>` | Header `X-Agent-Token`; tắt khi chưa đặt `AGENT_TOKEN` |
| Node | `GET/POST /nodes`, `POST /nodes/{id}/check`, `/sync` | Admin |
| Ví | `GET /billing/balance`, `POST /billing/topup`, `GET /billing/transactions` | Ví của tài khoản đang đăng nhập |
| payOS | `POST/GET /billing/payos`, `GET /billing/payos/{order_code}`, `POST /billing/payos/{order_code}/cancel` | Tạo/danh sách: đã đăng nhập; xem trạng thái: chủ đơn hoặc admin; hủy: chủ đơn |
| Thông báo | `POST /admin/notify/test` | Admin |
| Quản trị | `GET /admin/users`, `/admin/audit-logs`, `/admin/stats` | Admin |
| Khôi phục | `POST /admin/instances/{id}/resolve-provisioning` | Admin; đánh dấu tác vụ cấp phát bị gián đoạn để kiểm tra/xóa |

Các endpoint trong bảng đều có tiền tố `/api/v1`. Danh sách instance, giao dịch, người dùng và audit hỗ trợ `offset`, `limit` tối đa 200.

Ví dụ tạo gói:

```json
{"ten":"Small","vcpu":1,"ram_mb":1024,"disk_gb":10,"gia_theo_gio":"1000.00"}
```

Ví dụ thêm node:

```json
{"ten":"MSI","api_url":"https://100.64.0.10:8006","token_id":"cloud@pve!control","token_secret":"replace-with-node-token","mesh_ip":"100.64.0.10","proxmox_node":"pve-msi","storage":"local-lvm","bridge":"vmbr0","vm_template_id":9000,"lxc_template_id":9001,"vm_disk":"scsi0"}
```

`proxmox_node` là tên thực trong `/nodes` của Proxmox, khác với tên hiển thị `ten`. `mesh_ip` là địa chỉ node trong mạng phủ; địa chỉ kết nối API lấy từ `api_url`. Chạy `/nodes/{id}/sync` sau khi thêm node. Bộ điều phối chỉ dùng node online có lần đồng bộ thành công trong 120 giây gần nhất và có template đúng loại.

Ví dụ tạo VM:

```json
{"ten":"ubuntu-01","plan_id":1,"loai":"vm","cloud_user":"ubuntu","ssh_public_key":"ssh-ed25519 REPLACE_WITH_VALID_PUBLIC_KEY","ip_cidr":"10.10.0.10/24","gateway":"10.10.0.1","strategy":"best-fit"}
```

Thay bằng khóa OpenSSH thật, chỉ gửi khóa công khai. Bỏ `ip_cidr/gateway` để dùng DHCP. Địa chỉ DHCP được lấy khi đồng bộ; VM cần qemu-guest-agent đang chạy và quyền truy vấn agent. Nếu chưa lấy được IP thì trường `ip` là `null`. Mạng bridge, DHCP, định tuyến tới guest và cô lập mạng giữa tenant cần được cấu hình trên node/gateway.

VM được cấp mật khẩu ngẫu nhiên 16 ký tự có chữ hoa, chữ thường và số qua `cipassword`. Mật khẩu được mã hóa Fernet trong database, chỉ trả qua `/credentials` hoặc kết quả đổi mật khẩu; các phản hồi này có `Cache-Control: no-store`. Giữ khóa Fernet để giải mã cả token node lẫn mật khẩu VPS. `/credentials` trả `{username, password, ssh_host, ssh_port}`; `ssh_host` lấy từ `GATEWAY_HOST`. LXC dùng khóa SSH và trả `password=null`.

`POST /instances/{id}/password` nhận `{"password":"mat-khau-moi-it-nhat-10-ky-tu"}`; bỏ body hoặc gửi `{}` để tự sinh. Mật khẩu dài 10–128 ký tự, không chứa ký tự điều khiển. API cập nhật `cipassword`, tạo lại đĩa cloud-init và reboot VM đang chạy; VM dừng sẽ được khởi động và thu phí theo kỳ đang có. Đổi mật khẩu LXC chưa được hỗ trợ. Template phải cho phép cloud-init đặt mật khẩu và dịch vụ SSH xác thực bằng mật khẩu nếu cần dùng cách đăng nhập này.

`/detail` giữ các trường instance và thêm `ten_he_dieu_hanh` từ tên/description template, `node_ten`, `tong_chi_phi` là tổng tiền sử dụng đã trừ, `ngay_tao`; `trang_thai` được truy vấn trực tiếp trên Proxmox. `/stats` chấp nhận `hour`, `day`, `week`, mặc định `hour`, lấy RRD `AVERAGE`, sắp xếp theo thời gian tăng dần. Mỗi điểm có `time` (Unix giây), `cpu` (%), `mem_used`, `mem_total` (byte), `netin`, `netout`, `diskread`, `diskwrite` (byte/giây); dữ liệu thiếu giữ `null`. `/status-now` trả `cpu` (%), `mem` (byte), `uptime` (giây). `/logs` chỉ trả audit của instance, mới nhất trước, hỗ trợ `offset` và `limit` tối đa 200.

`POST /instances/{id}/reinstall` xóa toàn bộ dữ liệu guest rồi clone lại template đã lưu trên cùng node, cùng VMID và cổng SSH. API giữ cấu hình tài nguyên và giá đã chụp, user, SSH key, IP tĩnh/gateway hoặc DHCP; VM nhận mật khẩu mới. IP được truy vấn lại qua guest agent hoặc IPAM SDN; nếu chưa có DHCP, worker sẽ cập nhật sau. LXC cũng cài lại từ template và giữ khóa SSH cho root. Máy phải ở trạng thái `running` hoặc `stopped`, ví đủ số dư để chạy; không thu thêm kỳ khi kỳ đã trả còn hiệu lực. Bản ghi chưa lưu đủ user/SSH key/template trả lỗi yêu cầu quản trị kiểm tra. Thao tác đang chạy giữ `provisioning`; lỗi giữ `error` cùng VMID/cổng để quản trị kiểm tra an toàn. Mọi thao tác được ghi audit, không ghi mật khẩu.

Console dùng WebSocket `wss://<control-api>/api/v1/instances/{id}/console?token=<access_token>`. Template VM cần `serial0: socket`, console Linux trên `ttyS0` và dịch vụ serial getty. API gọi `termproxy` với `serial=serial0`, đăng nhập upstream bằng `<user>:<ticket>\n`, chờ `OK`, rồi chuyển nguyên văn text/bytes hai chiều. Client đóng gói nhập theo `0:<số byte UTF-8>:<dữ liệu>`, đổi kích thước theo `1:<cols>:<rows>:`. Upstream dùng API token của node và TLS theo `PROXMOX_VERIFY_SSL` (hỗ trợ CA riêng và `REQUESTS_CA_BUNDLE`). Reverse proxy cần hỗ trợ WebSocket và bỏ query string chứa JWT khỏi access log; chỉ dùng HTTPS/WSS khi triển khai.

## Template và Proxmox

API token phải dùng quyền tối thiểu phù hợp: xem node/storage/VM, cấp phát và clone, sửa CPU/RAM/đĩa/mạng/cloud-init, điều khiển nguồn và xóa; thêm `VM.Console` cho console web. VM dùng cloud-init cần template Linux có cloud-init, đĩa cloud-init và đĩa hệ thống đúng `vm_disk`. Đĩa template không được lớn hơn gói; API chỉ mở rộng đĩa, không thu nhỏ. Storage đích phải hỗ trợ loại guest được cấp phát. VM clone có đầy đủ đĩa riêng, được cấu hình số core, RAM, user, SSH key, IPv4 và khởi động sau khi tác vụ hoàn tất.

Proxmoxer dùng HTTPS, API token, xác thực TLS và timeout. Cài chứng thư được máy chạy API tin cậy, hoặc thêm CA nội bộ vào trust store/`REQUESTS_CA_BUNDLE`; tên host trong URL phải khớp chứng thư. Lỗi upstream được chuyển thành thông báo tiếng Việt, không trả nội dung lỗi gốc hoặc token.

LXC dùng API cấu hình mạng gốc và hook của template để cấp khóa SSH cho tài khoản `root`. API cấu hình LXC không nhận các trường cloud-init của QEMU; `ssh-public-keys` chỉ thuộc API tạo container từ archive, không dùng để sửa container vừa clone. Vì vậy LXC cần cài hook dưới đây trên từng node; việc thiếu hook trả lỗi rõ ràng. Template LXC cần Python 3, OpenSSH, tài khoản root được phép SSH bằng khóa và không chứa khóa truy cập dùng chung.

Sao chép `scripts/lxc_hook.py` tới `/usr/local/lib/control-plane/lxc_hook.py` trên node bằng tài khoản quản trị. Bật nội dung `snippets` trên storage `local`, tạo `/var/lib/vz/snippets/control-plane-lxc-hook.sh`:

```sh
#!/bin/sh
exec /usr/bin/python3 /usr/local/lib/control-plane/lxc_hook.py "$@"
```

```sh
chmod 0755 /var/lib/vz/snippets/control-plane-lxc-hook.sh
pct set 9001 --hookscript local:snippets/control-plane-lxc-hook.sh
```

Hook được kế thừa khi clone, đọc metadata public từ description và đặt `authorized_keys` khi container khởi động. Chuẩn bị template với SSH host key riêng được sinh ở lần khởi động đầu tiên. Gửi `loai=lxc`, `cloud_user=root` khi tạo LXC. Không cần SSH vào node từ Control API.

Tài liệu API nền tảng: [Proxmoxer authentication](https://proxmoxer.github.io/docs/latest/authentication/), [cloud-init QEMU](https://proxmoxer.github.io/docs/dev/examples/cloud-init/), [schema LXC chính thức](https://github.com/proxmox/pve-container/blob/master/src/PVE/API2/LXC.pm).

## Tài nguyên, cổng và tính tiền

`best-fit` tối thiểu hóa tổng tỷ lệ CPU/RAM/đĩa còn dư sau khi cấp phát. `least-loaded` chọn node có tỷ lệ tài nguyên ít dư nhất còn cao nhất. Hòa điểm chọn node có ID nhỏ nhất. Giá và tài nguyên được chụp vào instance để lịch sử tính tiền không phụ thuộc thay đổi gói về sau.

PostgreSQL khóa hàng singleton `allocation_locks` để tuần tự hóa cấp tài nguyên, cấp cổng, điều khiển nguồn và cập nhật ví giữa các API process/worker. Cổng SSH có unique constraint toàn hệ thống; VMID có unique constraint theo node. SQLite chỉ dùng cho unit test, không cung cấp hành vi khóa tương đương PostgreSQL. Các thao tác nguồn chờ Proxmox nên có thể giữ khóa lâu; cần hàng đợi và khóa theo tài nguyên khi mở rộng tải.

Cổng được cấp trong khoảng `SSH_PORT_START..SSH_PORT_END`, chỉ thu hồi sau khi Proxmox xác nhận xóa guest. Node-agent áp dụng DNAT IPv4 và chuyển tiếp IPv6 trên từng node tới `instance.ip:22`. `GATEWAY_HOST:ssh_port` phải được định tuyến/chuyển tiếp tới node tương ứng hoặc trỏ tới địa chỉ node phù hợp khi triển khai một node; node-agent không tự cấu hình gateway ở máy khác.

## Node-agent SSH

`node-agent/agent.py` dùng Python 3 và thư viện chuẩn, chạy trên từng node Proxmox có sẵn `iptables` và IPv6. Đặt `AGENT_TOKEN` ngẫu nhiên ít nhất 32 byte trong `.env` của Control API và cùng giá trị trong `/etc/control-plane/node-agent.env` (quyền `0600`):

```ini
API_URL=https://control.example.test
AGENT_TOKEN=<token-ngau-nhien-it-nhat-32-byte>
NODE_NAME=pve-asus
WAN_IFACE=wlo1
```

`API_URL` là gốc Control API, cũng chấp nhận gốc có `/api/v1`; HTTPS phải có chứng thư được node tin cậy. `NODE_NAME` khớp `proxmox_node`; đặt tên node khác nhau để ánh xạ không lẫn giữa các máy độc lập. `WAN_IFACE` mặc định `wlo1`. Endpoint `/api/v1/agent/ports` chỉ nhận `X-Agent-Token`, trả `[{"ssh_port":22000,"ip":"10.10.0.10","vmid":101}]` cho instance `running` có IP/cổng thuộc node đã chọn; không đặt token thì trả 404, token sai trả 401. Token này là bí mật chung có quyền xem ánh xạ cổng các node, chỉ cấp cho node tin cậy.

Chép script tới `/opt/control-plane/node-agent/agent.py`, chép `node-agent/node-agent.service` tới `/etc/systemd/system/node-agent.service`, sau đó chạy:

```sh
chmod 0600 /etc/control-plane/node-agent.env
systemctl daemon-reload
systemctl enable --now node-agent
journalctl -u node-agent -f
```

Mỗi 30 giây agent lấy danh sách cổng, đồng bộ chain NAT riêng `VPS_SSH` qua nhánh `PREROUTING -i <WAN_IFACE> -p tcp`, chỉ thêm/xóa luật thay đổi và không flush bảng NAT. Listener IPv6 `[::]:<ssh_port>` đặt `IPV6_V6ONLY`, chuyển TCP tới IPv4 guest cổng 22 bằng asyncio; đổi IP hoặc thu hồi cổng sẽ đóng listener cùng kết nối cũ của cổng đó. Lỗi API giữ ánh xạ gần nhất và thử lại sau 30 giây. Dừng dịch vụ sẽ thu hồi listener và luật trong chain riêng.

Node cần bật IPv4 forwarding, có tuyến về guest, đường trả gói phù hợp và firewall cho phép FORWARD IPv4/INPUT IPv6 với các cổng được cấp; agent không thay đổi các thiết lập đó. Dịch vụ mẫu giới hạn capability ở `CAP_NET_ADMIN`; listener dùng cổng từ 1024 trở lên. Không dùng chung chain `VPS_SSH` cho dịch vụ khác.

Thu trước một giờ khi khởi động; không hoàn tiền phần giờ chưa dùng. Mỗi kỳ tính tiền kiểm tra thời hạn `paid_until`, thu bù các kỳ đang chạy bị bỏ lỡ và dùng khóa giao dịch duy nhất để tránh thu trùng. Dừng hoặc xóa máy đang chạy cũng quyết toán các kỳ quá hạn trước khi đổi trạng thái. Máy dừng không phát sinh kỳ mới; khởi động lại sau khi thời hạn cũ hết sẽ bắt đầu kỳ mới. Số dư không đủ thì chuyển `suspended` và yêu cầu node dừng; thao tác dừng được thử lại khi đồng bộ node hoặc chạy kỳ tính tiền tiếp theo. Chỉ khởi động lại sau khi nạp đủ số dư và gọi `/start`. Worker chạy theo giờ nên thời điểm thực thi dừng có thể trễ tối đa một chu kỳ khi node còn online; node mất mạng chỉ dừng được khi kết nối trở lại.

Clone lỗi hoặc timeout giữ instance `error` cùng VMID, cổng và tài nguyên đã đặt chỗ. Worker cố dừng guest lỗi còn chạy; quản trị viên kiểm tra node rồi xóa instance qua API để thu hồi an toàn. Nếu tiến trình chết giữa lúc cấp phát thì bản ghi giữ `provisioning`: kiểm tra tác vụ Proxmox, chờ nó kết thúc, dùng endpoint khôi phục rồi xóa. Không tái sử dụng VMID của bản ghi lịch sử để tránh nhầm guest khi tác vụ cũ kết thúc muộn. Không chạy tác vụ tạo/xóa ngoài Control API trên cùng dải VMID của dịch vụ.

## Docker và migration

```powershell
docker build -t distributed-cloud-control .
docker run --rm --env-file .env distributed-cloud-control alembic upgrade head
docker run --rm --env-file .env -p 8000:8000 distributed-cloud-control
docker run --rm --env-file .env distributed-cloud-control python -m app.workers
```

Trong container, `DATABASE_URL` phải trỏ tới hostname PostgreSQL trong mạng Docker hoặc địa chỉ máy chủ phù hợp. Container chạy user không đặc quyền. Migration là bước riêng trước khi khởi động, API không tự tạo bảng.

## Phục vụ Flutter Web

`WEB_DIR` mặc định trống, không phục vụ web. Khi đã có bản Flutter Web được dựng riêng, đặt đường dẫn tuyệt đối tới thư mục chứa `index.html`, ví dụ `WEB_DIR=/opt/cloud/web/build/web`. Khởi động lại API để áp dụng. Thư mục không hợp lệ làm ứng dụng từ chối khởi động.

Các tệp thật trong thư mục được phục vụ trực tiếp; đường dẫn khác trả `index.html` để go_router xử lý đường dẫn thường. Các tiền tố `/api`, `/docs`, `/openapi.json`, `/redoc`, `/health` không đi qua SPA fallback. Chặn tệp ẩn và đường dẫn thoát thư mục, kể cả symlink; `index.html` cũng phải nằm trong `WEB_DIR`. HTML, service worker, manifest và version dùng `Cache-Control: no-cache`; tài nguyên khác cache một giờ để tránh giữ bản cũ quá lâu khi tên tệp không có hash.

Hai endpoint bản đồ trả cùng schema giới hạn: `id`, `ten`, `proxmox_node`, `online`, `last_seen_at`, `total_vcpu`, `total_ram_mb`, `total_disk_gb`, `used_vcpu`, `used_ram_mb`, `used_disk_gb`. `online` chỉ đúng khi trạng thái node online và lần đồng bộ thành công không quá 120 giây. Không có địa chỉ API, token, IP hoặc mesh IP. `/nodes` quản trị vẫn giữ quyền admin.

## Chạy kiểm thử

```powershell
python -m pytest -q
```

Test dùng SQLite trong bộ nhớ, ví và tài khoản giả, Proxmox được mock; test migration dùng SQLite tạm để kiểm tra upgrade/downgrade, giữ dữ liệu và đối chiếu schema với models. Bao phủ thuật toán chọn node, cấp/thu hồi cổng, tính tiền, JWT và quyền chủ sở hữu/admin, mật khẩu mã hóa, chi tiết/biểu đồ/trạng thái, cài lại VM/LXC, audit phân trang, console hai chiều và ngắt kết nối, token agent, thay đổi luật DNAT và listener IPv6. Kiểm tra race giữa process, chứng thư TLS, bridge, LXC hook, firewall/NAT và API Proxmox thật cần môi trường PostgreSQL/Proxmox tích hợp riêng.

Test payOS dùng `httpx.MockTransport`, kiểm chữ ký bằng HMAC tính độc lập, chữ ký sai, quyền đơn, giới hạn tiền, phân trang, hủy, lỗi mạng và hỏi trạng thái lặp/đồng thời bằng hai session SQLite trên tệp. Test thông báo mock `smtplib`, kiểm STARTTLS, nội dung HTML/UTC+7, đọc mật khẩu khi gửi, chống lặp, rollback và chuyển trạng thái node. Test chặn kết nối ra ngoài; loopback nội bộ phục vụ event loop Windows được cho phép. Chưa kiểm chứng giao dịch payOS/SMTP và tranh chấp nhiều process trên PostgreSQL thật.
