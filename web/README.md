# TBT Cloud

Flutter Web cho nền tảng VPS trên máy tính cá nhân. Tiếng Việt, Material 3, theme sáng/tối theo hệ thống, font tự lưu trong `assets/fonts`. Hệ thống thiết kế mô tả ở `../DESIGN.md`.

## Mã nguồn

| Thư mục | Trách nhiệm |
|---|---|
| `lib/api` | HTTP JSON, JWT Bearer, localStorage, dữ liệu phiên và xử lý hết phiên |
| `lib/theme` | Màu, font, chữ số tabular, điều khiển Material và lựa chọn chữ |
| `lib/map` | CustomPainter địa hình, mesh, node, điểm VPS và đường chọn có chuyển động |
| `lib/screens` | Các tuyến giới thiệu, tài khoản, máy chủ, tạo/chi tiết/console, ví, node, nhật ký và quản trị |
| `lib/widgets` | Điều hướng, thanh tài nguyên, biểu đồ, xác nhận và thao tác vòng đời |
| `lib/qr` | QR Model 2 byte/M, phiên bản 1–40, Reed–Solomon, BCH, mặt nạ và bộ vẽ |
| `test` | Vector QR độc lập và kiểm tra bố cục bằng dữ liệu giả trên máy tính/điện thoại |

## Cấu hình

API mặc định cùng origin tại `/api/v1`. Biến biên dịch `--dart-define=API_BASE=https://host.example/api/v1` thay gốc HTTP; không chứa bí mật. Console luôn dùng cùng host trang tại `/api/v1/instances/{id}/console`, chuyển `https` thành `wss` và `http` thành `ws`.

JWT lưu ở khóa `tbt_cloud_jwt` của localStorage. Khi triển khai, dùng HTTPS và loại query string của console khỏi access log. Không đưa khóa Proxmox, payOS hoặc SMTP vào frontend. Trạng thái thanh toán phải đọc từ API; tham số URL trả về không xác nhận thanh toán.

Trước mọi lệnh Flutter/Dart trên máy Windows:

```powershell
$env:PUB_CACHE='D:\FlutterCache\pub'
$env:TEMP='D:\FlutterCache\tmp'
$env:TMP='D:\FlutterCache\tmp'
& 'D:\Android\Flutter\flutter\bin\flutter.bat' analyze --no-pub
& 'D:\Android\Flutter\flutter\bin\flutter.bat' test --no-pub --concurrency=1 test/qr_code_test.dart test/session_payment_test.dart
```

Không cần gói bổ sung từ mạng. `flutter_web_plugins` là thư viện SDK cho URL đường dẫn thường. Không có lệnh build trong quy trình kiểm tra của thay đổi này.

`test/session_payment_test.dart` kiểm tra phạm vi tính giờ của ví admin, phản hồi 401 của phiên cũ/mới, đăng xuất trong lúc tải dữ liệu, QR trong khung hẹp và phản hồi hỏi trạng thái đến muộn sau khi hủy đơn. `test/surfaces_test.dart` là lượt kiểm bố cục riêng, chạy tuần tự bằng `test --no-pub --concurrency=1 test/surfaces_test.dart`; ảnh được ghi vào `build/surfaces/`.

## Hợp đồng dữ liệu

- Giá công khai lấy từ `GET /plans`; node công khai từ `GET /public/map`. Khi mất API bản đồ, dữ liệu minh họa được ghi rõ. VPS trên bản đồ giới thiệu luôn là minh họa.
- Khóa SSH công khai bắt buộc cho VM và LXC. LXC dùng root, không có console serial VM hoặc đổi mật khẩu qua cloud-init.
- Dữ liệu ổ đĩa chỉ có dung lượng được cấp; mức dùng ghi “Chưa có số đo sử dụng”. Không suy ra từ lưu lượng đĩa.
- Nhật ký khách chọn từng VPS, lấy `/instances/{id}/logs`. API hiện không có nhật ký chung của khách. Quản trị đọc `/admin/audit-logs`.
- Đơn nạp tiền được hỏi mỗi ba giây, không chồng request; dừng khi rời trang hoặc đơn kết thúc. Có thể chọn “Xem đơn” để tiếp tục theo dõi đơn cũ. Tiền thực và cộng ví thuộc backend.
- Số giờ còn lại và trang Máy chủ chỉ dùng VPS của tài khoản hiện tại; quản trị vẫn xem toàn bộ VPS tại `/quan-tri`.

Để phục vụ sản phẩm đã được build riêng, đặt `WEB_DIR` ở Control API tới thư mục có `index.html`. Cấu hình payOS return/cancel URL lần lượt kết thúc bằng `/thanh-toan/ket-qua` và `/thanh-toan/huy` trên cùng origin.
