// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:flutter_web_plugins/url_strategy.dart';
import 'package:go_router/go_router.dart';
import 'api/api_client.dart';
import 'api/cloud_state.dart';
import 'screens/admin_screen.dart';
import 'screens/auth_screen.dart';
import 'screens/console_screen.dart';
import 'screens/create_screen.dart';
import 'screens/detail_screen.dart';
import 'screens/landing_screen.dart';
import 'screens/logs_screen.dart';
import 'screens/servers_screen.dart';
import 'screens/wallet_screen.dart';
import 'theme/cloud_theme.dart';
import 'widgets/app_shell.dart';
import 'widgets/common.dart';

void main() { usePathUrlStrategy(); runApp(const CloudApp()); }

class CloudApp extends StatefulWidget {
  final CloudState? state;
  const CloudApp({super.key, this.state});
  @override
  State<CloudApp> createState() => _CloudAppState();
}
class _CloudAppState extends State<CloudApp> {
  late final state = widget.state ?? CloudState(ApiClient());
  late final router = GoRouter(refreshListenable: state, redirect: (context, route) {
    final path = route.uri.path;
    final public = path == '/' || path == '/dang-nhap' || path == '/dang-ky';
    if (!public && !state.signedIn) return Uri(path: '/dang-nhap', queryParameters: {'tiep': route.uri.toString()}).toString();
    if (path.startsWith('/quan-tri') && state.user != null && !state.admin) return '/may-chu';
    if (state.admin && (path == '/' || path == '/dang-nhap' || path == '/dang-ky' || path.startsWith('/may-chu') || path == '/tao-vps' || path == '/vi' || path == '/nhat-ky' || path.startsWith('/thanh-toan'))) return '/quan-tri';
    return null;
  }, errorBuilder: (context, route) => Scaffold(body: PageBody(children: [const Heading('Không tìm thấy trang', 'Đường dẫn này chưa có trong TBT Cloud.'), FilledButton(onPressed: () => context.go('/'), child: const Text('Về trang giới thiệu'))])), routes: [GoRoute(path: '/', builder: (_, _) => LandingScreen(api: state.api, state: state)), GoRoute(path: '/dang-nhap', builder: (_, r) => AuthScreen(key: const ValueKey('login'), state: state, next: r.uri.queryParameters['tiep'])), GoRoute(path: '/dang-ky', builder: (_, r) => AuthScreen(key: const ValueKey('register'), state: state, register: true, next: r.uri.queryParameters['tiep'])), GoRoute(path: '/may-chu/:id/console', builder: (_, r) => ConsoleScreen(state: state, id: int.tryParse(r.pathParameters['id']!) ?? 0)), ShellRoute(builder: (_, _, child) => AppShell(state: state, child: child), routes: [GoRoute(path: '/may-chu', builder: (_, _) => ServersScreen(state: state)), GoRoute(path: '/tao-vps', builder: (_, _) => CreateScreen(state: state)), GoRoute(path: '/may-chu/:id', builder: (_, r) => DetailScreen(key: ValueKey(r.pathParameters['id']), state: state, id: int.tryParse(r.pathParameters['id']!) ?? 0)), GoRoute(path: '/vi', builder: (_, r) => WalletScreen(key: ValueKey(r.uri.toString()), state: state, orderCode: r.uri.queryParameters['orderCode'])), GoRoute(path: '/nhat-ky', builder: (_, _) => LogsScreen(state: state)), GoRoute(path: '/quan-tri', builder: (_, _) => AdminScreen(state: state)), GoRoute(path: '/quan-tri/nguoi-dung/:id', builder: (_, r) => AdminScreen(state: state, area: 'nguoi-dung', userId: int.tryParse(r.pathParameters['id']!))), for (final area in ['ban-do', 'nguoi-dung', 'truy-xuat', 'cap-nhat', 'sao-luu']) GoRoute(path: '/quan-tri/$area', builder: (_, _) => AdminScreen(state: state, area: area)), for (final path in ['/thanh-toan/ket-qua', '/thanh-toan/huy']) GoRoute(path: path, builder: (_, r) => PaymentResultScreen(state: state, orderCode: r.uri.queryParameters['orderCode']))])]);
  @override
  void initState() { super.initState(); if (state.signedIn && state.user == null) Future.microtask(state.refresh); state.api.onUnauthorized = () { final next = router.routeInformationProvider.value.uri.toString(); state.logout(); router.go(Uri(path: '/dang-nhap', queryParameters: {'tiep': next}).toString()); }; }
  @override
  void dispose() { router.dispose(); if (widget.state == null) state.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: state, builder: (context, _) => MaterialApp.router(title: 'TBT Cloud', debugShowCheckedModeBanner: false, theme: cloudTheme(Brightness.light), darkTheme: cloudTheme(Brightness.dark), themeMode: state.themeMode, routerConfig: router, builder: (context, child) => Overlay(initialEntries: [OverlayEntry(builder: (_) => SelectionArea(child: child!))])));
}
