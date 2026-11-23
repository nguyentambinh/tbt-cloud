---
name: TBT Cloud
description: Hệ ký hiệu bản đồ cho cổng tự phục vụ VPS trên máy cá nhân.
colors:
  primary: "#7B2CBF"
  primary-ink-dark: "#D5AFF1"
  olive: "#A5B36A"
  yellow: "#FFD24D"
  contour-brown: "#8C5A2B"
  mesh-blue: "#5FA7D6"
  surface-light: "#FFFFFF"
  surface-dark: "#15171A"
  ink-light: "#20241F"
  ink-dark: "#F4F3EF"
  muted-light: "#575B51"
  muted-dark: "#BEBDB5"
  outline-light: "#B7B8AC"
  outline-dark: "#68685D"
  container-light: "#F2F4ED"
  container-dark: "#282C2A"
  map-light: "#FAFBF7"
  map-dark: "#1B201D"
typography:
  display:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "76px"
    fontWeight: 600
    lineHeight: 1.02
  display-compact:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "56px"
    fontWeight: 600
    lineHeight: 1.05
  headline:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "40px"
    fontWeight: 600
    lineHeight: 1.12
  headline-medium:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "32px"
    fontWeight: 600
  title:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "26px"
    fontWeight: 600
  body:
    fontFamily: "Be Vietnam Pro, sans-serif"
    fontSize: "14px"
    lineHeight: 1.6
  body-large:
    fontFamily: "Be Vietnam Pro, sans-serif"
    fontSize: "16px"
    lineHeight: 1.65
  label:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    letterSpacing: "0.3px"
  button:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "19px"
    fontWeight: 600
  description-label:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "17px"
    fontWeight: 600
rounded:
  status: "4px"
  control: "6px"
  panel: "8px"
spacing:
  gap-small: "8px"
  gap: "12px"
  field: "16px"
  mobile-page: "20px"
  panel: "24px"
  section: "32px"
  desktop-page: "40px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface-light}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "15px 22px"
  button-outlined:
    textColor: "{colors.ink-light}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
  button-text:
    textColor: "{colors.ink-light}"
    height: "48px"
  input:
    rounded: "{rounded.control}"
    padding: "16px"
  navigation-selected:
    textColor: "{colors.primary}"
  status-running:
    backgroundColor: "rgba(165,179,106,0.35)"
    textColor: "{colors.ink-light}"
    rounded: "{rounded.status}"
    padding: "5px 10px"
  panel:
    rounded: "{rounded.panel}"
    padding: "24px"
  description-row:
    typography: "{typography.description-label}"
    height: "52px"
  resource-bar:
    backgroundColor: "{colors.olive}"
    height: "6px"
---

# Design System: TBT Cloud

## Overview

**Creative North Star: "Rừng chạy được"**

Máy cá nhân là địa hình; Gateway, node và VPS tạo thành mạng có thể đọc và thao tác. Bề mặt trắng hoặc than chì giữ thông tin rõ ràng; vòng tròn đánh số, đường mesh và nét đồng mức tạo bản sắc bản đồ. Trang vận hành ưu tiên trạng thái, tài nguyên và chi phí theo giờ.

Hệ thống dùng chữ hẹp cho tiêu đề và số, chữ tiếng Việt thoáng cho nội dung. Nền đồng mức nằm trong bản đồ; các phần còn lại dùng hàng thông tin, khoảng trống và viền mảnh. Bản đồ và QR được vẽ bằng painter; UI không dùng raster. Ảnh mock chỉ là tham khảo.

**Key Characteristics:**

- Sáng và tối theo hệ thống.
- Vòng tròn số nối VPS với vị trí trên mạng.
- Màu có nhiệm vụ, số liệu có đơn vị.
- Bề mặt phẳng, thông tin tách bằng hàng và khoảng trống.

**Evidence nền: SOURCE.** Trích từ `web/lib/theme/cloud_theme.dart`, `widgets/common.dart`, `widgets/app_shell.dart`, `map/network_map.dart`, các màn máy chủ, giới thiệu, tạo VPS, chi tiết, ví và `web/pubspec.yaml`. Các bề mặt ngoài phạm vi trang chủ, header và quản trị chưa được xác minh bằng ảnh trong lượt đối chiếu này. Tài liệu này không xác nhận giao diện đạt nghiệm thu hoặc WCAG AA.

**Evidence trang chủ, header và quản trị: SOURCE + WIDGET VIEWPORT.** Đối chiếu thêm `widgets/brand_logo.dart`, `widgets/admin_common.dart`, `screens/landing_screen.dart` và `screens/admin*.dart`. Bộ ảnh widget ở `web/build/surfaces/admin/` có các bề rộng (390/768/1440/1920px), sáng/tối; các mẫu đã xem trực tiếp gồm `landing-390.0-light.png`, `pricing-768.0-dark.png`, `tong-quan-1440.0-light.png` và `map-owner-1920.0-dark.png`. Đây là render widget với dữ liệu kiểm thử, chưa browser verified; không suy rộng kết quả sang mọi trạng thái, dữ liệu thật hoặc WCAG AA.

## Colors

Màu đất và mạng nằm trên nền trung tính; các token có hậu tố light/dark đi cùng chế độ tương ứng.

### Primary

- **Tím đường chọn — primary:** đường Gateway → node → VPS được chọn, hành động chính, điều khiển đang chọn và focus ô nhập.
- **Tím chữ tối — primary-ink-dark:** chữ điều hướng và tab đang chọn trên nền tối.

**The Tím Có Nhiệm Vụ Rule.** Tím chỉ đánh dấu đường đang chọn, hành động chính và điều khiển đang chọn. Ngoại lệ có phạm vi: biểu đồ CPU/RAM dùng đường tím cùng vùng tím nhạt như hồ sơ độ cao; không mở rộng ngoại lệ sang nội dung khác.

### Secondary

- **Ô liu — olive:** vùng node hoạt động, thanh tài nguyên và trạng thái đang chạy.
- **Vàng — yellow:** cảnh báo, trạng thái cần chú ý, số dư sắp hết; luôn có nhãn chữ đi kèm.

### Tertiary

- **Nâu đồng mức — contour-brown:** địa hình, ký hiệu Gateway và nét phụ.
- **Xanh mesh — mesh-blue:** mạng phủ; hỗ trợ focus và vùng chọn văn bản.

### Neutral

- **surface-light / surface-dark:** nền trang trắng và than chì.
- **ink-light / ink-dark:** chữ chính của từng chế độ.
- **muted-light / muted-dark:** chữ phụ, nhãn, gợi ý nhập.
- **outline-light / outline-dark:** viền ô nhập và nút phụ.
- **container-light / container-dark:** rãnh tài nguyên và bề mặt trạng thái trung tính.
- **map-light / map-dark:** nền riêng của bản đồ.

Độ trong suốt nằm ở thành phần: trạng thái chạy dùng ô liu (35%), cảnh báo dùng vàng (35% sáng, 20% tối), đồng mức dùng nâu (18% sáng, 24% tối). Dải sắc độ trong sidecar chỉ để xem màu, được tổng hợp bằng OKLCH; không phải token đang dùng trong ứng dụng.

## Typography

**Display Font:** Barlow Condensed, dự phòng sans-serif.
**Body Font:** Be Vietnam Pro, dự phòng sans-serif.

Font đóng gói cục bộ trong `web/assets/fonts/`, khai báo ở `web/pubspec.yaml`; không tải font mạng. Barlow Condensed có trọng lượng 500/600/700; Be Vietnam Pro có 400/500/600/700. `figures` dùng số tabular cho giá, thời gian và tài nguyên.

### Hierarchy

- **Display / Display compact:** tiêu đề giới thiệu và số dư lớn; token compact dùng khi màn hình hẹp.
- **Headline / Headline medium:** tên trang, mục và tên VPS.
- **Title:** tiêu đề khối nhỏ.
- **Body / Body large:** thông tin và giải thích; kích thước và nhịp dòng theo frontmatter.
- **Label / Description label:** nhãn thao tác và nhãn cột; chỉ nhãn dữ liệu được chuyển thành chữ hoa.
- **Button:** nhãn hành động chính; nút viền dùng nhãn nhỏ hơn một bậc.

**The Hai Giọng Chữ Rule.** Barlow Condensed dẫn hướng và thể hiện số; Be Vietnam Pro giữ nội dung đọc liên tục. Chữ hoa dành cho nhãn dữ liệu, không thêm dòng eyebrow trên tiêu đề.

## Layout

Khung nội dung có bề rộng tối đa (1440px), căn giữa. `PageBody` dùng lề mobile-page dưới ngưỡng cửa sổ (700px), desktop-page từ ngưỡng đó. Khoảng cách lặp lại theo các token spacing; mẫu hàng thông tin cao tối thiểu (52px).

Header cao (82px), dùng cùng khung (1440px) và lề ngang với PageBody; khoảng trống co giãn giữ cụm tài khoản ở mép phải phần nội dung. Trang công khai chỉ giữ biểu tượng logo khi cửa sổ dưới (430px). AppShell sau đăng nhập chỉ giữ biểu tượng dưới (600px), chuyển điều hướng sang drawer dưới (1100px). Quản trị có tập điều hướng riêng và không hiện ví. Trang máy chủ dưới (700px) dùng bản đồ cao (180px), PageView mỗi VPS một trang và nhóm thao tác tại đáy; bản desktop dùng hai cột tỷ lệ (6:4), cách nhau panel spacing. Đây là mẫu của trang máy chủ, không bắt mọi trang lặp lại.

Lưới gói chuyển 1/2/3 cột theo bề rộng cục bộ tại (600px/1000px), cách nhau mobile-page spacing. Các khối giới thiệu và cặp biểu đồ chuyển hàng/cột tại bề rộng cục bộ (850px). Form tạo VPS giới hạn (760px), form đăng nhập (460px). Không gộp ngưỡng theo cửa sổ và ngưỡng LayoutBuilder thành một breakpoint toàn cục.

Bảng quản trị chuyển thành các hàng nhãn–giá trị khi bề rộng cục bộ dưới (700px); phía trên ngưỡng dùng DataTable trong vùng cuộn riêng. Nhóm lọc, thao tác và phân trang dùng Wrap để xuống hàng. Heading đặt thao tác sau phần chữ dưới (600px). Đây là cách thích ứng của các thành phần quản trị, không thay mẫu hàng của cổng khách.

## Elevation & Depth

Bề mặt chính phẳng; Panel và bản đồ không khai báo bóng. Khoảng trống, viền và nền trạng thái thể hiện phân cấp. Dialog, drawer, menu và phản hồi hover/focus/pressed kế thừa Material 3; không trích giá trị bóng mặc định thành token riêng khi chưa kiểm kết quả render.

**The Phẳng Trong Nội Dung Rule.** Dùng viền mảnh và khoảng cách để nhóm nội dung; không dùng bóng lệch cứng hoặc thêm card trong card để tạo độ sâu.

## Shapes

Các góc status/control/panel theo frontmatter. Nút, ô nhập và khung bản đồ có góc mềm nhỏ; ký hiệu VPS là vòng tròn, Gateway là tam giác viền nâu. Viền thông thường mảnh (1px); focus ô nhập, vòng VPS và lựa chọn gói dùng nét nhấn (2px). Ký hiệu VPS trong bản đồ rộng (31px) với vùng thao tác (44px).

## Components

### Buttons

Nút chính tím chữ trắng; nút viền và nút chữ dùng màu mực của chế độ. Nút chính và nút viền có kích thước tối thiểu (48×48px), nút chữ (44×48px), nút biểu tượng (44×44px). Trạng thái disabled xuất hiện khi đang xử lý hoặc thao tác không hợp lệ; nhãn bận mô tả việc đang làm. Hover/focus/pressed kế thừa Material 3, không có chuyển động nhấc nút tùy biến.

### Chips

`StatusMark` là nhãn trạng thái chữ thường, nền trong suốt có sắc, không phải nút. Running dùng olive, stopped dùng container, các trạng thái khác dùng yellow; chữ giải nghĩa trạng thái luôn hiện. ChoiceChip chọn loại máy/số tiền và SegmentedButton chọn giờ/ngày/tuần kế thừa Material 3; chưa trích các màu dẫn xuất của chúng thành token chuẩn.

### Cards / Containers

Panel có viền mảnh, không nền phủ hay bóng riêng, đệm panel. Lựa chọn gói dùng cùng góc bo, nền tím nhạt (7%) và viền tím khi được chọn. Danh sách VPS ưu tiên hàng chia bằng đường mảnh; hàng đang chọn có nền tím rất nhẹ (6%).

### Inputs / Fields

Ô nhập có đệm field, viền outline của chế độ và góc control. Focus chuyển viền sang primary với nét (2px). Gợi ý và nhãn dùng muted; lỗi và disabled kế thừa Material. Mật khẩu có ẩn/hiện, nút biểu tượng có tooltip.

### Navigation

Điều hướng desktop nằm ngang, mục hiện tại có chữ tím và gạch chân tím; nền tối dùng primary-ink-dark cho chữ. Drawer thay thanh mục khi thiếu chiều ngang. Ví luôn hiện số dư và số giờ ước tính khi có VPS chạy; thời gian thấp có chữ cảnh báo. Chi tiết VPS dùng tab dạng nút chữ với gạch chân ở mục đang chọn.

### Brand

Logo dùng ba máy cá nhân ô liu, viền nâu, nối bằng mesh xanh; không dùng tím trang trí. BrandLogo vẽ biểu tượng bằng painter trong khung (42×42px), tên Barlow Condensed theo màu mực của chế độ, cỡ (30px); bản đầy đủ nằm trong khung (170×48px), bản gọn chỉ giữ biểu tượng. Nhãn ngữ nghĩa là TBT Cloud. Hero mở rộng cùng hình học bằng code, dùng nhãn nội dung và mũi tên vẽ nét. SVG sáng/tối và biểu tượng vuông ở `web/web/brand/`; icon PNG xuất từ cùng painter phục vụ icon web.

### Service categories and price levels

Tiêu đề nhóm dịch vụ dùng nâu cho VPS, xanh mesh cho PostgreSQL và ô liu cho ứng dụng web, luôn đi với tên nhóm; màu chữ được pha với mực theo chế độ. Các mức gói dùng nhãn trung tính ngay dưới giá theo giờ, trước ước tính tháng; nhãn mô tả cấp giá trong nhóm, không trở thành eyebrow trên tên gói hay token màu mới.

### Administration data

Số tiền trong bảng, tổng số liệu và chi tiết dùng chung định dạng có dấu phân nhóm và đơn vị đồng. Biểu đồ doanh thu dùng cột ô liu, lưới mảnh, ghi mức cao nhất và kỳ đầu/cuối; trạng thái không có dữ liệu hoặc chưa có thanh toán được viết rõ. Hàng và nhóm thao tác tiếp tục dùng viền, khoảng trống và thành phần Material hiện có.

### Network map

Đồng mức nâu nằm trong khung bản đồ; mạng mesh xanh nối các node quanh Gateway. Đường tím chỉ nối tới VPS đang chọn, vòng tròn số đồng bộ lựa chọn với danh sách. Đường được vẽ trong (850ms), easing `easeOutExpo`; tắt animation theo cài đặt giảm chuyển động. Nhãn bản đồ là tên của chính hình, không phải eyebrow trang.

### Description rows and resources

Hàng mô tả có cột nhãn chữ hoa rộng (100px hoặc 145px), giá trị chọn/sao chép được. Thanh tài nguyên cao (6px), cùng thang (0–100%), đổi vàng khi vượt (85%); dữ liệu thiếu ghi rõ chưa có số đo. Biểu đồ CPU/RAM cùng thang, chia lưới mỗi (25%), để trống khoảng thiếu dữ liệu, không làm mượt đường hoặc thêm điểm giả.

Sidecar chứa bản chuyển HTML/CSS tĩnh của các thành phần Flutter để xem mẫu. Chúng không thay thế render Flutter; các lớp trạng thái trong mẫu là mô phỏng Material, chưa visual verified.

### Payment QR

QR đen trên nền trắng có quiet zone bốn module, rộng tối đa 300px và co theo khung thanh toán trên điện thoại. Mã và trạng thái thuộc đơn đang xem; phản hồi từ lượt theo dõi cũ không được thay trạng thái sau khi đổi hoặc hủy đơn. Thời gian còn lại trong Ví và thanh điều hướng chỉ tính từ VPS đang chạy của chính tài khoản.

## Do's and Don'ts

### Do:

- **Do** dùng theme sáng/tối và font cục bộ cho mọi màn.
- **Do** giữ số đo, trạng thái, đơn vị và nhãn chữ đi cùng màu.
- **Do** giữ đồng mức trong bản đồ và số VPS đồng bộ giữa bản đồ với danh sách.
- **Do** giữ tím theo vai trò đã nêu, gồm ngoại lệ biểu đồ CPU/RAM.
- **Do** xem giao diện ở kích thước thực trước khi coi token dẫn xuất hoặc trạng thái Material là đã kiểm.

### Don't:

- **Don't** dùng chữ gradient, glass, sọc dày bên cạnh hoặc bóng lệch cứng.
- **Don't** lồng card trong card, thêm eyebrow hoặc dùng emoji làm biểu tượng.
- **Don't** dùng tím trang trí cho nội dung không thuộc các vai trò đã xác định.
- **Don't** đưa ảnh mock vào UI hoặc thay bản đồ/QR painter bằng raster.
- **Don't** chuẩn hóa lỗi render, mất tương phản hoặc màu Material dẫn xuất chưa kiểm thành quy tắc kế thừa.

**Not canonized:** màu nền/chữ dẫn xuất của ChoiceChip, SegmentedButton, drawer, divider và overlay Material; các biến thể tím tối riêng lẻ chưa được kiểm tương phản. Chưa sửa hay coi chúng là lỗi xác nhận vì chỉ có bằng chứng SOURCE, thiếu capture Flutter thực tế.
