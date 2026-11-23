// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../api/cloud_state.dart';
import '../api/api_client.dart';
import '../theme/cloud_theme.dart';

String money(dynamic value) {
  final parts = number(value).round().abs().toString().replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (m) => '${m[1]}.');
  return '${number(value) < 0 ? '−' : ''}$parts\u0111';
}
String date(dynamic value) {
  final d = DateTime.tryParse('$value')?.toLocal();
  if (d == null) return 'Chưa có';
  String p(int n) => '$n'.padLeft(2, '0');
  return '${p(d.day)}/${p(d.month)}/${d.year} ${p(d.hour)}:${p(d.minute)}';
}
String stateName(dynamic value) => const {'running': 'Đang chạy', 'stopped': 'Đã tắt', 'suspended': 'Tạm dừng vì hết tiền', 'provisioning': 'Đang cấp phát', 'error': 'Cần kiểm tra', 'deleted': 'Đã hủy', 'pending': 'Chờ thanh toán', 'paid': 'Đã thanh toán', 'cancelled': 'Đã hủy', 'expired': 'Đã hết hạn', 'failed': 'Chưa hoàn tất'}[value] ?? 'Chưa xác định';
void message(BuildContext context, String text) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

class PageBody extends StatelessWidget {
  final List<Widget> children;
  const PageBody({super.key, required this.children});
  @override
  Widget build(BuildContext context) => SingleChildScrollView(child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1440), child: Padding(padding: EdgeInsets.all(MediaQuery.sizeOf(context).width < 700 ? 20 : 40), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: children)))));
}
class Heading extends StatelessWidget {
  final String title, subtitle;
  final Widget? trailing;
  const Heading(this.title, this.subtitle, {super.key, this.trailing});
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.only(bottom: 28), child: LayoutBuilder(builder: (context, c) {
    final text = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: Theme.of(context).textTheme.headlineLarge), const SizedBox(height: 8), Text(subtitle, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant))]);
    return c.maxWidth < 600 ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [text, if (trailing != null) Padding(padding: const EdgeInsets.only(top: 16), child: trailing!)]) : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: text), ?trailing]);
  }));
}
class Panel extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  const Panel({super.key, required this.child, this.padding = const EdgeInsets.all(24)});
  @override
  Widget build(BuildContext context) => Container(width: double.infinity, padding: padding, decoration: BoxDecoration(border: Border.all(color: Theme.of(context).dividerColor), borderRadius: BorderRadius.circular(8)), child: child);
}
class Notice extends StatelessWidget {
  final String text;
  final VoidCallback? retry;
  const Notice(this.text, {super.key, this.retry});
  @override
  Widget build(BuildContext context) => Container(width: double.infinity, margin: const EdgeInsets.only(bottom: 20), padding: const EdgeInsets.all(16), color: CloudColors.yellow.withValues(alpha: Theme.of(context).brightness == Brightness.dark ? .2 : .35), child: Row(children: [const Icon(Icons.info_outline), const SizedBox(width: 12), Expanded(child: Text(text)), if (retry != null) TextButton(onPressed: retry, child: const Text('Thử lại'))]));
}
class StatusMark extends StatelessWidget {
  final String status;
  const StatusMark(this.status, {super.key});
  @override
  Widget build(BuildContext context) => Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5), decoration: BoxDecoration(color: (status == 'running' ? CloudColors.olive : status == 'stopped' ? Theme.of(context).colorScheme.surfaceContainerHighest : CloudColors.yellow).withValues(alpha: .35), borderRadius: BorderRadius.circular(4)), child: Text(stateName(status), style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.onSurface)));
}
class DescriptionRow extends StatelessWidget {
  final String label, value;
  final bool copy;
  const DescriptionRow(this.label, this.value, {super.key, this.copy = false});
  @override
  Widget build(BuildContext context) => Container(constraints: const BoxConstraints(minHeight: 52), decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Theme.of(context).dividerColor))), child: LayoutBuilder(builder: (context, c) => Row(children: [SizedBox(width: c.maxWidth < 350 ? 100 : 145, child: Text(label.toUpperCase(), style: figures.copyWith(fontSize: 17, color: Theme.of(context).colorScheme.onSurfaceVariant))), Expanded(child: SelectableText(value, style: const TextStyle(fontSize: 14))), if (copy) IconButton(tooltip: 'Sao chép $label', onPressed: () async { await Clipboard.setData(ClipboardData(text: value)); if (context.mounted) message(context, 'Đã sao chép.'); }, icon: const Icon(Icons.content_copy_outlined, size: 18))])));
}
class ResourceBar extends StatelessWidget {
  final String label, value;
  final double? ratio;
  const ResourceBar(this.label, this.value, this.ratio, {super.key});
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.symmetric(vertical: 10), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [Text(label, style: figures.copyWith(fontSize: 18)), const Spacer(), Flexible(child: Text(value, style: figures.copyWith(fontSize: 20), textAlign: TextAlign.end))]), const SizedBox(height: 10), Semantics(label: '$label: $value', child: LinearProgressIndicator(value: (ratio ?? 0).clamp(0, 1), minHeight: 6, color: ratio != null && ratio! > .85 ? CloudColors.yellow : CloudColors.olive, backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest)), const SizedBox(height: 4), Text(ratio == null ? 'Chưa có số đo sử dụng' : '${(ratio! * 100).toStringAsFixed(1)}% đã dùng', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.onSurfaceVariant))]));
}
Future<bool> confirm(BuildContext context, String title, String content, {String? typedName}) async => await showDialog<bool>(context: context, builder: (_) => ConfirmDialog(title: title, content: content, typedName: typedName)) ?? false;
class ConfirmDialog extends StatefulWidget {
  final String title, content;
  final String? typedName;
  const ConfirmDialog({super.key, required this.title, required this.content, this.typedName});
  @override
  State<ConfirmDialog> createState() => _ConfirmDialogState();
}
class _ConfirmDialogState extends State<ConfirmDialog> {
  final controller = TextEditingController();
  @override
  void dispose() { controller.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => AlertDialog(title: Text(widget.title), content: SizedBox(width: 420, child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [Text(widget.content), if (widget.typedName != null) ...[const SizedBox(height: 20), TextField(controller: controller, onChanged: (_) => setState(() {}), decoration: InputDecoration(labelText: 'Gõ lại tên máy: ${widget.typedName}'))]])), actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Quay lại')), FilledButton(onPressed: widget.typedName == null || controller.text == widget.typedName ? () => Navigator.pop(context, true) : null, child: Text(widget.title))]);
}

class PlanChoices extends StatelessWidget {
  final List<Json> plans;
  final int? selected;
  final ValueChanged<int> onSelect;
  final String? Function(Json)? disabledReason;
  final bool tiers;
  final String gpuName;
  const PlanChoices({super.key, required this.plans, required this.onSelect, this.selected, this.disabledReason, this.tiers = false, this.gpuName = ''});
  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
    final columns = c.maxWidth < 600 ? 1 : c.maxWidth < 1000 ? 2 : 3;
    final width = (c.maxWidth - (columns - 1) * 20) / columns;
    return Wrap(spacing: 20, runSpacing: 20, children: [for (final plan in plans) SizedBox(width: width, child: Semantics(selected: selected == plan['id'], enabled: disabledReason?.call(plan) == null, child: Opacity(opacity: disabledReason?.call(plan) == null ? 1 : .55, child: Material(color: selected == plan['id'] ? CloudColors.purple.withValues(alpha: .07) : Colors.transparent, child: InkWell(onTap: disabledReason?.call(plan) == null ? () => onSelect(plan['id'] as int) : null, borderRadius: BorderRadius.circular(8), child: Container(padding: const EdgeInsets.all(24), decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), border: Border.all(color: selected == plan['id'] ? CloudColors.purple : Theme.of(context).dividerColor, width: selected == plan['id'] ? 2 : 1)), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [Expanded(child: Text('${plan['ten']}', style: Theme.of(context).textTheme.headlineMedium)), Icon(selected == plan['id'] ? Icons.radio_button_checked_outlined : Icons.radio_button_unchecked_outlined, color: selected == plan['id'] ? CloudColors.purple : Theme.of(context).colorScheme.onSurfaceVariant)]), const SizedBox(height: 22), Text('${money(plan['gia_theo_gio'])} / giờ', style: figures.copyWith(fontSize: 34)), if (tiers) Text('Mức ${['Cơ bản', 'Tiêu chuẩn', 'Nâng cao', 'Chuyên dụng'][(plans.indexOf(plan) * 4 ~/ plans.length).clamp(0, 3)]}', style: figures.copyWith(fontSize: 18, color: Theme.of(context).colorScheme.onSurfaceVariant)), Text('Khoảng ${money(number(plan['gia_theo_gio']) * 720)} / tháng', style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)), const SizedBox(height: 16), Text('${plan['mo_ta'] ?? ''}', style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)), const SizedBox(height: 22), const Divider(), if (hasGpu(plan)) DescriptionRow('GPU', '${number(plan['gpu']).toInt()} × ${gpuName.isEmpty ? 'GPU NVIDIA' : gpuName}'), DescriptionRow('vCPU', '${plan['vcpu']} lõi'), DescriptionRow('RAM', '${plan['ram_mb']} MB'), DescriptionRow('Ổ đĩa', '${plan['disk_gb']} GB'), if (disabledReason?.call(plan) != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(disabledReason!(plan)!))])))))))]);
  });
}
