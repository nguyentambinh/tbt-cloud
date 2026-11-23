// Nguyễn Tâm Bình - 2324801030003
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tbt_cloud/api/api_client.dart';
import 'package:tbt_cloud/api/cloud_state.dart';
import 'package:tbt_cloud/map/network_map.dart';
import 'package:tbt_cloud/screens/detail_screen.dart';
import 'package:tbt_cloud/screens/servers_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/app_shell.dart';
import 'package:tbt_cloud/widgets/header_tools.dart';

http.Response response(dynamic data, [int status = 200]) => http.Response(jsonEncode(data), status, headers: {'content-type': 'application/json'});
final plans = <Json>[
  {'id': 1, 'ten': 'Nano', 'dich_vu': 'vps', 'vcpu': 1, 'ram_mb': 512, 'disk_gb': 10, 'gia_theo_gio': '300', 'gpu': 0},
  {'id': 9, 'ten': 'AI Tiêu chuẩn', 'dich_vu': 'vps', 'vcpu': 6, 'ram_mb': 16384, 'disk_gb': 40, 'gia_theo_gio': '9000', 'gpu': 1},
];
final machines = <Json>[
  {'id': 1, 'ten': 'khach1-1', 'user_id': 7, 'node_id': 2, 'plan_id': 1, 'dich_vu': 'vps', 'loai': 'vm', 'ket_noi': 'ssh', 'trang_thai': 'running', 'ip': '10.10.10.5', 'ssh_port': 22010, 'vcpu': 1, 'ram_mb': 512, 'disk_gb': 10, 'gia_theo_gio': '300'},
  {'id': 2, 'ten': 'khach1-2', 'user_id': 7, 'node_id': 3, 'plan_id': 9, 'dich_vu': 'vps', 'loai': 'vm', 'ket_noi': 'ssh', 'trang_thai': 'running', 'ip': '10.20.20.5', 'ssh_port': 22011, 'vcpu': 6, 'ram_mb': 16384, 'disk_gb': 40, 'gia_theo_gio': '9000'},
];

CloudState customer(List<String> calls) {
  final state = CloudState(ApiClient(client: MockClient((request) async {
    calls.add(request.url.path);
    final path = request.url.path;
    if (path.endsWith('/auth/me')) return response({'id': 7, 'email': 'khach1@example.test', 'username': 'khach1', 'role': 'user'});
    if (path.endsWith('/instances')) return response(machines);
    if (path.endsWith('/plans')) return response(plans);
    if (path.endsWith('/billing/balance')) return response({'balance': 50000});
    if (path.endsWith('/public/gpu')) return response({'tong': 1, 'ranh': 0, 'loai': ['NVIDIA GeForce RTX 5060 8 GB']});
    return response([]);
  })));
  state.api.token = 'token';
  return state;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    for (final font in [('Barlow Condensed', 'BarlowCondensed-SemiBold.ttf'), ('Be Vietnam Pro', 'BeVietnamPro-Regular.ttf'), ('Roboto', 'BeVietnamPro-Regular.ttf')]) {
      await (FontLoader(font.$1)..addFont(rootBundle.load('assets/fonts/${font.$2}'))).load();
    }
  });
  testWidgets('khách không thấy Mạng node, bản đồ mesh hay tên node', (tester) async {
    tester.view.physicalSize = const Size(1440, 1400); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    final calls = <String>[];
    final state = customer(calls);
    addTearDown(state.dispose);
    await state.refresh();
    final router = GoRouter(initialLocation: '/may-chu', routes: [ShellRoute(builder: (_, _, child) => AppShell(state: state, child: child), routes: [GoRoute(path: '/may-chu', builder: (_, _) => ServersScreen(state: state))])]);
    addTearDown(router.dispose);
    await tester.pumpWidget(MaterialApp.router(theme: cloudTheme(Brightness.dark), routerConfig: router));
    await tester.pumpAndSettle();
    expect(calls.any((p) => p.contains('/nodes/map')), isFalse);
    expect(find.text('Mạng node'), findsNothing);
    expect(find.byType(NetworkMap), findsNothing);
    expect(find.text('Máy cá nhân'), findsNothing);
    expect(find.textContaining('1 × NVIDIA GeForce RTX 5060 8 GB · 6 vCPU'), findsOneWidget);
    expect(find.text('khach1-1'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('đặt mật khẩu chặn mật khẩu ngắn và gửi đúng body', (tester) async {
    tester.view.physicalSize = const Size(1440, 2400); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    Map<String, dynamic>? sent;
    final api = ApiClient(client: MockClient((request) async {
      final path = request.url.path;
      if (path.endsWith('/password')) { sent = jsonDecode(request.body) as Map<String, dynamic>; return response({'username': 'root', 'password': sent!['password'], 'ket_noi': 'ssh', 'ssh_host': 'gateway.test', 'ssh_port': 22010, 'dia_chi': 'gateway.test:22010'}); }
      if (path.endsWith('/credentials')) return response({'username': 'root', 'password': '12345678', 'ket_noi': 'ssh', 'ssh_host': '103.77.208.60', 'ipv6': '2402:800:639e:f77c::113', 'ssh_port': 22010, 'dia_chi': '103.77.208.60:22010'});
      if (path.endsWith('/detail')) return response({...machines[0], 'ten_he_dieu_hanh': 'Debian 13', 'node_ten': 'node-bi-mat', 'vmid': 120});
      if (path.endsWith('/status-now')) return response({'cpu': 0, 'mem': 0});
      if (path.endsWith('/auth/me')) return response({'id': 7, 'email': 'khach1@example.test', 'role': 'user'});
      return response([]);
    }));
    final state = CloudState(api);
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: Scaffold(body: DetailScreen(state: state, id: 1))));
    await tester.pumpAndSettle();
    expect(find.textContaining('node-bi-mat'), findsNothing);
    expect(find.text('ssh root@2402:800:639e:f77c::113'), findsOneWidget);
    expect(find.text('ssh -p 22010 root@103.77.208.60'), findsOneWidget);
    await tester.ensureVisible(find.byKey(const ValueKey('set-password'))); await tester.tap(find.byKey(const ValueKey('set-password'))); await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('new-password')), '1234567');
    await tester.enterText(find.byKey(const ValueKey('new-password-again')), '1234567');
    await tester.tap(find.byKey(const ValueKey('password-submit'))); await tester.pumpAndSettle();
    expect(find.text('Mật khẩu cần 8 - 128 ký tự.'), findsOneWidget);
    expect(sent, isNull);
    await tester.enterText(find.byKey(const ValueKey('new-password')), '24681357');
    await tester.enterText(find.byKey(const ValueKey('new-password-again')), '24681357');
    await tester.tap(find.byKey(const ValueKey('password-submit'))); await tester.pumpAndSettle();
    expect(sent, {'password': '24681357'});
    expect(tester.takeException(), isNull);
  });

  testWidgets('cài lại đổi hệ điều hành, gói và báo giá mới', (tester) async {
    tester.view.physicalSize = const Size(1440, 3000); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    Object? sent = 'chua-gui';
    final api = ApiClient(client: MockClient((request) async {
      final path = request.url.path;
      if (path.endsWith('/reinstall-options')) return response({'os_ma': 'debian13', 'plan_id': 1, 'gia_theo_gio': '300', 'os': [{'ma': 'debian13', 'ten': 'Debian 13', 'ho': 'linux', 'ket_noi': 'ssh', 'min_ram_mb': 512, 'min_disk_gb': 10}, {'ma': 'windows11', 'ten': 'Windows 11', 'ho': 'windows', 'ket_noi': 'rdp', 'min_ram_mb': 4096, 'min_disk_gb': 64}], 'plans': [{'id': 1, 'ten': 'Nano', 'vcpu': 1, 'ram_mb': 512, 'disk_gb': 10, 'gpu': 0, 'gia_theo_gio': '300', 'du_tai_nguyen': true}, {'id': 5, 'ten': 'Windows', 'vcpu': 2, 'ram_mb': 4096, 'disk_gb': 64, 'gpu': 0, 'gia_theo_gio': '2500', 'du_tai_nguyen': true}, {'id': 6, 'ten': 'Lớn', 'vcpu': 8, 'ram_mb': 16384, 'disk_gb': 100, 'gpu': 0, 'gia_theo_gio': '9000', 'du_tai_nguyen': false}]});
      if (path.endsWith('/reinstall')) { sent = request.body.isEmpty ? null : jsonDecode(request.body); return response({...machines[0], 'plan_id': 5, 'gia_theo_gio': '2500'}); }
      if (path.endsWith('/credentials')) return response({'username': 'root', 'password': 'Ab1!cd2@', 'ket_noi': 'ssh', 'ssh_host': 'gateway.test', 'ssh_port': 22010, 'dia_chi': 'gateway.test:22010'});
      if (path.endsWith('/detail')) return response({...machines[0], 'ten_he_dieu_hanh': 'Debian 13', 'vmid': 120});
      if (path.endsWith('/status-now')) return response({'cpu': 0, 'mem': 0});
      if (path.endsWith('/auth/me')) return response({'id': 7, 'email': 'khach1@example.test', 'role': 'user'});
      return response([]);
    }));
    final state = CloudState(api);
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: Scaffold(body: DetailScreen(state: state, id: 1))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cài lại hệ điều hành').first); await tester.pumpAndSettle();
    expect(find.text('Giá giữ nguyên 300đ / giờ.'), findsOneWidget);
    await tester.ensureVisible(find.text('Windows 11')); await tester.tap(find.text('Windows 11')); await tester.pumpAndSettle();
    expect(find.textContaining('sang 2.500đ / giờ (tăng 2.200đ / giờ)'), findsOneWidget);
    expect(find.text('Máy chủ đang chạy dịch vụ của bạn không còn đủ tài nguyên cho gói này.'), findsOneWidget);
    await tester.ensureVisible(find.byKey(const ValueKey('reinstall-submit'))); await tester.tap(find.byKey(const ValueKey('reinstall-submit'))); await tester.pumpAndSettle();
    expect(find.textContaining('tăng 2.200đ / giờ'), findsWidgets);
    await tester.enterText(find.byType(TextField).last, 'khach1-1'); await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Cài lại hệ điều hành').last); await tester.pumpAndSettle();
    expect(sent, {'os_ma': 'windows11', 'plan_id': 5});
    expect(tester.takeException(), isNull);
  });

  testWidgets('chuông thông báo mở hộp thoại, bấm thông báo tới đúng trang; nút giao diện đổi chế độ', (tester) async {
    tester.view.physicalSize = const Size(1440, 1000); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    var read = 0;
    final state = CloudState(ApiClient(client: MockClient((request) async {
      final path = request.url.path;
      if (path.endsWith('/notifications/read')) { read++; return response({'chua_doc': 0}); }
      if (path.endsWith('/notifications')) return response({'chua_doc': read > 0 ? 0 : 1, 'items': [{'id': 9, 'tieu_de': 'Đã tạo máy chủ khach1-1', 'noi_dung': 'Máy đã chạy.', 'link': '/may-chu/1', 'luc': '2026-11-23T15:00:00Z', 'da_doc': read > 0}]});
      if (path.endsWith('/auth/me')) return response({'id': 7, 'email': 'khach1@example.test', 'role': 'user'});
      if (path.endsWith('/instances')) return response(machines);
      if (path.endsWith('/plans')) return response(plans);
      if (path.endsWith('/billing/balance')) return response({'balance': 50000});
      return response([]);
    })));
    state.api.token = 'token';
    addTearDown(state.dispose);
    await state.refresh();
    expect(state.unread, 1);
    final router = GoRouter(initialLocation: '/vi', routes: [ShellRoute(builder: (_, _, child) => AppShell(state: state, child: child), routes: [GoRoute(path: '/vi', builder: (_, _) => const Text('trang-vi')), GoRoute(path: '/may-chu/:id', builder: (_, r) => Text('chi-tiet-${r.pathParameters['id']}'))])]);
    addTearDown(router.dispose);
    await tester.pumpWidget(MaterialApp.router(theme: cloudTheme(Brightness.light), routerConfig: router));
    await tester.pumpAndSettle();
    expect(find.text('1'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('notification-bell'))); await tester.pumpAndSettle();
    expect(find.byType(NotificationDialog), findsOneWidget);
    expect(read, 1);
    await tester.tap(find.text('Đã tạo máy chủ khach1-1')); await tester.pumpAndSettle();
    expect(find.text('chi-tiet-1'), findsOneWidget);
    expect(state.unread, 0);
    await tester.tap(find.byKey(const ValueKey('theme-button'))); await tester.pumpAndSettle();
    await tester.tap(find.text('Tối')); await tester.pumpAndSettle();
    expect(state.themeMode, ThemeMode.dark);
    expect(tester.takeException(), isNull);
  });
}
