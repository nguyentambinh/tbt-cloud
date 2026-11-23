// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../api/cloud_state.dart';
import '../theme/cloud_theme.dart';
import 'common.dart';

class ThemeButton extends StatelessWidget {
  final CloudState state;
  const ThemeButton({super.key, required this.state});
  @override
  Widget build(BuildContext context) {
    const options = [(ThemeMode.system, 'Theo hệ thống', Icons.brightness_auto_outlined), (ThemeMode.light, 'Sáng', Icons.light_mode_outlined), (ThemeMode.dark, 'Tối', Icons.dark_mode_outlined)];
    final current = options.firstWhere((o) => o.$1 == state.themeMode);
    return PopupMenuButton<ThemeMode>(key: const ValueKey('theme-button'), tooltip: 'Giao diện: ${current.$2}', icon: Icon(current.$3), onSelected: state.setTheme, itemBuilder: (_) => [for (final o in options) CheckedPopupMenuItem(value: o.$1, checked: o.$1 == state.themeMode, child: Row(children: [Icon(o.$3, size: 20), const SizedBox(width: 12), Text(o.$2)]))]);
  }
}

class NotificationBell extends StatelessWidget {
  final CloudState state;
  const NotificationBell({super.key, required this.state});
  Future<void> open(BuildContext context) async {
    final link = await showDialog<String>(context: context, builder: (_) => NotificationDialog(state: state));
    if (link != null && context.mounted) context.go(link);
  }
  @override
  Widget build(BuildContext context) => IconButton(key: const ValueKey('notification-bell'), tooltip: state.unread > 0 ? '${state.unread} thông báo chưa đọc' : 'Thông báo', onPressed: () => open(context), icon: Badge(isLabelVisible: state.unread > 0, label: Text(state.unread > 9 ? '9+' : '${state.unread}'), backgroundColor: CloudColors.purple, textColor: Colors.white, child: const Icon(Icons.notifications_none_outlined)));
}

class NotificationDialog extends StatefulWidget {
  final CloudState state;
  const NotificationDialog({super.key, required this.state});
  @override
  State<NotificationDialog> createState() => _NotificationDialogState();
}
class _NotificationDialogState extends State<NotificationDialog> {
  late final Set<int> fresh = {for (final item in widget.state.notifications) if (item['da_doc'] != true) item['id'] as int};
  bool loading = true;
  @override
  void initState() { super.initState(); refresh(); }
  Future<void> refresh() async {
    await widget.state.loadNotifications();
    if (!mounted) return;
    setState(() { fresh.addAll({for (final item in widget.state.notifications) if (item['da_doc'] != true) item['id'] as int}); loading = false; });
    await widget.state.markNotificationsRead();
  }
  @override
  Widget build(BuildContext context) {
    final items = widget.state.notifications;
    final accent = Theme.of(context).brightness == Brightness.dark ? const Color(0xFFD5AFF1) : CloudColors.purple;
    return Dialog(insetPadding: const EdgeInsets.all(16), child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 520, maxHeight: 640), child: Column(mainAxisSize: MainAxisSize.min, children: [Padding(padding: const EdgeInsets.fromLTRB(24, 12, 8, 4), child: Row(children: [Expanded(child: Text('Thông báo', style: Theme.of(context).textTheme.headlineMedium)), IconButton(tooltip: 'Đóng', onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close))])), if (loading) const LinearProgressIndicator(minHeight: 2), const Divider(height: 1), Flexible(child: items.isEmpty && !loading ? const Padding(padding: EdgeInsets.all(32), child: Text('Chưa có thông báo nào.')) : ListView.separated(shrinkWrap: true, itemCount: items.length, separatorBuilder: (_, _) => const Divider(height: 1), itemBuilder: (context, i) {
      final item = items[i];
      final isNew = fresh.contains(item['id']);
      return ListTile(key: ValueKey('notification-${item['id']}'), minVerticalPadding: 12, contentPadding: const EdgeInsets.symmetric(horizontal: 24), tileColor: isNew ? accent.withValues(alpha: .08) : null, leading: Icon(isNew ? Icons.circle : Icons.circle_outlined, size: 10, color: isNew ? accent : Theme.of(context).colorScheme.outline), title: Text('${item['tieu_de']}', style: TextStyle(fontWeight: isNew ? FontWeight.w600 : FontWeight.w500)), subtitle: Text('${item['noi_dung']}\n${date(item['luc'])}', style: const TextStyle(fontSize: 13)), isThreeLine: true, trailing: const Icon(Icons.chevron_right), onTap: () => Navigator.pop(context, '${item['link']}'));
    }))])));
  }
}

