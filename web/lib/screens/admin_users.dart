// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../api/api_client.dart';
import '../widgets/admin_common.dart';
import '../widgets/common.dart';

class AdminUsers extends StatefulWidget {
  final ApiClient api;
  final int? userId;
  final int? actorId;
  const AdminUsers({super.key, required this.api, this.userId, this.actorId});
  @override
  State<AdminUsers> createState() => _AdminUsersState();
}
class _AdminUsersState extends State<AdminUsers> {
  final search = TextEditingController();
  Json? data;
  String? error;
  bool busy = true;
  int offset = 0;
  String status = '', tab = 'transactions';
  @override
  void initState() { super.initState(); load(); }
  @override
  void dispose() { search.dispose(); super.dispose(); }
  Future<void> load() async {
    setState(() { busy = true; error = null; });
    try {
      final path = widget.userId == null ? '/admin/data/users?offset=$offset&limit=20&q=${Uri.encodeQueryComponent(search.text.trim())}${status.isEmpty ? '' : '&column=is_blocked&value=${status == 'blocked' ? 'true' : 'false'}'}' : '/admin/users/${widget.userId}?offset=$offset&limit=20';
      final result = await widget.api.get(path);
      if (mounted) setState(() => data = result);
    } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  Future<void> mutate(String path, String method, [Json? body]) async {
    setState(() { busy = true; error = null; });
    try { await widget.api.request('/admin/users/${widget.userId}$path', method: method, body: body); if (!mounted) return; message(context, 'Đã cập nhật tài khoản.'); if (method == 'DELETE') { context.go('/quan-tri/nguoi-dung'); } else { await load(); } } catch (e) { if (mounted) setState(() { error = e.toString(); busy = false; }); }
  }
  Future<void> reset() async {
    if (!await confirm(context, 'Đặt lại mật khẩu', 'Mọi phiên cũ của tài khoản sẽ bị thu hồi. Mật khẩu tạm chỉ hiện một lần.')) return;
    setState(() { busy = true; error = null; });
    try { final result = await widget.api.post('/admin/users/${widget.userId}/reset-password'); if (!mounted) return; await showDialog<void>(context: context, builder: (context) => AlertDialog(title: const Text('Mật khẩu tạm'), content: Column(mainAxisSize: MainAxisSize.min, children: [const Text('Sao chép và chuyển riêng cho khách hàng. Đóng hộp thoại sẽ không xem lại được.'), const SizedBox(height: 20), SelectableText('${result['temporary_password']}')]), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Đã lưu mật khẩu'))])); } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  @override
  Widget build(BuildContext context) {
    if (widget.userId == null) return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Wrap(spacing: 12, runSpacing: 12, children: [SizedBox(width: 380, child: TextField(controller: search, onSubmitted: (_) { offset = 0; load(); }, decoration: const InputDecoration(labelText: 'Tên, tài khoản hoặc email', prefixIcon: Icon(Icons.search_outlined)))), SizedBox(width: 200, child: DropdownButtonFormField<String>(initialValue: status, decoration: const InputDecoration(labelText: 'Trạng thái'), items: const [DropdownMenuItem(value: '', child: Text('Tất cả')), DropdownMenuItem(value: 'active', child: Text('Đang hoạt động')), DropdownMenuItem(value: 'blocked', child: Text('Bị khóa'))], onChanged: busy ? null : (value) { status = value!; offset = 0; load(); })), FilledButton(onPressed: busy ? null : () { offset = 0; load(); }, child: const Text('Tìm kiếm'))]), const SizedBox(height: 24), if (busy) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), if (data != null) ...[AdminTable(items: rows(data!['items']), columns: const ['ho_ten', 'username', 'email', 'role', 'is_blocked'], onSelect: (row) => context.go('/quan-tri/nguoi-dung/${row['id']}')), AdminPager(offset: offset, total: (data!['total'] as int?) ?? 0, busy: busy, onPage: (value) { offset = value; load(); })]]);
    final own = widget.userId == widget.actorId;
    final page = data?[tab] is Map ? Map<String, dynamic>.from(data![tab] as Map) : <String, dynamic>{};
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [TextButton.icon(onPressed: () => context.go('/quan-tri/nguoi-dung'), icon: const Icon(Icons.arrow_back), label: const Text('Danh sách người dùng')), if (busy) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), if (data != null) ...[for (final field in [('Họ và tên', 'ho_ten'), ('Tên tài khoản', 'username'), ('Email', 'email'), ('Quyền', 'role'), ('Bị khóa', 'is_blocked'), ('Ngày tạo', 'created_at')]) DescriptionRow(field.$1, adminValue(field.$2, data![field.$2])), DescriptionRow('Số dư ví', money(data!['balance'])), const SizedBox(height: 24), Wrap(spacing: 12, runSpacing: 12, children: [OutlinedButton(onPressed: busy || own ? null : () async { final block = data!['is_blocked'] != true; if (await confirm(context, block ? 'Khóa tài khoản' : 'Mở khóa tài khoản', 'Thao tác này thu hồi các phiên đăng nhập cũ.')) mutate('/state', 'PUT', {'is_blocked': block}); }, child: Text(data!['is_blocked'] == true ? 'Mở khóa tài khoản' : 'Khóa tài khoản')), OutlinedButton(onPressed: busy ? null : reset, child: const Text('Đặt lại mật khẩu')), OutlinedButton(onPressed: busy || own ? null : () async { final role = data!['role'] == 'admin' ? 'user' : 'admin'; if (await confirm(context, 'Đổi quyền tài khoản', role == 'admin' ? 'Tài khoản sẽ có toàn quyền quản trị và không thể thuê dịch vụ mới.' : 'Tài khoản sẽ chuyển thành khách hàng.')) mutate('/role', 'PUT', {'role': role}); }, child: const Text('Đổi quyền')), FilledButton(onPressed: busy ? null : () async { final input = await adminForm(context, 'Điều chỉnh số dư ví', [('amount', 'Số tiền cộng hoặc trừ (đ)', ''), ('reason', 'Lý do bắt buộc', '')], numeric: ['amount']); if (input != null) mutate('/wallet', 'POST', {...input, 'request_id': 'wallet-${DateTime.now().microsecondsSinceEpoch}'}); }, child: const Text('Điều chỉnh ví')), OutlinedButton(onPressed: busy || own ? null : () async { if (await confirm(context, 'Xóa người dùng', 'Chỉ xóa khi không còn dịch vụ. Thông tin đăng nhập bị ẩn danh; giao dịch và nhật ký được giữ để đối soát.')) mutate('', 'DELETE'); }, child: const Text('Xóa người dùng'))]), const SizedBox(height: 32), Wrap(spacing: 12, runSpacing: 8, children: [for (final item in [('transactions', 'Giao dịch ví'), ('instances', 'Dịch vụ'), ('logs', 'Nhật ký')]) ChoiceChip(label: Text(item.$2), selected: tab == item.$1, onSelected: busy ? null : (_) { tab = item.$1; offset = 0; load(); })]), const SizedBox(height: 20), AdminTable(items: rows(page['items']), columns: tab == 'transactions' ? const ['created_at', 'kind', 'amount', 'description'] : tab == 'instances' ? const ['ten', 'dich_vu', 'node_id', 'trang_thai'] : const ['created_at', 'action', 'resource', 'detail']), AdminPager(offset: offset, total: (page['total'] as int?) ?? 0, busy: busy, onPage: (value) { offset = value; load(); })]]);
  }
}
