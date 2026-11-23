// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../widgets/common.dart';

String auditName(String action) => const {'instance.reserve': 'Đặt chỗ tài nguyên', 'instance.provision_failed': 'Cấp phát chưa thành công', 'instance.password_begin': 'Bắt đầu đổi mật khẩu', 'instance.password_failed': 'Đổi mật khẩu chưa thành công', 'instance.reinstall_begin': 'Bắt đầu cài lại hệ điều hành', 'instance.reinstall_failed': 'Cài lại chưa thành công', 'billing.suspend': 'Tạm dừng vì hết tiền', 'billing.stop_pending': 'Chờ node để dừng máy', 'payment.create': 'Tạo đơn nạp tiền', 'payment.paid': 'Thanh toán đơn nạp', 'payment.cancel': 'Hủy đơn nạp', 'wallet.topup': 'Nạp tiền vào ví', 'auth.register': 'Đăng ký tài khoản', 'auth.login': 'Đăng nhập', 'admin.bootstrap': 'Tạo quản trị viên', 'instance.create': 'Tạo máy chủ', 'instance.start': 'Bật máy chủ', 'instance.stop': 'Tắt máy chủ', 'instance.reboot': 'Khởi động lại máy chủ', 'instance.delete': 'Hủy máy chủ', 'instance.password': 'Đổi mật khẩu', 'instance.reinstall': 'Cài lại hệ điều hành', 'instance.error': 'Lỗi cấp phát máy chủ', 'instance.suspend': 'Tạm dừng vì hết tiền', 'instance.suspended': 'Tạm dừng vì hết tiền', 'instance.resolve_provisioning': 'Kiểm tra cấp phát gián đoạn', 'billing.topup': 'Nạp tiền vào ví', 'billing.usage': 'Thanh toán giờ sử dụng', 'payos.create': 'Tạo đơn nạp tiền', 'payos.paid': 'Thanh toán đơn nạp', 'payos.cancel': 'Hủy đơn nạp', 'node.create': 'Thêm node', 'node.sync': 'Đồng bộ node', 'node.check': 'Kiểm tra kết nối node', 'plan.create': 'Tạo gói tài nguyên'}[action] ?? 'Cập nhật dịch vụ';

class LogList extends StatefulWidget {
  final ApiClient api;
  final String path;
  const LogList({super.key, required this.api, required this.path});
  @override
  State<LogList> createState() => _LogListState();
}
class _LogListState extends State<LogList> {
  List<Json> logs = [];
  int offset = 0, generation = 0;
  bool busy = true;
  String? error;
  @override
  void initState() { super.initState(); load(); }
  @override
  void didUpdateWidget(LogList old) { super.didUpdateWidget(old); if (old.path != widget.path) { offset = 0; load(); } }
  Future<void> load() async {
    final ticket = ++generation;
    setState(() { busy = true; error = null; logs = []; });
    try { final data = await widget.api.list('${widget.path}?offset=$offset&limit=20'); if (mounted && ticket == generation) setState(() => logs = data); } catch (e) { if (mounted && ticket == generation) setState(() => error = e.toString()); }
    if (mounted && ticket == generation) setState(() => busy = false);
  }
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [if (busy) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), if (!busy && error == null && logs.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 24), child: Text('Chưa có thao tác trong trang này.')), for (final log in logs) Container(padding: const EdgeInsets.symmetric(vertical: 18), decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Theme.of(context).dividerColor))), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Padding(padding: EdgeInsets.only(top: 3), child: Icon(Icons.history_outlined, size: 20)), const SizedBox(width: 16), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(auditName('${log['action']}'), style: const TextStyle(fontWeight: FontWeight.w600)), Text('${date(log['created_at'])} · ${log['resource'].toString().replaceFirst('instance:', 'Máy chủ ')}', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.onSurfaceVariant))]))])), const SizedBox(height: 16), Wrap(spacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: [OutlinedButton(onPressed: busy || offset == 0 ? null : () { offset -= 20; load(); }, child: const Text('Trang trước')), Text('Trang ${offset ~/ 20 + 1}'), OutlinedButton(onPressed: busy || logs.length < 20 ? null : () { offset += 20; load(); }, child: const Text('Trang sau'))])]);
}
class LogsScreen extends StatefulWidget {
  final CloudState state;
  const LogsScreen({super.key, required this.state});
  @override
  State<LogsScreen> createState() => _LogsScreenState();
}
class _LogsScreenState extends State<LogsScreen> {
  int? selected;
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: widget.state, builder: (context, _) {
    final instances = widget.state.myInstances;
    final id = instances.where((v) => v['id'] == selected).firstOrNull?['id'] as int? ?? instances.firstOrNull?['id'] as int?;
    return PageBody(children: [const Heading('Nhật ký của bạn', 'Chọn máy chủ để xem các thao tác đã ghi nhận.'), if (id == null) const Notice('Chưa có VPS. Nhật ký thao tác sẽ xuất hiện sau khi tạo máy.') else ...[DropdownButtonFormField<int>(initialValue: id, isExpanded: true, decoration: const InputDecoration(labelText: 'Máy chủ'), items: [for (final v in instances) DropdownMenuItem(value: v['id'] as int, child: Text('${v['ten']}'))], onChanged: (v) => setState(() => selected = v)), const SizedBox(height: 24), LogList(api: widget.state.api, path: '/instances/$id/logs')]]);
  });
}
