// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../api/cloud_state.dart';
import '../theme/cloud_theme.dart';
import 'brand_logo.dart';
import 'common.dart';
import 'header_tools.dart';

const destinations = [('/may-chu', 'Máy chủ', Icons.dns_outlined), ('/tao-vps', 'Tạo VPS', Icons.add_circle_outline), ('/vi', 'Ví', Icons.account_balance_wallet_outlined), ('/nhat-ky', 'Nhật ký', Icons.history_outlined)];
const adminDestinations = [('/quan-tri', 'Tổng quan', Icons.analytics_outlined), ('/quan-tri/ban-do', 'Bản đồ', Icons.hub_outlined), ('/quan-tri/nguoi-dung', 'Người dùng', Icons.people_outline), ('/quan-tri/truy-xuat', 'Truy xuất', Icons.manage_search_outlined), ('/quan-tri/cap-nhat', 'Cập nhật', Icons.tune_outlined), ('/quan-tri/sao-luu', 'Sao lưu', Icons.backup_outlined)];

class AppShell extends StatefulWidget {
  final CloudState state;
  final Widget child;
  const AppShell({super.key, required this.state, required this.child});
  @override
  State<AppShell> createState() => _AppShellState();
}
class _AppShellState extends State<AppShell> {
  @override
  void initState() { super.initState(); if (widget.state.user == null) Future.microtask(widget.state.refresh); }
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: widget.state, builder: (context, _) {
    final width = MediaQuery.sizeOf(context).width;
    final mobile = width < 1100;
    final path = GoRouterState.of(context).uri.path;
    final items = widget.state.admin ? adminDestinations : destinations;
    final wallet = InkWell(key: const ValueKey('header-wallet'), onTap: () => context.go('/vi'), child: Padding(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8), child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.end, children: [Text(money(widget.state.balance), style: figures.copyWith(fontSize: 24)), Text(widget.state.hours == null ? 'Chưa có VPS đang chạy' : 'còn khoảng ${widget.state.hours!.floor()} giờ chạy', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 11, color: widget.state.hours != null && widget.state.hours! < 24 ? (Theme.of(context).brightness == Brightness.dark ? CloudColors.yellow : const Color(0xFF715300)) : Theme.of(context).colorScheme.onSurfaceVariant))])));
    final header = Row(children: [if (mobile) Builder(builder: (context) => IconButton(tooltip: 'Mở điều hướng', onPressed: () => Scaffold.of(context).openDrawer(), icon: const Icon(Icons.menu_outlined))), InkWell(onTap: () => context.go(widget.state.admin ? '/quan-tri' : '/'), child: BrandLogo(compact: width < 600)), if (!mobile) ...[const SizedBox(width: 18), ...items.map((d) { final selected = path == d.$1 || d.$1 != '/quan-tri' && path.startsWith('${d.$1}/'); return TextButton(onPressed: () => context.go(d.$1), child: Text(d.$2, style: TextStyle(color: selected ? (Theme.of(context).brightness == Brightness.dark ? const Color(0xFFD5AFF1) : CloudColors.purple) : Theme.of(context).colorScheme.onSurface, decoration: selected ? TextDecoration.underline : null))); })], const Spacer(), if (!widget.state.admin) SizedBox(width: width < 600 ? 156 : 205, child: wallet), if (width >= 600) ThemeButton(state: widget.state), NotificationBell(state: widget.state), PopupMenuButton<String>(key: const ValueKey('header-account'), tooltip: 'Tài khoản', padding: EdgeInsets.zero, icon: const Icon(Icons.account_circle_outlined), onSelected: (value) { if (value.startsWith('theme-')) { widget.state.setTheme(ThemeMode.values.byName(value.substring(6))); } else if (value == 'logout') { widget.state.logout(); context.go('/dang-nhap'); } else { context.go('/quan-tri'); } }, itemBuilder: (_) => [PopupMenuItem(enabled: false, child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [if (widget.state.user?['ho_ten'] != null) Text(widget.state.user!['ho_ten'] as String), if (widget.state.user?['username'] != null) Text('@${widget.state.user!["username"]}'), Text(widget.state.user?['email'] ?? 'Tài khoản')])), if (width < 600) ...[for (final o in const [(ThemeMode.system, 'Giao diện theo hệ thống'), (ThemeMode.light, 'Giao diện sáng'), (ThemeMode.dark, 'Giao diện tối')]) CheckedPopupMenuItem(value: 'theme-${o.$1.name}', checked: widget.state.themeMode == o.$1, child: Text(o.$2)), const PopupMenuDivider()], if (widget.state.admin) const PopupMenuItem(value: 'admin', child: Text('Quản trị')), const PopupMenuItem(value: 'logout', child: Text('Đăng xuất'))])]);
    return Scaffold(appBar: PreferredSize(preferredSize: const Size.fromHeight(82), child: Container(decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Theme.of(context).dividerColor))), child: SafeArea(child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1440), child: Padding(padding: EdgeInsets.symmetric(horizontal: width < 700 ? 20 : 40), child: SizedBox(height: 82, child: header))))))), drawer: mobile ? Drawer(child: SafeArea(child: Column(children: [const SizedBox(height: 24), const BrandLogo(), const SizedBox(height: 24), for (final d in items) ListTile(minTileHeight: 56, selected: path == d.$1, leading: Icon(d.$3), title: Text(d.$2), onTap: () { Navigator.pop(context); context.go(d.$1); })]))) : null, body: Column(children: [if (widget.state.loading) const LinearProgressIndicator(minHeight: 2, color: CloudColors.olive), if (widget.state.error != null) Notice(widget.state.error!, retry: widget.state.refresh), Expanded(child: widget.child)]));
  });
}
