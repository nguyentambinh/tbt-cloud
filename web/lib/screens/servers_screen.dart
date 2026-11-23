// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../theme/cloud_theme.dart';
import '../widgets/common.dart';
import '../widgets/instance_actions.dart';

class ServersScreen extends StatefulWidget {
  final CloudState state;
  const ServersScreen({super.key, required this.state});
  @override
  State<ServersScreen> createState() => _ServersScreenState();
}
class _ServersScreenState extends State<ServersScreen> {
  int? selected;
  final pages = PageController(keepPage: false);
  @override
  void dispose() { pages.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: widget.state, builder: (context, _) {
    final items = widget.state.myInstances;
    final current = items.where((v) => v['id'] == selected).firstOrNull ?? items.firstOrNull;
    final mobile = MediaQuery.sizeOf(context).width < 700;
    if (items.isEmpty) return PageBody(children: [const Heading('Máy chủ của bạn', 'Các máy chủ và dịch vụ bạn đang thuê.'), if (widget.state.loading) const Text('Đang tải danh sách máy chủ…') else ...[Text('Bạn chưa có máy chủ nào.', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12), const Text('Chọn loại dịch vụ và gói phù hợp, nạp đủ một giờ sử dụng rồi bấm tạo. Tài khoản và mật khẩu được đặt sẵn.'), const SizedBox(height: 20), FilledButton.icon(onPressed: () => context.go('/tao-vps'), icon: const Icon(Icons.add_circle_outline), label: const Text('Tạo máy chủ đầu tiên'))]]);
    if (mobile) {
      final index = items.indexOf(current!);
      WidgetsBinding.instance.addPostFrameCallback((_) { if (mounted && pages.hasClients && pages.page?.round() != index) pages.jumpToPage(index); });
      return Column(children: [Expanded(child: PageView.builder(controller: pages, itemCount: items.length, onPageChanged: (i) => setState(() => selected = items[i]['id'] as int), itemBuilder: (context, index) => SingleChildScrollView(padding: const EdgeInsets.all(20), child: _summary(items[index], index + 1, actions: false)))), Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Text('${index + 1} / ${items.length} máy chủ · Vuốt để đổi máy', style: const TextStyle(fontSize: 12))), SafeArea(top: false, child: Container(width: double.infinity, padding: const EdgeInsets.all(12), decoration: BoxDecoration(border: Border(top: BorderSide(color: Theme.of(context).dividerColor))), child: InstanceActions(key: ValueKey(current['id']), state: widget.state, instance: current)))]);
    }
    return PageBody(children: [Heading('Máy chủ của bạn', '${items.length} dịch vụ · ${items.where((v) => v['trang_thai'] == 'running').length} đang chạy', trailing: Wrap(spacing: 12, children: [OutlinedButton.icon(onPressed: widget.state.refresh, icon: const Icon(Icons.refresh_outlined), label: const Text('Cập nhật')), FilledButton.icon(onPressed: () => context.go('/tao-vps'), icon: const Icon(Icons.add_outlined), label: const Text('Tạo dịch vụ'))])), Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(flex: 6, child: Column(children: [for (var i = 0; i < items.length; i++) _row(items[i], i + 1, current!['id'] == items[i]['id'])])), const SizedBox(width: 24), Expanded(flex: 4, child: Panel(child: _summary(current!, items.indexOf(current) + 1)))])]);
  });
  Widget _summary(Json v, int index, {bool actions = true}) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [Container(width: 38, height: 38, alignment: Alignment.center, decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: CloudColors.purple, width: 2)), child: Text('$index', style: figures.copyWith(fontSize: 26))), const SizedBox(width: 12), Expanded(child: Text('${v['ten']}', style: Theme.of(context).textTheme.headlineMedium)), StatusMark('${v['trang_thai']}')]), const SizedBox(height: 20), Text('${money(v['gia_theo_gio'])} / giờ', style: figures.copyWith(fontSize: 38)), DescriptionRow('Dịch vụ', serviceName(number(widget.state.planOf(v['plan_id'])?['gpu']) > 0 ? 'ai' : v['dich_vu'])), DescriptionRow('Gói', widget.state.planName(v['plan_id'])), DescriptionRow('Cấu hình', widget.state.specs(v)), if (v['ipv6'] != null) DescriptionRow('IPv6', '${v['ipv6']}', copy: true), DescriptionRow('IP nội bộ', v['ip'] ?? 'Đang chờ cấp IP', copy: v['ip'] != null), DescriptionRow(v['ket_noi'] == 'rdp' ? 'Cổng RDP' : 'Cổng SSH', '${v['ssh_port'] ?? 'Chưa cấp'}'), const SizedBox(height: 12), if (actions) InstanceActions(key: ValueKey(v['id']), state: widget.state, instance: v)]);
  Widget _row(Json v, int index, bool active) => Material(color: active ? CloudColors.purple.withValues(alpha: .06) : Colors.transparent, child: InkWell(onTap: () => setState(() => selected = v['id'] as int), child: Container(constraints: const BoxConstraints(minHeight: 80), padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12), decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Theme.of(context).dividerColor))), child: Row(children: [Container(width: 32, height: 32, alignment: Alignment.center, decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: active ? CloudColors.purple : CloudColors.brown)), child: Text('$index', style: figures.copyWith(fontSize: 23))), const SizedBox(width: 20), Expanded(flex: 5, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${v['ten']}', style: const TextStyle(fontWeight: FontWeight.w600)), Text(widget.state.specs(v), style: const TextStyle(fontSize: 12))])), Expanded(flex: 2, child: Align(alignment: Alignment.centerLeft, child: StatusMark('${v['trang_thai']}'))), Text('${money(v['gia_theo_gio'])} / giờ', style: figures.copyWith(fontSize: 22)), const SizedBox(width: 8), IconButton(tooltip: 'Chi tiết ${v['ten']}', onPressed: () => context.go('/may-chu/${v['id']}'), icon: const Icon(Icons.open_in_new_outlined))]))));
}
