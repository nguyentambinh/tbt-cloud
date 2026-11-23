// Nguyễn Tâm Bình - 2324801030003
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tbt_cloud/api/api_client.dart';
import 'package:tbt_cloud/api/cloud_state.dart';
import 'package:tbt_cloud/screens/admin_screen.dart';
import 'package:tbt_cloud/screens/auth_screen.dart';
import 'package:tbt_cloud/screens/create_screen.dart';
import 'package:tbt_cloud/screens/detail_screen.dart';
import 'package:tbt_cloud/screens/landing_screen.dart';
import 'package:tbt_cloud/screens/logs_screen.dart';
import 'package:tbt_cloud/screens/servers_screen.dart';
import 'package:tbt_cloud/screens/wallet_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/app_shell.dart';
import 'package:tbt_cloud/widgets/common.dart';

final nodes = [for (var i = 1; i <= 3; i++) {'id': i, 'ten': ['Máy ASUS', 'Máy Dell', 'Máy thành viên'][i - 1], 'proxmox_node': 'pve-node-$i', 'online': true, 'last_seen_at': DateTime.now().toUtc().toIso8601String(), 'total_vcpu': 16, 'used_vcpu': i * 2, 'total_ram_mb': 16384, 'used_ram_mb': i * 1024, 'total_disk_gb': 200, 'used_disk_gb': i * 20}];
final plans = [{'id': 1, 'ten': 'Nhỏ', 'vcpu': 1, 'ram_mb': 1024, 'disk_gb': 10, 'gia_theo_gio': '500'}, {'id': 2, 'ten': 'Vừa', 'vcpu': 2, 'ram_mb': 2048, 'disk_gb': 20, 'gia_theo_gio': '1000'}];
final instances = [for (var i = 1; i <= 3; i++) {'id': i, 'ten': ['may-chu-web', 'api-thu-nghiem', 'du-lieu-nho'][i - 1], 'user_id': 1, 'node_id': i, 'plan_id': i == 2 ? 2 : 1, 'trang_thai': i == 3 ? 'stopped' : 'running', 'loai': 'vm', 'ip': '10.10.10.${100 + i}', 'ssh_port': 22000 + i, 'vcpu': i == 2 ? 2 : 1, 'ram_mb': i == 2 ? 2048 : 1024, 'disk_gb': 10, 'gia_theo_gio': i == 2 ? '1000' : '500', 'paid_until': '2026-11-23T12:00:00Z', 'created_at': '2026-11-22T10:00:00Z', 'ngay_tao': '2026-11-22T10:00:00Z', 'vmid': 100 + i, 'node_ten': nodes[i - 1]['ten'], 'ten_he_dieu_hanh': 'Debian 13', 'tong_chi_phi': '1500'}];

CloudState fixture() {
  final api = ApiClient(client: MockClient((request) async {
    final path = request.url.path;
    dynamic value;
    if (path.endsWith('/plans')) { value = plans; }
    else if (path.endsWith('/map')) { value = nodes; }
    else if (path.endsWith('/auth/me')) { value = {'id': 1, 'email': 'kiem-thu@example.test', 'role': 'admin'}; }
    else if (path.endsWith('/detail')) { value = instances.first; }
    else if (path.endsWith('/credentials')) { value = {'username': 'debian', 'password': 'Fake-test-only-123', 'ssh_host': 'gateway.example.test', 'ssh_port': 22001}; }
    else if (path.endsWith('/status-now')) { value = {'cpu': 12.5, 'mem': 412 * 1024 * 1024, 'uptime': 3600}; }
    else if (path.endsWith('/stats')) { value = [for (var i = 0; i < 48; i++) {'time': 1795360000 + i * 60, 'cpu': 8 + i % 11, 'mem_used': (300 + i * 2) * 1024 * 1024, 'mem_total': 1024 * 1024 * 1024}]; }
    else if (path.endsWith('/balance')) { value = {'balance': '99500'}; }
    else if (path.endsWith('/instances')) { value = instances; }
    else if (path.endsWith('/logs') || path.endsWith('/audit-logs')) { value = [{'id': 1, 'action': 'instance.create', 'resource': 'instance:1', 'created_at': '2026-11-22T10:00:00Z', 'detail': ''}]; }
    else if (path.endsWith('/transactions')) { value = [{'id': 1, 'amount': '-500', 'kind': 'usage', 'instance_id': 1, 'created_at': '2026-11-22T10:00:00Z'}]; }
    else if (path.endsWith('/users')) { value = [{'id': 1, 'email': 'kiem-thu@example.test', 'role': 'admin', 'created_at': '2026-11-22T10:00:00Z'}]; }
    else if (path.endsWith('/payos')) { value = []; }
    else { return http.Response(jsonEncode({'detail': 'Chức năng kiểm thử chưa có dữ liệu.'}), 404, headers: {'content-type': 'application/json'}); }
    return http.Response(jsonEncode(value), 200, headers: {'content-type': 'application/json'});
  }));
  api.token = 'fixture-token';
  return CloudState(api)..user = {'id': 1, 'email': 'kiem-thu@example.test', 'role': 'admin'}..balance = 99500..nodes = nodes..plans = plans..instances = instances;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    for (final family in [('Barlow Condensed', 'BarlowCondensed-SemiBold.ttf'), ('Be Vietnam Pro', 'BeVietnamPro-Regular.ttf')]) {
      final loader = FontLoader(family.$1)..addFont(rootBundle.load('assets/fonts/${family.$2}'));
      await loader.load();
    }
  });
  for (final route in ['/', '/may-chu', '/may-chu/1', '/tao-vps', '/vi', '/nhat-ky', '/quan-tri', '/dang-nhap', '/dang-ky']) {
    for (final size in [const Size(1440, 1000), const Size(390, 844)]) {
      testWidgets('$route hiển thị không tràn tại ${size.width}', (tester) async {
        tester.view.physicalSize = size; tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
        final state = fixture(), capture = GlobalKey();
        Widget screen(String path) => switch (path) { '/' => LandingScreen(api: state.api), '/may-chu' => ServersScreen(state: state), '/may-chu/1' => DetailScreen(state: state, id: 1), '/tao-vps' => CreateScreen(state: state), '/vi' => WalletScreen(state: state), '/nhat-ky' => LogsScreen(state: state), '/quan-tri' => AdminScreen(state: state), '/dang-ky' => AuthScreen(state: state, register: true), _ => AuthScreen(state: state) };
        final router = GoRouter(initialLocation: route, routes: [for (final path in ['/', '/dang-nhap', '/dang-ky']) GoRoute(path: path, builder: (_, _) => screen(path)), ShellRoute(builder: (_, _, child) => AppShell(state: state, child: child), routes: [for (final path in ['/may-chu', '/may-chu/1', '/tao-vps', '/vi', '/nhat-ky', '/quan-tri']) GoRoute(path: path, builder: (_, _) => screen(path))])]);
        await tester.pumpWidget(RepaintBoundary(key: capture, child: MaterialApp.router(theme: cloudTheme(Brightness.light), darkTheme: cloudTheme(Brightness.dark), routerConfig: router, builder: (context, child) => MediaQuery(data: MediaQuery.of(context).copyWith(disableAnimations: true), child: Overlay(initialEntries: [OverlayEntry(builder: (_) => SelectionArea(child: child!))])))));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        final name = route == '/may-chu' ? (size.width > 700 ? 'desktop' : 'mobile') : '${route == '/' ? 'landing' : route.substring(1).replaceAll('/', '-')}-${size.width > 700 ? 'desktop' : 'mobile'}';
        await tester.runAsync(() async {
          final boundary = capture.currentContext!.findRenderObject()! as RenderRepaintBoundary;
          final picture = await boundary.toImage();
          final bytes = (await picture.toByteData(format: ui.ImageByteFormat.png))!;
          final file = File('build/surfaces/$name.png');
          await file.parent.create(recursive: true); await file.writeAsBytes(bytes.buffer.asUint8List()); picture.dispose();
        });
        if (route == '/may-chu' && size.width < 700) { await tester.drag(find.byType(PageView), const Offset(-350, 0)); await tester.pumpAndSettle(); expect(tester.takeException(), isNull); }
        await tester.pumpWidget(const SizedBox.shrink()); router.dispose(); state.dispose();
      });
    }
  }
  test('Tiền hiển thị đúng quy ước Việt Nam', () { expect(money('99500'), '99.500đ'); expect(money('-500'), '−500đ'); });
}
