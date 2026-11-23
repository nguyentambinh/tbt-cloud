# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Flutter Web (thư mục `web/`), gọi Control API FastAPI (`control-plane/`, tiền tố `/api/v1`, JWT Bearer). Một giao diện phải dùng được trên máy tính (chính) và điện thoại.

## Users

- **Khách thuê VPS** (người dùng chính): sinh viên, lập trình viên cần một máy chủ Linux nhỏ để chạy thử dịch vụ, học tập, làm đồ án. Họ tự đặt VPS, nạp tiền, bật/tắt, mở console, cài lại hệ điều hành, lấy thông tin SSH, theo dõi chi phí; thường thao tác trên máy tính, đôi khi mở trên điện thoại để xem trạng thái hoặc khởi động lại máy.
- **Quản trị viên** (thành viên Nhóm 01): theo dõi node, gói, người dùng, VPS, nhật ký. Phần quản trị làm tối thiểu.
- **Giảng viên chấm đồ án**: xem demo, cần thấy rõ hệ thống chạy thật.

## Product Purpose

TBT Cloud cung cấp máy chủ ảo (VPS) chạy trên máy tính cá nhân của các thành viên nhóm, gom thành một nền tảng đám mây phân tán. Khách tự phục vụ hoàn toàn như ở một nhà cung cấp thật: đặt VPS, thanh toán, quản lý vòng đời máy. Thành công nghĩa là khách tạo được VPS và SSH vào trong vài phút mà không cần quản trị viên can thiệp, và luôn biết mình đang trả bao nhiêu.

## Positioning

Hạ tầng là các máy cá nhân ở nhiều nơi (mỗi máy một node Proxmox VE độc lập, nối nhau bằng mạng WireGuard do Headscale điều phối), không phải trung tâm dữ liệu. Giao diện phải cho thấy điều đó: VPS đang nằm trên node nào, node còn bao nhiêu tài nguyên.

## Operating Context

- Khách đăng ký, nạp tiền vào ví bằng **payOS** (chuyển khoản/QR ngân hàng), chọn gói (vCPU, RAM, đĩa, giá theo giờ), tạo VPS từ template (Debian 13 cloud-init hoặc LXC).
- Tiền bị trừ theo giờ; hết số dư thì VPS bị dừng.
- Truy cập VPS qua SSH tới cổng riêng do gateway cấp, hoặc console trên trình duyệt.
- Demo trước giảng viên: tạo VPS, thấy nó xuất hiện trên node, SSH vào, xem ví bị trừ và nhật ký.

## Capabilities and Constraints

- Có sẵn (API): đăng ký/đăng nhập, gói, tạo/xem/bật/tắt/khởi động lại/xóa VPS, ví và giao dịch, quản trị node, nhật ký kiểm tra. Đang bổ sung: thông tin đăng nhập VPS (mật khẩu ẩn/hiện), biểu đồ tài nguyên, cài lại hệ điều hành, nhật ký thao tác theo VPS, console web (WebSocket).
- Trang chi tiết VPS phải có đủ: thẻ dịch vụ (gói, hostname, IP), chi phí, ngày tạo và hạn đã trả trước, hủy dịch vụ; khối máy chủ có trạng thái và nút Tắt / Khởi động lại / Console; tab Tổng quan / Cài lại hệ điều hành / Nhật ký thao tác; CPU / RAM / Ổ đĩa có mức dùng; thông tin đăng nhập có sao chép và hướng dẫn SSH; bảng chi tiết (IP, hệ điều hành, tên máy chủ, máy ảo, node, console); biểu đồ tài nguyên.
- Thanh toán thật qua payOS (cần khóa client id, api key, checksum key của tài khoản payOS nhóm). Hạ tầng nằm sau CGNAT nên xác nhận thanh toán ưu tiên cách hỏi trạng thái giao dịch từ payOS thay vì phụ thuộc webhook.
- Giao diện tiếng Việt. Thông báo lỗi là câu người thật hiểu được, không lộ mã lỗi hay thông báo gốc của máy chủ.
- Ảnh trong `huong_dan/tham_khao_giao_dien/` chỉ dùng để biết đủ thành phần của trang khách hàng; không sao chép giao diện.

## Brand Commitments

- Tên: **TBT Cloud**. Logo ba máy cá nhân nối bằng nét mesh, dùng ô liu/xanh mesh/viền nâu; chữ Barlow Condensed và Be Vietnam Pro, nền sáng/tối theo DESIGN.md. SVG sáng/tối và biểu tượng vuông ở `web/web/brand/`; header và hero vẽ bằng code, icon PNG xuất từ cùng painter. Giao diện được kiểm bằng ảnh widget ở 390/768/1440/1920px, chưa nghiệm thu trên trình duyệt thật.

## Evidence on Hand

- Hệ thống chạy thật: node `pve-asus` (Proxmox VE 9.2), gateway (Control API + PostgreSQL + Headscale), VPS tạo qua API trong khoảng 3 giây, có IP sau khoảng 18 giây; số đo và ảnh trong `NHAT_KY_THUC_HIEN.md` và `BaoCao/minh_chung/`.
- Không có khách hàng thật, đánh giá, số liệu doanh thu: không được bịa.

## Product Principles

1. Khách tự làm được mọi việc với VPS của mình, không phải nhờ quản trị viên.
2. Tiền luôn minh bạch: số dư, giá theo giờ, chi phí tích lũy của từng VPS hiển thị rõ ở nơi khách ra quyết định.
3. Cho thấy hạ tầng thật: node nào, ở đâu, còn bao nhiêu, đang chạy ra sao.
4. Thao tác nguy hiểm (hủy, cài lại hệ điều hành, đổi mật khẩu) luôn xác nhận rõ hậu quả trước khi làm.

## Accessibility & Inclusion

Dùng được trên điện thoại (vùng chạm đủ lớn, không cuộn ngang), tương phản chữ đạt mức WCAG AA.
