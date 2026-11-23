// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../widgets/admin_common.dart';
import '../widgets/common.dart';

class AdminSettings extends StatefulWidget {
  final ApiClient api;
  const AdminSettings({super.key, required this.api});
  @override
  State<AdminSettings> createState() => _AdminSettingsState();
}
class _AdminSettingsState extends State<AdminSettings> {
  String table = 'plans';
  int offset = 0;
  Json? data;
  String? error;
  bool busy = true;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    setState(() { busy = true; error = null; });
    try { final result = await widget.api.get('/admin/data/$table?offset=$offset&limit=20'); if (mounted) setState(() => data = result); } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  Future<void> save(String path, String method, Object? body) async {
    setState(() { busy = true; error = null; });
    try { await widget.api.request(path, method: method, body: body); if (mounted) { message(context, 'Đã lưu dữ liệu.'); await load(); } } catch (e) { if (mounted) setState(() { error = e.toString(); busy = false; }); }
  }
  Future<void> plan([Json? row]) async {
    final input = await adminForm(context, row == null ? 'Thêm gói dịch vụ' : 'Sửa gói dịch vụ', [('ten', 'Tên gói', '${row?['ten'] ?? ''}'), ('dich_vu', 'Loại: vps, postgres hoặc webapp', '${row?['dich_vu'] ?? 'vps'}'), ('mo_ta', 'Mô tả', '${row?['mo_ta'] ?? ''}'), ('vcpu', 'Số vCPU', '${row?['vcpu'] ?? 1}'), ('ram_mb', 'RAM (MB)', '${row?['ram_mb'] ?? 1024}'), ('disk_gb', 'Ổ đĩa (GB)', '${row?['disk_gb'] ?? 10}'), ('gia_theo_gio', 'Giá theo giờ (đ)', '${row?['gia_theo_gio'] ?? 500}')], numeric: ['vcpu', 'ram_mb', 'disk_gb', 'gia_theo_gio'], optional: ['mo_ta']);
    if (input == null || !mounted) return;
    for (final key in ['vcpu', 'ram_mb', 'disk_gb']) { final value = int.tryParse('${input[key]}'); if (value == null || value <= 0) { message(context, 'CPU, RAM và đĩa cần là số nguyên dương.'); return; } input[key] = value; }
    input['active'] = row?['active'] ?? true;
    await save('/admin/plans${row == null ? '' : '/${row['id']}'}', row == null ? 'POST' : 'PUT', input);
  }
  Future<void> node(Json row) async {
    final input = await adminForm(context, 'Thông tin node', [for (final field in [('ten', 'Tên hiển thị'), ('proxmox_node', 'Tên node Proxmox'), ('storage', 'Kho lưu trữ'), ('bridge', 'Cầu mạng')]) (field.$1, field.$2, '${row[field.$1] ?? ''}')]);
    if (input != null) await save('/admin/nodes/${row['id']}', 'PUT', input);
  }
  Future<void> templates(Json row) async {
    setState(() { busy = true; error = null; });
    try {
      final values = await Future.wait([widget.api.list('/os', authenticated: false), widget.api.list('/admin/nodes/${row['id']}/os-templates')]);
      if (!mounted) return;
      final fields = <(String, String, String)>[for (final image in values[0]) ('${image['ma']}', '${image['ten']} · mã template', values[1].where((item) => item['os_ma'] == image['ma']).map((item) => '${item['template_id']}').firstOrNull ?? '')];
      final result = await adminForm(context, 'Ánh xạ hệ điều hành · ${row['ten']}', fields, numeric: fields.map((field) => field.$1).toList(), optional: fields.map((field) => field.$1).toList());
      if (result != null) {
        final mappings = <Json>[];
        for (final entry in result.entries.where((entry) => '${entry.value}'.isNotEmpty)) { final id = int.tryParse('${entry.value}'); if (id == null || id < 100 || id > 999999999) { if (mounted) message(context, 'Mã template là số nguyên từ 100 đến 999999999.'); return; } mappings.add({'os_ma': entry.key, 'template_id': id}); }
        await save('/admin/nodes/${row['id']}/os-templates', 'PUT', mappings);
      }
    } catch (e) { if (mounted) setState(() => error = e.toString()); } finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Wrap(spacing: 12, runSpacing: 12, children: [for (final item in [('plans', 'Gói dịch vụ'), ('nodes', 'Node và hệ điều hành')]) ChoiceChip(label: Text(item.$2), selected: table == item.$1, onSelected: busy ? null : (_) { table = item.$1; offset = 0; load(); }), if (table == 'plans') FilledButton.icon(onPressed: busy ? null : () => plan(), icon: const Icon(Icons.add_outlined), label: const Text('Thêm gói'))]), const SizedBox(height: 24), if (busy) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), if (data != null) ...[for (final row in rows(data!['items'])) ...[Padding(padding: const EdgeInsets.symmetric(vertical: 16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${row['ten']}', style: Theme.of(context).textTheme.headlineSmall), const SizedBox(height: 8), Text(table == 'plans' ? '${row['dich_vu']} · ${row['vcpu']} vCPU · ${row['ram_mb']} MB RAM · ${row['disk_gb']} GB · ${money(row['gia_theo_gio'])}/giờ · ${row['active'] == true ? 'Đang công bố' : 'Đã ẩn'}' : '${row['mesh_ip']} · ${row['proxmox_node']} · ${row['trang_thai']}'), const SizedBox(height: 8), if (table == 'plans') Text('${row['mo_ta'] ?? ''}'), Wrap(spacing: 12, runSpacing: 8, children: [TextButton(onPressed: busy ? null : () => table == 'plans' ? plan(row) : node(row), child: const Text('Sửa thông tin')), if (table == 'plans') ...[TextButton(onPressed: busy ? null : () => save('/admin/plans/${row['id']}', 'PUT', {for (final key in ['ten', 'dich_vu', 'mo_ta', 'vcpu', 'ram_mb', 'disk_gb', 'gia_theo_gio']) key: row[key], 'active': row['active'] != true}), child: Text(row['active'] == true ? 'Ẩn gói' : 'Công bố gói')), TextButton(onPressed: busy ? null : () async { if (await confirm(context, 'Xóa gói', 'Chỉ xóa gói chưa từng được sử dụng.')) save('/admin/plans/${row['id']}', 'DELETE', null); }, child: const Text('Xóa gói'))] else TextButton(onPressed: busy ? null : () => templates(row), child: const Text('Ánh xạ hệ điều hành'))])])), const Divider(height: 1)], AdminPager(offset: offset, total: (data!['total'] as int?) ?? 0, busy: busy, onPage: (value) { offset = value; load(); })]]);
}
