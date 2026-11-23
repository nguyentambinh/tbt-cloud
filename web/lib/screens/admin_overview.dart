// Nguyễn Tâm Bình - 2324801030003
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../theme/cloud_theme.dart';
import '../widgets/admin_common.dart';
import '../widgets/common.dart';

class AdminOverview extends StatefulWidget {
  final ApiClient api;
  const AdminOverview({super.key, required this.api});
  @override
  State<AdminOverview> createState() => _AdminOverviewState();
}
class _AdminOverviewState extends State<AdminOverview> {
  Json? data, revenue;
  DateTimeRange? range;
  String? error;
  bool busy = true;
  int offset = 0;
  String get dates => range == null ? '' : '&start=${range!.start.toIso8601String().substring(0, 10)}&end=${range!.end.toIso8601String().substring(0, 10)}';
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    setState(() { busy = true; error = null; });
    try { final values = await Future.wait([widget.api.get('/admin/stats?$dates'), widget.api.get('/admin/revenue?offset=$offset&limit=50$dates')]); if (mounted) setState(() { data = values[0]; revenue = values[1]; }); } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  Widget export(String section) => TextButton.icon(onPressed: busy ? null : () => exportAdmin(context, widget.api, '/admin/reports/$section/csv?offset=${section == 'daily' ? offset : 0}&limit=50$dates', '$section.csv'), icon: const Icon(Icons.download_outlined, size: 18), label: const Text('Xuất CSV'));
  Widget table(String title, String section, List<Json> items, List<String> columns) => Padding(padding: const EdgeInsets.only(top: 32), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Heading(title, '', trailing: export(section)), AdminTable(items: items, columns: columns)]));
  Widget totals() => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Heading('Dòng tiền và khách hàng', '', trailing: export('totals')), LayoutBuilder(builder: (context, c) {
    final columns = c.maxWidth < 600 ? 1 : c.maxWidth < 1000 ? 2 : 3;
    return Wrap(spacing: 24, runSpacing: 24, children: [for (final field in ['revenue', 'spent', 'wallet_balance', 'users', 'new_7', 'new_30']) SizedBox(width: (c.maxWidth - (columns - 1) * 24) / columns, child: Container(padding: const EdgeInsets.only(bottom: 12), decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Theme.of(context).dividerColor))), child: Row(children: [Expanded(child: Text(adminLabel(field))), const SizedBox(width: 12), Text(['revenue', 'spent', 'wallet_balance'].contains(field) ? money(data![field]) : '${data![field] ?? 0}', style: figures.copyWith(fontSize: 28))])))]);
  })]);
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: [OutlinedButton.icon(onPressed: busy ? null : () async { final result = await showDateRangePicker(context: context, firstDate: DateTime(2020), lastDate: DateTime.now(), initialDateRange: range, helpText: 'Chọn khoảng ngày thống kê (UTC)'); if (result != null) { range = result; offset = 0; load(); } }, icon: const Icon(Icons.date_range_outlined), label: Text(range == null ? 'Lọc theo khoảng ngày' : '${date(range!.start).split(' ').first} – ${date(range!.end).split(' ').first}')), if (range != null) TextButton(onPressed: busy ? null : () { range = null; offset = 0; load(); }, child: const Text('Bỏ lọc')), TextButton.icon(onPressed: busy ? null : load, icon: const Icon(Icons.refresh_outlined), label: const Text('Tải lại'))]), const SizedBox(height: 20), if (busy) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), if (data != null) ...[Text('${data!['scope'] ?? ''}', style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)), const SizedBox(height: 24), totals(), const SizedBox(height: 32), LayoutBuilder(builder: (context, c) { final charts = [for (final spec in [('daily', 'Doanh thu theo ngày'), ('monthly', 'Doanh thu theo tháng')]) Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Heading(spec.$2, range == null ? (spec.$1 == 'daily' ? '30 ngày gần nhất · payOS thành công' : '12 tháng gần nhất · payOS thành công') : 'Theo khoảng ngày đã chọn', trailing: export(spec.$1)), RevenueChart(items: rows(revenue?[spec.$1])), const SizedBox(height: 12)])]; return c.maxWidth < 850 ? Column(children: charts) : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: charts[0]), const SizedBox(width: 32), Expanded(child: charts[1])]); }), AdminPager(offset: offset, total: (revenue?['daily_total'] as int?) ?? 0, limit: 50, busy: busy, onPage: (value) { offset = value; load(); }), for (final group in [('service', 'Dịch vụ đang chạy theo loại'), ('os', 'Dịch vụ đang chạy theo hệ điều hành'), ('node', 'Dịch vụ đang chạy theo node')]) table(group.$2, group.$1, rows((data!['running'] as Map?)?[group.$1]).map((row) => {...row, 'name': group.$1 == 'service' ? serviceName(row['name']) : row['name']}).toList(), ['name', 'count']), table('Khách hàng chi tiêu nhiều nhất', 'top_customers', rows(data!['top_customers']), ['ho_ten', 'username', 'email', 'spent']), const SizedBox(height: 32), Heading('Tài nguyên từng node', 'Số đo gần nhất do worker đồng bộ. Node mất kết nối sẽ giữ số đo cũ.', trailing: export('nodes')), for (final node in rows(data!['nodes'])) ...[Text('${node['ten']} · ${node['online'] == true ? 'Trực tuyến' : 'Mất kết nối'}', style: Theme.of(context).textTheme.titleLarge), ResourceBar('CPU', node['cpu_percent'] == null ? 'Chưa có số đo' : '${node['cpu_percent']}%', node['cpu_percent'] == null ? null : number(node['cpu_percent']) / 100), for (final resource in [('RAM', 'ram_mb', 'MB'), ('Đĩa', 'disk_gb', 'GB')]) ResourceBar(resource.$1, node['measured_${resource.$2}'] == null ? 'Chưa có số đo' : '${node['measured_${resource.$2}']} / ${node['total_${resource.$2}']} ${resource.$3}', node['measured_${resource.$2}'] != null && number(node['total_${resource.$2}']) > 0 ? number(node['measured_${resource.$2}']) / number(node['total_${resource.$2}']) : null), Text('Đã cấp phát ${node['used_vcpu']} / ${node['total_vcpu']} vCPU · Đồng bộ ${date(node['last_seen_at'])}'), const SizedBox(height: 20)]]]);
}

class RevenueChart extends StatelessWidget {
  final List<Json> items;
  const RevenueChart({super.key, required this.items});
  @override
  Widget build(BuildContext context) => Semantics(label: 'Biểu đồ doanh thu: ${items.map((row) => '${row['period']}: ${money(row['amount'])}').join(', ')}', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Cao nhất ${money(items.fold<double>(0, (value, row) => math.max(value, number(row['amount']))))}'), SizedBox(height: 160, width: double.infinity, child: CustomPaint(painter: _RevenuePainter(items, Theme.of(context).dividerColor))), Row(children: [Text(items.isEmpty ? 'Chưa có dữ liệu' : '${items.first['period']}'), const Spacer(), if (items.length > 1) Text('${items.last['period']}')]), if (items.isNotEmpty && items.every((row) => number(row['amount']) == 0)) const Padding(padding: EdgeInsets.only(top: 8), child: Text('Chưa có thanh toán payOS thành công trong kỳ.'))]));
}
class _RevenuePainter extends CustomPainter {
  final List<Json> items;
  final Color line;
  _RevenuePainter(this.items, this.line);
  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()..color = line..strokeWidth = 1;
    for (var i = 0; i <= 4; i++) { final y = 12 + (size.height - 24) * i / 4; canvas.drawLine(Offset(0, y), Offset(size.width, y), grid); }
    if (items.isEmpty) return;
    final max = items.fold<double>(1, (value, row) => math.max(value, number(row['amount'])));
    final step = size.width / items.length;
    for (var i = 0; i < items.length; i++) { final height = number(items[i]['amount']) / max * (size.height - 24); canvas.drawRect(Rect.fromLTWH(i * step + step * .15, size.height - 12 - height, step * .7, height), Paint()..color = CloudColors.olive); }
  }
  @override
  bool shouldRepaint(_RevenuePainter oldDelegate) => oldDelegate.items != items || oldDelegate.line != line;
}
