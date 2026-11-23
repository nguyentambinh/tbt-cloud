// Nguyễn Tâm Bình - 2324801030003
import 'dart:convert';
import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../api/browser.dart';
import '../api/cloud_state.dart';
import '../theme/cloud_theme.dart';
import 'common.dart';

const advisorAccept = '.docx,.xlsx,.pdf,.png,.jpg,.jpeg,.webp,.txt';

class AiAdvisor extends StatefulWidget {
  final ApiClient api;
  final bool busy;
  final ValueChanged<Json> onCreate, onChoose;
  final Future<(String, List<int>)?> Function()? picker;
  const AiAdvisor({super.key, required this.api, required this.onCreate, required this.onChoose, this.busy = false, this.picker});
  @override
  State<AiAdvisor> createState() => _AiAdvisorState();
}
class _AiAdvisorState extends State<AiAdvisor> {
  final need = TextEditingController();
  (String, List<int>)? file;
  Json? result;
  String? error;
  bool asking = false, more = false;
  @override
  void dispose() { need.dispose(); super.dispose(); }
  Future<void> attach() async {
    final picked = await (widget.picker ?? () => pickFile(advisorAccept))();
    if (picked == null || !mounted) return;
    if (picked.$2.length > 8 * 1024 * 1024) { setState(() => error = 'Tệp lớn hơn 8 MB. Hãy chọn tệp nhỏ hơn.'); return; }
    setState(() { file = picked; error = null; });
  }
  Future<void> ask() async {
    if (need.text.trim().isEmpty && file == null) { setState(() => error = 'Hãy kể nhu cầu của bạn hoặc đính kèm một tệp.'); return; }
    setState(() { asking = true; error = null; result = null; more = false; });
    try {
      final data = await widget.api.post('/ai/goi-y', {'mo_ta': need.text.trim(), if (file != null) ...{'tep_ten': file!.$1, 'tep_base64': base64Encode(file!.$2)}});
      if (mounted) setState(() => result = data);
    } catch (e) { if (mounted) setState(() => error = e is ApiException ? e.message : 'AI chưa gợi ý được. Hãy thử lại sau ít phút.'); }
    if (mounted) setState(() => asking = false);
  }
  String specs(Json s) => '${number(s['gpu']) > 0 ? '${number(s['gpu']).toInt()} GPU · ' : ''}${s['vcpu']} vCPU · ${s['ram_mb']} MB RAM · ${s['disk_gb']} GB${s['ten_he_dieu_hanh'] == null ? '' : ' · ${s['ten_he_dieu_hanh']}'}';
  Widget option(Json s, {bool best = false}) {
    final accent = Theme.of(context).brightness == Brightness.dark ? const Color(0xFFD5AFF1) : CloudColors.purple;
    final webapp = s['dich_vu'] == 'webapp';
    return Container(width: double.infinity, margin: const EdgeInsets.only(top: 12), padding: const EdgeInsets.all(20), decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), border: Border.all(color: best ? accent : Theme.of(context).dividerColor, width: best ? 2 : 1), color: best ? accent.withValues(alpha: .06) : null), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (best) Text('PHÙ HỢP NHẤT', style: figures.copyWith(fontSize: 16, color: accent)),
      Wrap(spacing: 12, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.end, children: [Text('${s['ten_dich_vu']} · ${s['ten_goi']}', style: Theme.of(context).textTheme.titleLarge), Text('${money(s['gia_theo_gio'])} / giờ', style: figures.copyWith(fontSize: 24))]),
      const SizedBox(height: 4), Text(specs(s), style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
      const SizedBox(height: 10), Text('${s['ly_do']}'),
      const SizedBox(height: 14), Wrap(spacing: 10, runSpacing: 8, children: [FilledButton.icon(key: ValueKey('ai-create-${s['plan_id']}-${s['os_ma']}'), onPressed: widget.busy ? null : () => (webapp ? widget.onChoose : widget.onCreate)(s), icon: Icon(webapp ? Icons.edit_outlined : Icons.add_circle_outline), label: Text(webapp ? 'Chọn và nhập kho Git' : 'Tạo máy này')), if (!webapp) OutlinedButton(onPressed: widget.busy ? null : () => widget.onChoose(s), child: const Text('Chọn rồi tự chỉnh'))]),
    ]));
  }
  @override
  Widget build(BuildContext context) {
    final items = [for (final s in (result?['goi_y'] as List? ?? const [])) Map<String, dynamic>.from(s as Map)];
    return Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [const Icon(Icons.auto_awesome_outlined), const SizedBox(width: 10), Expanded(child: Text('Chưa biết chọn gì? Để AI chọn giúp', style: Theme.of(context).textTheme.headlineMedium))]),
      const SizedBox(height: 8), const Text('Kể vấn đề bạn đang gặp hoặc đính kèm tài liệu (Word, Excel, PDF, ảnh). AI đọc rồi đưa bạn tới cấu hình phù hợp nhất.'),
      const SizedBox(height: 16),
      TextField(key: const ValueKey('ai-need'), controller: need, enabled: !asking, minLines: 3, maxLines: 6, maxLength: 4000, decoration: const InputDecoration(labelText: 'Bạn cần giải quyết việc gì?', hintText: 'Ví dụ: cửa hàng có 3 chi nhánh, đơn hàng ghi sổ tay hay thất lạc, muốn có trang đặt hàng và nơi lưu dữ liệu chung…')),
      Wrap(spacing: 12, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [OutlinedButton.icon(key: const ValueKey('ai-attach'), onPressed: asking ? null : attach, icon: const Icon(Icons.attach_file_outlined), label: const Text('Đính kèm tệp')), if (file != null) InputChip(label: Text(file!.$1, overflow: TextOverflow.ellipsis), onDeleted: asking ? null : () => setState(() => file = null)), FilledButton.icon(key: const ValueKey('ai-ask'), onPressed: asking ? null : ask, icon: const Icon(Icons.auto_awesome_outlined), label: Text(asking ? 'AI đang đọc…' : 'Gợi ý cho tôi'))]),
      if (asking) const Padding(padding: EdgeInsets.only(top: 16), child: LinearProgressIndicator()),
      if (error != null) Padding(padding: const EdgeInsets.only(top: 16), child: Notice(error!)),
      if (items.isNotEmpty) ...[
        const SizedBox(height: 20),
        if ('${result!['tom_tat']}'.isNotEmpty) Text('AI hiểu nhu cầu của bạn: ${result!['tom_tat']}', style: const TextStyle(fontStyle: FontStyle.italic)),
        option(items.first, best: true),
        if (items.length > 1) Padding(padding: const EdgeInsets.only(top: 12), child: TextButton.icon(key: const ValueKey('ai-more'), onPressed: () => setState(() => more = !more), icon: Icon(more ? Icons.expand_less : Icons.expand_more), label: Text(more ? 'Ẩn bớt' : 'Xem thêm ${items.length - 1} gợi ý liên quan'))),
        if (more) for (final s in items.skip(1)) option(s),
      ],
    ]));
  }
}
