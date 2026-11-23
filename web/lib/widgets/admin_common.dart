// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../api/browser.dart';
import 'common.dart';

List<Json> rows(dynamic value) => value is List ? value.map((row) => Map<String, dynamic>.from(row as Map)).toList() : [];
String adminLabel(String key) => const {'id': 'Mã', 'ho_ten': 'Họ và tên', 'username': 'Tên tài khoản', 'email': 'Email', 'role': 'Quyền', 'is_blocked': 'Bị khóa', 'created_at': 'Ngày tạo', 'ten': 'Tên', 'dich_vu': 'Dịch vụ', 'trang_thai': 'Trạng thái', 'amount': 'Số tiền', 'kind': 'Loại', 'description': 'Nội dung', 'status': 'Trạng thái', 'paid_at': 'Ngày thanh toán', 'action': 'Thao tác', 'resource': 'Đối tượng', 'detail': 'Chi tiết', 'period': 'Kỳ', 'name': 'Tên', 'count': 'Số lượng', 'spent': 'Đã tiêu', 'revenue': 'Doanh thu payOS', 'wallet_balance': 'Tổng số dư ví', 'users': 'Người dùng', 'new_7': 'Mới trong 7 ngày', 'new_30': 'Mới trong 30 ngày', 'gia_theo_gio': 'Giá / giờ', 'active': 'Đang công bố', 'size': 'Dung lượng (byte)', 'created_by': 'Người tạo', 'user_id': 'Mã khách hàng', 'node_id': 'Mã node', 'plan_id': 'Mã gói', 'vcpu': 'vCPU', 'ram_mb': 'RAM (MB)', 'disk_gb': 'Đĩa (GB)', 'mo_ta': 'Mô tả', 'value': 'Giá trị', 'balance': 'Số dư ví'}[key] ?? key;
String adminValue(String key, dynamic value) => value == null ? 'Chưa có' : key == 'dich_vu' ? serviceName(value) : ['status', 'trang_thai'].contains(key) ? (['online', 'offline'].contains(value) ? (value == 'online' ? 'Trực tuyến' : 'Mất kết nối') : stateName(value)) : key == 'role' ? (value == 'admin' ? 'Quản trị viên' : 'Khách hàng') : key == 'kind' ? (const {'usage': 'Sử dụng dịch vụ', 'topup': 'Nạp tiền', 'adjustment': 'Điều chỉnh ví'}[value] ?? '$value') : value is bool ? (value ? 'Có' : 'Không') : ['amount', 'spent', 'revenue', 'wallet_balance', 'balance', 'gia_theo_gio'].contains(key) ? money(value) : key.endsWith('_at') ? date(value) : '$value';

class AdminTable extends StatelessWidget {
  final List<Json> items;
  final List<String> columns;
  final ValueChanged<Json>? onSelect;
  const AdminTable({super.key, required this.items, required this.columns, this.onSelect});
  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const Padding(padding: EdgeInsets.symmetric(vertical: 24), child: Text('Không có dữ liệu phù hợp với bộ lọc.'));
    return LayoutBuilder(builder: (context, c) => c.maxWidth < 700 ? Column(children: [for (final row in items) ...[InkWell(onTap: onSelect == null ? null : () => onSelect!(row), child: Padding(padding: const EdgeInsets.symmetric(vertical: 16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [for (final key in columns) Padding(padding: const EdgeInsets.only(bottom: 6), child: Text('${adminLabel(key)}: ${adminValue(key, row[key])}')), if (onSelect != null) const Padding(padding: EdgeInsets.only(top: 8), child: Row(mainAxisSize: MainAxisSize.min, children: [Text('Mở chi tiết'), Icon(Icons.chevron_right)]))]))), const Divider(height: 1)]]) : SingleChildScrollView(scrollDirection: Axis.horizontal, child: DataTable(showCheckboxColumn: false, horizontalMargin: 0, columnSpacing: 28, columns: [for (final key in columns) DataColumn(label: Text(adminLabel(key)))], rows: [for (final row in items) DataRow(onSelectChanged: onSelect == null ? null : (_) => onSelect!(row), cells: [for (final key in columns) DataCell(ConstrainedBox(constraints: const BoxConstraints(maxWidth: 260), child: Text(adminValue(key, row[key]), maxLines: 2, overflow: TextOverflow.ellipsis)))])])));
  }
}

class AdminPager extends StatelessWidget {
  final int offset, total, limit;
  final bool busy;
  final ValueChanged<int> onPage;
  const AdminPager({super.key, required this.offset, required this.total, this.limit = 20, required this.busy, required this.onPage});
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.symmetric(vertical: 20), child: Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: [Text(total == 0 ? '0 kết quả' : '${offset + 1} – ${(offset + limit).clamp(0, total)} / $total'), OutlinedButton(onPressed: busy || offset == 0 ? null : () => onPage((offset - limit).clamp(0, total)), child: const Text('Trang trước')), OutlinedButton(onPressed: busy || offset + limit >= total ? null : () => onPage(offset + limit), child: const Text('Trang sau'))]));
}

Future<void> exportAdmin(BuildContext context, ApiClient api, String path, String filename) async {
  try { final bytes = await api.request(path, binary: true) as List<int>; saveDownload(bytes, filename); if (context.mounted) message(context, 'Đã chuẩn bị tệp tải về.'); } catch (e) { if (context.mounted) message(context, e.toString()); }
}

Future<Json?> adminForm(BuildContext context, String title, List<(String, String, String)> fields, {List<String> numeric = const [], List<String> optional = const []}) async {
  final controllers = {for (final field in fields) field.$1: TextEditingController(text: field.$3)};
  final form = GlobalKey<FormState>();
  final result = await showDialog<Json>(context: context, builder: (context) => AlertDialog(title: Text(title), content: SizedBox(width: 480, child: SingleChildScrollView(child: Form(key: form, child: Column(mainAxisSize: MainAxisSize.min, children: [for (final field in fields) Padding(padding: const EdgeInsets.only(bottom: 16), child: TextFormField(controller: controllers[field.$1], keyboardType: numeric.contains(field.$1) ? const TextInputType.numberWithOptions(decimal: true, signed: true) : TextInputType.text, decoration: InputDecoration(labelText: field.$2), validator: (text) { if (optional.contains(field.$1) && (text ?? '').trim().isEmpty) return null; if ((text ?? '').trim().isEmpty) return 'Vui lòng nhập ${field.$2.toLowerCase()}.'; if (numeric.contains(field.$1) && num.tryParse(text!) == null) return 'Nhập một số hợp lệ.'; return null; }))])))), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Quay lại')), FilledButton(onPressed: () { if (form.currentState!.validate()) Navigator.pop(context, {for (final field in fields) field.$1: controllers[field.$1]!.text.trim()}); }, child: const Text('Xác nhận'))]));
  for (final controller in controllers.values) { controller.dispose(); }
  return result;
}
