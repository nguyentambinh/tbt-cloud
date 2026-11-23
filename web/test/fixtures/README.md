# Vector QR mức M

`qr_m_vectors.json` chứa ma trận và codeword cố định từ bộ mã hóa độc lập QRCode của Kazuhiko Arase (MIT), bản có sẵn trong npm qrcode-terminal. Sinh ở chế độ byte, mức sửa lỗi M, mặt nạ cố định 0, 3, 7; phiên bản 1, 7, 13, 26, 40. Thư viện tham chiếu chỉ dùng ngoại tuyến để sinh dữ liệu kiểm chứng, không được thêm vào ứng dụng hay pubspec.

Kiểm cả codeword xen kẽ, sửa lỗi Reed–Solomon, alignment, BCH thông tin phiên bản, định dạng và mọi ô ma trận. Các test bổ sung kiểm ranh giới dung lượng và UTF-8. Quy tắc mã hóa: ISO/IEC 18004, QR Model 2, quiet zone bốn module ở QrView.
