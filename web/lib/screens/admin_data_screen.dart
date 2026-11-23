// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../widgets/admin_common.dart';
import '../widgets/common.dart';

class AdminDataScreen extends StatefulWidget {
  final ApiClient api;
  const AdminDataScreen({super.key, required this.api});
  @override
  State<AdminDataScreen> createState() => _AdminDataScreenState();
}
class _AdminDataScreenState extends State<AdminDataScreen> {
  final search = TextEditingController(), value = TextEditingController();
  String table = 'users', column = '';
  DateTimeRange? range;
  Json? data;
  bool busy = true;
  String? error;
  int offset = 0;
  String get path => '/admin/data/$table?offset=$offset&limit=20&q=${Uri.encodeQueryComponent(search.text.trim())}${column.isEmpty ? '' : '&column=${Uri.encodeQueryComponent(column)}&value=${Uri.encodeQueryComponent(value.text.trim())}'}${range == null ? '' : '&start=${range!.start.toIso8601String().substring(0, 10)}&end=${range!.end.toIso8601String().substring(0, 10)}'}';
  @override
  void initState() { super.initState(); load(); }
  @override
  void dispose() { search.dispose(); value.dispose(); super.dispose(); }
  Future<void> load() async {
    setState(() { busy = true; error = null; });
    try { final result = await widget.api.get(path); if (mounted) setState(() => data = result); } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [const Text('Tra cứu chỉ đọc. Chọn cột để lọc giá trị chính xác; tìm kiếm chung áp dụng cho các cột công khai.'), const SizedBox(height: 20), Wrap(spacing: 12, runSpacing: 16, children: [SizedBox(width: 250, child: DropdownButtonFormField<String>(initialValue: table, decoration: const InputDecoration(labelText: 'Bảng dữ liệu'), items: [for (final item in [('users', 'Người dùng'), ('instances', 'Dịch vụ'), ('transactions', 'Giao dịch'), ('payments', 'Thanh toán'), ('audit-logs', 'Nhật ký hệ thống'), ('plans', 'Gói'), ('nodes', 'Node')]) DropdownMenuItem(value: item.$1, child: Text(item.$2))], onChanged: busy ? null : (item) { table = item!; column = ''; range = null; offset = 0; data = null; load(); })), SizedBox(width: 350, child: TextField(controller: search, onSubmitted: (_) { offset = 0; load(); }, decoration: const InputDecoration(labelText: 'Tìm kiếm chung', prefixIcon: Icon(Icons.search_outlined)))), SizedBox(width: 250, child: DropdownButtonFormField<String>(key: ValueKey('$table-$column'), initialValue: column, decoration: const InputDecoration(labelText: 'Cột lọc'), items: [const DropdownMenuItem(value: '', child: Text('Không lọc theo cột')), for (final key in (data?['columns'] as List? ?? [])) DropdownMenuItem(value: '$key', child: Text(adminLabel('$key')))], onChanged: busy ? null : (item) => setState(() => column = item!))), SizedBox(width: 250, child: TextField(controller: value, enabled: column.isNotEmpty && !busy, decoration: const InputDecoration(labelText: 'Giá trị chính xác'))), OutlinedButton.icon(onPressed: busy || table == 'plans' ? null : () async { final chosen = await showDateRangePicker(context: context, firstDate: DateTime(2020), lastDate: DateTime.now(), initialDateRange: range, helpText: 'Khoảng ngày UTC'); if (chosen != null) setState(() => range = chosen); }, icon: const Icon(Icons.date_range_outlined), label: Text(range == null ? 'Khoảng ngày' : '${date(range!.start).split(' ').first} – ${date(range!.end).split(' ').first}')), if (range != null) TextButton(onPressed: () => setState(() => range = null), child: const Text('Bỏ khoảng ngày')), FilledButton(onPressed: busy ? null : () { offset = 0; load(); }, child: const Text('Truy xuất')), OutlinedButton.icon(onPressed: busy || data == null ? null : () => exportAdmin(context, widget.api, '$path&csv=true', '$table-trang-${offset ~/ 20 + 1}.csv'), icon: const Icon(Icons.download_outlined), label: const Text('Xuất CSV trang này'))]), const SizedBox(height: 24), if (busy) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), if (data != null) ...[AdminTable(items: rows(data!['items']), columns: (data!['columns'] as List? ?? []).map((key) => '$key').toList()), AdminPager(offset: offset, total: (data!['total'] as int?) ?? 0, busy: busy, onPage: (value) { offset = value; load(); })]]);
}
