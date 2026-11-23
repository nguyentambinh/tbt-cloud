// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../widgets/admin_common.dart';
import '../widgets/common.dart';

class AdminBackups extends StatefulWidget {
  final CloudState state;
  const AdminBackups({super.key, required this.state});
  @override
  State<AdminBackups> createState() => _AdminBackupsState();
}
class _AdminBackupsState extends State<AdminBackups> {
  Json? data;
  bool busy = true;
  int offset = 0;
  String? error, result;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    setState(() { busy = true; error = null; });
    try { final value = await widget.state.api.get('/admin/backups?offset=$offset&limit=20'); if (mounted) setState(() => data = value); } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  Future<void> action(String path, String method, [Json? body]) async {
    setState(() { busy = true; error = null; result = null; });
    try {
      final value = await widget.state.api.request('/admin/backups$path', method: method, body: body, timeoutSeconds: 620);
      if (!mounted) return;
      if (path.endsWith('/restore')) { message(context, '${value['detail']}'); widget.state.logout(); context.go('/dang-nhap'); return; }
      setState(() => result = value['detail'] as String? ?? 'Đã tạo bản sao lưu.');
      await load();
    } catch (e) { if (mounted) setState(() { error = e.toString(); busy = false; }); }
  }
  Future<void> restore(Json row) async {
    final input = await adminForm(context, 'Khôi phục cơ sở dữ liệu', [('confirmation', 'Nhập KHOI PHUC để xác nhận', '')]);
    if (input == null || !mounted) return;
    if (input['confirmation'] != 'KHOI PHUC') { message(context, 'Chưa đúng chữ xác nhận KHOI PHUC.'); return; }
    await action('/${row['name']}/restore', 'POST', input);
  }
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [const Notice('Khôi phục sẽ thay thế toàn bộ dữ liệu hiện tại. Hệ thống tạo một bản sao lưu an toàn trước khi khôi phục và thu hồi mọi phiên đăng nhập. Chỉ thực hiện trong thời gian bảo trì.'), Wrap(spacing: 12, runSpacing: 12, children: [FilledButton.icon(onPressed: busy ? null : () => action('', 'POST'), icon: const Icon(Icons.backup_outlined), label: Text(busy ? 'Đang xử lý…' : 'Tạo bản sao lưu')), OutlinedButton.icon(onPressed: busy ? null : load, icon: const Icon(Icons.refresh_outlined), label: const Text('Tải lại danh sách'))]), const SizedBox(height: 24), if (busy) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), if (result != null) Padding(padding: const EdgeInsets.only(bottom: 20), child: Text(result!)), if (data != null) ...[if (rows(data!['items']).isEmpty) const Text('Chưa có bản sao lưu. Tạo bản đầu tiên để bảo vệ dữ liệu.'), for (final row in rows(data!['items'])) ...[Padding(padding: const EdgeInsets.symmetric(vertical: 16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(date(row['created_at']), style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 8), SelectableText('${row['name']}'), Text('${row['size']} byte · Người tạo #${row['created_by']}${row['safety'] == true ? ' · Sao lưu trước khôi phục' : ''}'), Wrap(spacing: 12, runSpacing: 8, children: [TextButton.icon(onPressed: busy ? null : () => exportAdmin(context, widget.state.api, '/admin/backups/${row['name']}/download', '${row['name']}'), icon: const Icon(Icons.download_outlined), label: const Text('Tải về')), TextButton(onPressed: busy ? null : () => restore(row), child: const Text('Khôi phục')), TextButton(onPressed: busy ? null : () async { if (await confirm(context, 'Xóa bản sao lưu', 'Tệp sao lưu này sẽ bị xóa khỏi máy chủ.')) action('/${row['name']}', 'DELETE'); }, child: const Text('Xóa'))])])), const Divider(height: 1)], AdminPager(offset: offset, total: (data!['total'] as int?) ?? 0, busy: busy, onPage: (value) { offset = value; load(); })]]);
}
