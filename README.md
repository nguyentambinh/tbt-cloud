# TBT Cloud

Nền tảng đám mây phân tán cung cấp máy chủ ảo từ máy tính cá nhân. Mỗi máy tính của thành viên chạy Proxmox VE và trở thành một node; Control API điều phối việc tạo máy, mạng, tính tiền; khách thuê tự phục vụ qua web.

## Kiến trúc

```
Khách (trình duyệt, SSH)
   │  IPv4: trạm chuyển tiếp WireGuard (cổng 22000 - 23999, web 18000)
   │  IPv6: địa chỉ riêng từng VPS, mọi cổng
   ▼
Gateway (LXC trên node biên): Control API FastAPI · PostgreSQL · Headscale · web Flutter
   │  mạng riêng WireGuard / Headscale
   ▼
Node Proxmox VE (máy cá nhân, nhiều nơi): VM KVM, LXC, GPU passthrough
```

- **IaaS:** máy chủ ảo Linux (Debian, Ubuntu, CentOS Stream, Kali) và Windows (Server 2022, 11), máy chủ AI có GPU NVIDIA dựng sẵn CUDA, PyTorch, JupyterLab.
- **PaaS:** PostgreSQL có sẵn chuỗi kết nối; ứng dụng web triển khai từ kho Git công khai (trang tĩnh hoặc Node.js).
- **Tự phục vụ:** tạo máy một bước (tên, tài khoản root, mật khẩu đặt sẵn), console trên trình duyệt, cài lại hoặc đổi gói, ví nạp qua payOS, trừ tiền theo giờ, thông báo trong web và Gmail.
- **Quản trị:** thống kê, bản đồ node, người dùng, truy xuất dữ liệu, cập nhật gói và node, sao lưu và khôi phục CSDL.

## Thư mục

| Thư mục | Nội dung |
|---|---|
| `control-plane/` | Control API (FastAPI, SQLAlchemy, Alembic), worker đồng bộ node, payOS, tính tiền; test pytest |
| `web/` | Cổng web Flutter cho khách và quản trị; test widget |
| `node-agent/` | Agent trên từng node: chuyển cổng IPv4 (iptables), IPv6 riêng cho VPS (route /128, proxy NDP) |
| `scripts/he_dieu_hanh/` | Dựng và thử template hệ điều hành (Linux cloud image, Windows tự cài, máy chủ AI) |
| `scripts/paas/` | Template PaaS: PostgreSQL, nginx, Node.js và dịch vụ tự cấu hình khi khởi động |
| `scripts/relay/` | Trạm chuyển tiếp IPv4 qua WireGuard cho node sau CGNAT |
| `scripts/chuyen_he_dieu_hanh/` | Chuyển máy thành viên giữa Windows và Proxmox |

## Chạy thử cục bộ

```
cd control-plane
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m pytest -q
```

```
cd web
flutter pub get
flutter test
flutter build web --release
```

Cấu hình Control API đọc từ biến môi trường hoặc tệp `.env` (`DATABASE_URL`, `JWT_SECRET`, `FERNET_KEY`, `GATEWAY_HOST`, khóa payOS, SMTP). Tệp `.env` không nằm trong kho.

## Nhóm thực hiện

Nhóm 01, môn Điện toán đám mây, Viện Công nghệ số, Đại học Thủ Dầu Một: Nguyễn Tâm Bình (nhóm trưởng), Nguyễn Hoàng Thiên, Vũ Đức Thắng, Phạm Văn Tùng, Bùi Anh Tín, Nguyễn Hoàng Bảo Thiên.
