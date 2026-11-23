// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import 'common.dart';

class InstanceActions extends StatefulWidget {
  final CloudState state;
  final Json instance;
  final VoidCallback? onChanged;
  final bool details;
  const InstanceActions({super.key, required this.state, required this.instance, this.onChanged, this.details = true});
  @override
  State<InstanceActions> createState() => _InstanceActionsState();
}
class _InstanceActionsState extends State<InstanceActions> {
  bool busy = false;
  Future<void> act(String action) async {
    if (action == 'reboot' && !await confirm(context, 'Khởi động lại', 'Các kết nối tới máy chủ sẽ ngắt trong lúc khởi động lại.')) return;
    if (!mounted) return;
    if (action == 'stop' && !await confirm(context, 'Tắt máy chủ', 'Dịch vụ trên VPS sẽ dừng. Phần giờ đã trả chưa dùng sẽ không được hoàn lại.')) return;
    if (!mounted) return;
    setState(() => busy = true);
    try {
      await widget.state.api.post('/instances/${widget.instance['id']}/$action');
      await widget.state.refresh();
      if (!mounted) return;
      widget.onChanged?.call();
      if (mounted) message(context, 'Đã cập nhật trạng thái máy chủ.');
    } catch (e) { if (mounted) message(context, e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  @override
  Widget build(BuildContext context) {
    final running = widget.instance['trang_thai'] == 'running';
    final available = ['running', 'stopped', 'suspended'].contains(widget.instance['trang_thai']);
    return Wrap(spacing: 8, runSpacing: 8, children: [OutlinedButton.icon(onPressed: busy || !available ? null : () => act(running ? 'stop' : 'start'), icon: Icon(running ? Icons.stop_circle_outlined : Icons.play_circle_outline, size: 19), label: Text(busy ? 'Đang xử lý…' : running ? 'Tắt' : 'Bật')), OutlinedButton.icon(onPressed: busy || !running ? null : () => act('reboot'), icon: const Icon(Icons.restart_alt_outlined, size: 19), label: const Text('Khởi động lại')), FilledButton.icon(onPressed: !running || busy || widget.instance['loai'] != 'vm' || widget.instance['ket_noi'] == 'rdp' ? null : () => context.go('/may-chu/${widget.instance['id']}/console'), icon: const Icon(Icons.terminal_outlined, size: 19), label: const Text('Console')), if (widget.details) TextButton(onPressed: () => context.go('/may-chu/${widget.instance['id']}'), child: const Text('Xem chi tiết'))]);
  }
}
