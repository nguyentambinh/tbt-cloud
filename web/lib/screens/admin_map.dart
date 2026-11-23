// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../api/api_client.dart';
import '../map/network_map.dart';
import '../widgets/admin_common.dart';
import '../widgets/common.dart';

class AdminMap extends StatefulWidget {
  final ApiClient api;
  const AdminMap({super.key, required this.api});
  @override
  State<AdminMap> createState() => _AdminMapState();
}
class _AdminMapState extends State<AdminMap> {
  Json? data, owner;
  int offset = 0, selection = 0, ownerPage = 0;
  bool busy = true, ownerBusy = false;
  String? error, ownerError;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    setState(() { busy = true; error = null; owner = null; selection = 0; ownerBusy = false; });
    try { final result = await widget.api.get('/admin/map?offset=$offset&limit=20'); if (mounted) setState(() => data = result); } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  Future<void> select(int id) async {
    final instance = rows(data?['items']).firstWhere((row) => row['id'] == id);
    setState(() { selection = id; owner = null; ownerError = null; ownerBusy = true; ownerPage = 0; });
    try { final result = await widget.api.get('/admin/users/${instance['user_id']}'); if (mounted && selection == id) setState(() => owner = result); } catch (e) { if (mounted && selection == id) setState(() => ownerError = e.toString()); }
    if (mounted && selection == id) setState(() => ownerBusy = false);
  }
  static const perPage = 6;
  // Dịch vụ của chủ sở hữu: mỗi trang 6 mục, nút trang hoặc lăn chuột trong khung để chuyển trang
  Widget ownerServices(List<Json> items) {
    if (items.isEmpty) return const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Text('Khách hàng chưa có dịch vụ.'));
    final pages = (items.length + perPage - 1) ~/ perPage;
    final page = ownerPage.clamp(0, pages - 1);
    final shown = items.skip(page * perPage).take(perPage).toList();
    void go(int value) { if (value >= 0 && value < pages && value != page) setState(() => ownerPage = value); }
    final list = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [for (final row in shown) Container(width: double.infinity, constraints: const BoxConstraints(minHeight: 60), padding: const EdgeInsets.symmetric(vertical: 10), decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Theme.of(context).dividerColor))), child: Row(children: [Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${row['ten']}', style: const TextStyle(fontWeight: FontWeight.w600)), Text(adminValue('dich_vu', row['dich_vu']), style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.onSurfaceVariant))])), StatusMark('${row['trang_thai']}')]))]);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Listener(onPointerSignal: (event) { if (event is PointerScrollEvent && pages > 1) { final next = page + (event.scrollDelta.dy > 0 ? 1 : -1); if (next >= 0 && next < pages) GestureBinding.instance.pointerSignalResolver.register(event, (_) => go(next)); } }, child: list), Padding(padding: const EdgeInsets.only(top: 12), child: Wrap(spacing: 12, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [Text('${page * perPage + 1} - ${(page * perPage + shown.length)} / ${items.length}'), OutlinedButton(key: const ValueKey('owner-prev'), onPressed: page == 0 ? null : () => go(page - 1), child: const Text('Trang trước')), OutlinedButton(key: const ValueKey('owner-next'), onPressed: page >= pages - 1 ? null : () => go(page + 1), child: const Text('Trang sau'))])), if (items.length >= 20) Padding(padding: const EdgeInsets.only(top: 8), child: Text('Hiện 20 dịch vụ gần nhất; xem đầy đủ tại trang chi tiết người dùng.', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.onSurfaceVariant)))]);
  }
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [if (busy) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), if (data != null) ...[const Text('Chọn vòng tròn dịch vụ trên bản đồ hoặc chọn trong danh sách để xem khách hàng.'), const SizedBox(height: 20), LayoutBuilder(builder: (context, c) {
    final map = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [NetworkMap(nodes: rows(data!['nodes']), instances: rows(data!['items']), selected: selection, onSelect: select, height: c.maxWidth < 700 ? 320 : 440), const SizedBox(height: 16), for (final node in rows(data!['nodes'])) ...[Text('${node['ten']}', style: Theme.of(context).textTheme.titleLarge), for (final row in rows(data!['items']).where((row) => row['node_id'] == node['id'])) ListTile(selectedColor: Theme.of(context).brightness == Brightness.dark ? const Color(0xFFD5AFF1) : const Color(0xFF7B2CBF), contentPadding: EdgeInsets.zero, selected: selection == row['id'], title: Text('${row['ten']}'), subtitle: Text('${adminValue('dich_vu', row['dich_vu'])} · ${stateName(row['trang_thai'])}'), trailing: const Icon(Icons.chevron_right), onTap: () => select(row['id'] as int)), const Divider()], AdminPager(offset: offset, total: (data!['total'] as int?) ?? 0, busy: busy, onPage: (value) { offset = value; load(); })]);
    final panel = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Chủ sở hữu dịch vụ', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 16), if (ownerBusy) const LinearProgressIndicator(), if (ownerError != null) Notice(ownerError!), if (owner == null && !ownerBusy && ownerError == null) const Text('Chưa chọn dịch vụ.'), if (owner != null) ...[for (final field in [('Họ và tên', 'ho_ten'), ('Tên tài khoản', 'username'), ('Email', 'email'), ('Ngày tạo', 'created_at')]) DescriptionRow(field.$1, adminValue(field.$2, owner![field.$2])), DescriptionRow('Số dư', money(owner!['balance'])), const SizedBox(height: 20), FilledButton(onPressed: () => context.go('/quan-tri/nguoi-dung/${owner!['id']}'), child: const Text('Chi tiết người dùng')), const SizedBox(height: 24), Text('Dịch vụ của khách hàng', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 8), ownerServices(rows((owner!['instances'] as Map?)?['items']))]]);
    return c.maxWidth < 1000 ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [map, const SizedBox(height: 24), panel]) : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(flex: 6, child: map), const SizedBox(width: 32), Expanded(flex: 4, child: panel)]);
  })]]);
}
