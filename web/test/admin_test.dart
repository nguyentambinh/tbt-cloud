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
import 'package:tbt_cloud/main.dart';
import 'package:tbt_cloud/map/network_map.dart';
import 'package:tbt_cloud/screens/admin_screen.dart';
import 'package:tbt_cloud/screens/landing_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/app_shell.dart';
import 'package:tbt_cloud/widgets/common.dart';

final customer = <String, dynamic>{'id': 7, 'ho_ten': 'Nguyễn An', 'username': 'nguyen.an', 'email': 'an@example.test', 'role': 'user', 'is_blocked': false, 'balance': '250000', 'created_at': '2026-11-01T08:00:00Z'};
final nodes = <Json>[{'id': 1, 'ten': 'Máy ASUS', 'online': true, 'mesh_ip': '100.64.0.2', 'proxmox_node': 'pve-asus', 'storage': 'local-lvm', 'bridge': 'vmbr0', 'trang_thai': 'online', 'total_vcpu': 16, 'used_vcpu': 4, 'total_ram_mb': 16384, 'used_ram_mb': 4096, 'total_disk_gb': 200, 'used_disk_gb': 40}];
final services = <Json>[{'id': 3, 'ten': 'web-cua-an', 'user_id': 7, 'node_id': 1, 'dich_vu': 'webapp', 'trang_thai': 'running'}, {'id': 4, 'ten': 'du-lieu-cua-an', 'user_id': 7, 'node_id': 1, 'dich_vu': 'postgres', 'trang_thai': 'running'}];
final plans = <Json>[for (final type in ['vps', 'postgres', 'webapp']) {'id': ['vps', 'postgres', 'webapp'].indexOf(type) + 1, 'ten': 'Gói $type', 'dich_vu': type, 'mo_ta': 'Môi trường phát triển', 'vcpu': 1, 'ram_mb': 1024, 'disk_gb': 10, 'gia_theo_gio': 500, 'active': true}];
http.Response response(dynamic value, [int status = 200]) => http.Response(jsonEncode(value), status, headers: {'content-type': 'application/json'});
Json page(List<Json> items) => {'items': items, 'total': items.length, 'columns': items.isEmpty ? [] : items.first.keys.toList()};
CloudState fixture({void Function(http.Request)? observe, bool admin = true}) {
  final api = ApiClient(client: MockClient((request) async {
    observe?.call(request);
    final path = request.url.path;
    if (path == '/api/v1/admin/stats') return response({'revenue': 150000, 'spent': 30000, 'wallet_balance': 250000, 'users': 1, 'new_7': 1, 'new_30': 1, 'running': {'service': [{'name': 'webapp', 'count': 1}, {'name': 'postgres', 'count': 1}], 'os': [{'name': 'Debian 13', 'count': 2}], 'node': [{'name': 'Máy ASUS', 'count': 2}]}, 'top_customers': [{...customer, 'spent': 30000}], 'nodes': nodes, 'scope': 'Số liệu giả dùng để kiểm thử widget.'});
    if (path.endsWith('/admin/revenue')) return response({'daily': [for (var i = 1; i <= 30; i++) {'period': '2026-11-${'$i'.padLeft(2, '0')}', 'amount': i == 23 ? 150000 : 0}], 'monthly': [{'period': '2026-11', 'amount': 150000}], 'daily_total': 30});
    if (path.endsWith('/admin/map')) return response({...page(services), 'nodes': nodes});
    if (path.endsWith('/admin/users/7')) return response({...customer, 'transactions': page([{'id': 1, 'kind': 'usage', 'amount': -500, 'description': 'Một giờ chạy', 'created_at': '2026-11-23T00:00:00Z'}]), 'instances': page(services), 'logs': page([{'action': 'auth.login', 'resource': 'user:7', 'detail': '', 'created_at': '2026-11-23T00:00:00Z'}])});
    if (path.endsWith('/admin/data/users')) return response(page([customer]));
    if (path.endsWith('/admin/data/plans')) return response(page(plans));
    if (path.endsWith('/admin/data/nodes')) return response(page(nodes));
    if (path.endsWith('/admin/backups')) return response(page([{'name': '20261123T120000000000-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.dump', 'created_at': '2026-11-23T12:00:00Z', 'created_by': 1, 'size': 32768, 'safety': false}]));
    if (path.endsWith('/auth/me')) return response(admin ? {'id': 1, 'role': 'admin', 'email': 'admin@example.test'} : customer);
    if (path.endsWith('/balance')) return response({'balance': 250000});
    if (path.endsWith('/plans')) return response(plans);
    if (path.endsWith('/map')) return response(nodes);
    if (path.endsWith('/instances')) return response(services);
    if (path.endsWith('/os')) return response([{'ma': 'debian13', 'ten': 'Debian 13', 'san_sang': true, 'ket_noi': 'ssh'}]);
    return response([]);
  }))..token = 'widget-fixture';
  return CloudState(api)..user = admin ? {'id': 1, 'role': 'admin', 'email': 'admin@example.test'} : customer..balance = 250000..nodes = nodes..instances = services..plans = plans;
}
Future<void> capture(WidgetTester tester, GlobalKey key, String name) => tester.runAsync(() async {
  final boundary = key.currentContext!.findRenderObject() as RenderRepaintBoundary;
  final picture = await boundary.toImage();
  final bytes = (await picture.toByteData(format: ui.ImageByteFormat.png))!.buffer.asUint8List();
  final file = File('build/surfaces/admin/$name.png');
  await file.parent.create(recursive: true); await file.writeAsBytes(bytes); picture.dispose();
});
void viewport(WidgetTester tester, double width) { tester.view.physicalSize = Size(width, 1000); tester.view.devicePixelRatio = 1; addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio); }

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    for (final font in [('Barlow Condensed', 'BarlowCondensed-SemiBold.ttf'), ('Be Vietnam Pro', 'BeVietnamPro-Regular.ttf'), ('Roboto', 'BeVietnamPro-Regular.ttf')]) { await (FontLoader(font.$1)..addFont(rootBundle.load('assets/fonts/${font.$2}'))).load(); }
    await (FontLoader('MaterialIcons')..addFont(File('D:/Android/Flutter/flutter/bin/cache/artifacts/material_fonts/materialicons-regular.otf').readAsBytes().then((bytes) => ByteData.sublistView(bytes)))).load();
  });
  for (final width in [390.0, 768.0, 1440.0, 1920.0]) {
    for (final brightness in [Brightness.light, Brightness.dark]) {
      testWidgets('Trang chủ chọn nhu cầu và căn header $width $brightness', (tester) async {
        viewport(tester, width); final state = fixture(admin: false); addTearDown(state.dispose); final key = GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key: key, child: MaterialApp(debugShowCheckedModeBanner: false, theme: cloudTheme(brightness), home: LandingScreen(api: state.api)))); await tester.pumpAndSettle();
        expect(find.byType(NetworkMap), findsNothing); expect(find.byType(PlanChoices), findsNothing);
        expect(tester.getBottomRight(find.byKey(const ValueKey('public-account'))).dx, closeTo((width > 1440 ? (width + 1440) / 2 : width) - (width < 700 ? 20 : 40), 1));
        await capture(tester, key, 'landing-$width-${brightness.name}');
        final vps = find.byKey(const ValueKey('need-vps')); await tester.ensureVisible(vps); await tester.tap(vps); await tester.pumpAndSettle();
        expect(find.byType(PlanChoices), findsOneWidget); expect(tester.widget<PlanChoices>(find.byType(PlanChoices)).plans.first['dich_vu'], 'vps');
        expect(find.text('Hệ điều hành hỗ trợ'), findsOneWidget);
        final postgres = find.byKey(const ValueKey('need-postgres')); await tester.ensureVisible(postgres); await tester.tap(postgres); await tester.pumpAndSettle();
        expect(find.text('Hệ điều hành hỗ trợ'), findsNothing); expect(tester.widget<PlanChoices>(find.byType(PlanChoices)).plans.first['dich_vu'], 'postgres');
        final all = find.byKey(const ValueKey('need-all')); await tester.ensureVisible(all); await tester.tap(all); await tester.pumpAndSettle();
        expect(find.byType(PlanChoices), findsNWidgets(4)); await capture(tester, key, 'pricing-$width-${brightness.name}'); expect(tester.takeException(), isNull);
      });
      for (final area in ['tong-quan', 'ban-do', 'nguoi-dung', 'truy-xuat', 'cap-nhat', 'sao-luu', 'chi-tiet']) {
        testWidgets('Admin $area $width $brightness', (tester) async {
          viewport(tester, width); final state = fixture(); final key = GlobalKey();
          final location = area == 'tong-quan' ? '/quan-tri' : area == 'chi-tiet' ? '/quan-tri/nguoi-dung/7' : '/quan-tri/$area';
          final router = GoRouter(initialLocation: location, routes: [GoRoute(path: location, builder: (_, _) => AppShell(state: state, child: AdminScreen(state: state, area: area == 'chi-tiet' ? 'nguoi-dung' : area, userId: area == 'chi-tiet' ? 7 : null)))]);
          addTearDown(router.dispose); addTearDown(state.dispose);
          await tester.pumpWidget(RepaintBoundary(key: key, child: MaterialApp.router(debugShowCheckedModeBanner: false, theme: cloudTheme(brightness), routerConfig: router))); await tester.pumpAndSettle();
          expect(find.byKey(const ValueKey('header-wallet')), findsNothing); expect(find.text('Tạo VPS'), findsNothing);
          expect(tester.getBottomRight(find.byKey(const ValueKey('header-account'))).dx, closeTo((width > 1440 ? (width + 1440) / 2 : width) - (width < 700 ? 20 : 40), 1));
          await capture(tester, key, '$area-$width-${brightness.name}');
          if (area == 'ban-do') {
            await tester.tap(find.byTooltip('web-cua-an')); await tester.pumpAndSettle();
            final owner = find.text('an@example.test'); await tester.ensureVisible(owner); await tester.pumpAndSettle();
            expect(owner, findsOneWidget); expect(find.text('nguyen.an'), findsOneWidget); expect(find.text('250.000đ'), findsOneWidget); expect(find.text('Chi tiết người dùng'), findsOneWidget);
            await capture(tester, key, 'map-owner-$width-${brightness.name}');
          }
          expect(tester.takeException(), isNull); await tester.pumpWidget(const SizedBox.shrink());
        });
      }
      testWidgets('Header khách sát phải $width $brightness', (tester) async {
        viewport(tester, width); final state = fixture(admin: false); addTearDown(state.dispose);
        final router = GoRouter(initialLocation: '/may-chu', routes: [GoRoute(path: '/may-chu', builder: (_, _) => AppShell(state: state, child: const PageBody(children: [Text('Nội dung khách hàng')])))]); addTearDown(router.dispose);
        await tester.pumpWidget(MaterialApp.router(debugShowCheckedModeBanner: false, theme: cloudTheme(brightness), routerConfig: router)); await tester.pumpAndSettle();
        expect(tester.getBottomRight(find.byKey(const ValueKey('header-account'))).dx, closeTo((width > 1440 ? (width + 1440) / 2 : width) - (width < 700 ? 20 : 40), 1));
        expect(find.byKey(const ValueKey('header-wallet')), findsOneWidget); expect(tester.takeException(), isNull);
      });
    }
  }
  testWidgets('Admin chuyển thẳng quản trị, chặn route thuê và bỏ gọi ví', (tester) async {
    final requests = <String>[]; final state = fixture(observe: (request) => requests.add(request.url.path)); addTearDown(state.dispose);
    await state.refresh(); expect(requests, isNot(contains('/api/v1/billing/balance')));
    await tester.pumpWidget(CloudApp(state: state)); await tester.pumpAndSettle(); expect(find.text('Tổng quan hệ thống'), findsOneWidget);
    GoRouter.of(tester.element(find.byType(AdminScreen))).go('/tao-vps'); await tester.pumpAndSettle(); expect(find.text('Tổng quan hệ thống'), findsOneWidget); expect(find.text('Tạo dịch vụ'), findsNothing);
  });
  testWidgets('Trang chủ cập nhật ví theo phiên khách hàng', (tester) async {
    final state = fixture(admin: false)..balance = 0; addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: LandingScreen(api: state.api, state: state))); await tester.pumpAndSettle();
    expect(find.text('0đ'), findsOneWidget);
    await state.refresh(); await tester.pumpAndSettle();
    expect(find.text('250.000đ'), findsOneWidget); expect(find.text('Đăng ký'), findsNothing);
  });
}
