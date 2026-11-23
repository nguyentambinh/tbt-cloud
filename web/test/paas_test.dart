// Nguyễn Tâm Bình - 2324801030003
import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tbt_cloud/api/api_client.dart';
import 'package:tbt_cloud/api/cloud_state.dart';
import 'package:tbt_cloud/screens/create_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/service_connection.dart';

http.Response response(dynamic data, [int status = 200]) => http.Response(jsonEncode(data), status, headers: {'content-type': 'application/json'});
const connection = 'postgresql://app:Fixture-password-123@gateway.example.test:23000/app';
final plan = {'id': 1, 'ten': 'Nhỏ', 'dich_vu': 'vps', 'mo_ta': 'Web cá nhân', 'vcpu': 1, 'ram_mb': 1024, 'disk_gb': 10, 'gia_theo_gio': '500'};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final kind in ['postgres', 'webapp']) {
    for (final width in [390.0, 1440.0]) {
      for (final brightness in [Brightness.light, Brightness.dark]) {
        testWidgets('$kind kết nối ở $width $brightness', (tester) async {
          tester.view.physicalSize = Size(width, 1000); tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
          String? copied;
          tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async { if (call.method == 'Clipboard.setData') copied = (call.arguments as Map)['text'] as String; return null; });
          addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
          final api = ApiClient(client: MockClient((request) async {
            expect(request.url.path, endsWith('/instances/1/service'));
            return response({'dich_vu': kind, 'host': 'gateway.example.test', 'port': 23000, 'connection_string': kind == 'postgres' ? connection : null, 'url': kind == 'webapp' ? 'http://gateway.example.test:23000' : null, 'repo_url': 'https://example.test/app.git', 'branch': 'main'});
          }));
          await tester.pumpWidget(MaterialApp(theme: cloudTheme(brightness), home: Scaffold(body: SingleChildScrollView(padding: const EdgeInsets.all(20), child: ServiceConnection(api: api, id: 1, kind: kind)))));
          await tester.pumpAndSettle();
          if (kind == 'postgres') {
            expect(find.text(connection), findsNothing);
            await tester.tap(find.text('Hiện mật khẩu')); await tester.pump();
            expect(find.text(connection), findsOneWidget);
            await tester.tap(find.text('Ẩn mật khẩu')); await tester.pump();
            expect(find.text(connection), findsNothing);
            await tester.tap(find.text('Sao chép chuỗi kết nối')); await tester.pump();
            expect(copied, connection);
          } else {
            expect(find.text('http://gateway.example.test:23000'), findsOneWidget);
            await tester.tap(find.text('Mở ứng dụng web')); await tester.pump();
            expect(find.text('main'), findsOneWidget);
          }
          expect(tester.takeException(), isNull);
        });
      }
    }
  }
  for (final kind in ['vps', 'postgres', 'webapp']) {
    testWidgets('Tạo $kind gửi cấu hình phù hợp', (tester) async {
      tester.view.physicalSize = const Size(1440, 1400); tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
      final servicePlan = {...plan, 'dich_vu': kind};
      Json? sent;
      final api = ApiClient(client: MockClient((request) async {
        if (request.method == 'POST') { sent = Map<String, dynamic>.from(jsonDecode(request.body) as Map); return response({'id': 1, ...sent!}); }
        if (request.url.path.endsWith('/me')) return response({'id': 1, 'role': 'user'});
        if (request.url.path.endsWith('/balance')) return response({'balance': '10000'});
        if (request.url.path.endsWith('/plans')) return response([servicePlan]);
        return response([]);
      }));
      final state = CloudState(api)..balance = 10000..plans = [servicePlan]..osImages = [{'ma': 'debian13', 'ten': 'Debian 13', 'ho': 'linux', 'min_ram_mb': 512, 'min_disk_gb': 10, 'ket_noi': 'ssh', 'san_sang': true}];
      final router = GoRouter(initialLocation: '/tao-vps', routes: [GoRoute(path: '/tao-vps', builder: (_, _) => Scaffold(body: CreateScreen(state: state))), GoRoute(path: '/may-chu/:id', builder: (_, _) => const Scaffold(body: Text('Chi tiết thử nghiệm')))]);
      addTearDown(router.dispose); addTearDown(state.dispose);
      await tester.pumpWidget(MaterialApp.router(theme: cloudTheme(Brightness.light), routerConfig: router, builder: (context, child) => MediaQuery(data: MediaQuery.of(context).copyWith(disableAnimations: true), child: child!)));
      final choice = find.widgetWithText(ChoiceChip, serviceName(kind));
      await tester.ensureVisible(choice); await tester.tap(choice); await tester.pump();
      if (kind == 'webapp') {
        final repo = find.widgetWithText(TextFormField, 'Kho Git công khai');
        await tester.ensureVisible(repo);
        for (final invalid in ['http://example.test/app.git', 'https://user:pass@example.test/app.git', 'https://@example.test/app.git', 'https://example.test/a b']) {
          await tester.enterText(repo, invalid); await tester.pump();
          expect(find.text('Nhập địa chỉ HTTPS của kho Git công khai, không kèm tài khoản hay mật khẩu.'), findsOneWidget);
        }
        await tester.enterText(repo, 'https://example.test/app.git'); await tester.pump();
        expect(find.text('Nhập địa chỉ HTTPS của kho Git công khai, không kèm tài khoản hay mật khẩu.'), findsNothing);
      }
      await tester.ensureVisible(find.byKey(const ValueKey('advanced-options'))); await tester.tap(find.text('Tùy chọn nâng cao')); await tester.pumpAndSettle();
      final name = find.byKey(const ValueKey('advanced-name'));
      await tester.ensureVisible(name); await tester.enterText(name, 'dich-vu-thu');
      final ssh = find.byKey(const ValueKey('advanced-ssh'));
      await tester.ensureVisible(ssh); await tester.enterText(ssh, 'ssh-ed25519 AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA fixture');
      final submit = find.widgetWithText(FilledButton, 'Tạo dịch vụ');
      await tester.ensureVisible(submit); await tester.tap(submit); await tester.pumpAndSettle();
      expect(sent?['dich_vu'], kind); expect(sent?['loai'], 'vm');
      expect(sent?['plan_id'], servicePlan['id']); expect(sent?['ten'], 'dich-vu-thu'); expect(sent?['ssh_public_key'], startsWith('ssh-ed25519')); expect(sent!.containsKey('cloud_user'), isFalse);
      if (kind == 'webapp') { expect(sent?['repo_url'], 'https://example.test/app.git'); expect(sent?['branch'], 'main'); } else { expect(sent!.containsKey('repo_url'), isFalse); }
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    });
  }
  testWidgets('Lỗi kết nối có lời nhắc thử lại và không lộ exception', (tester) async {
    final api = ApiClient(client: MockClient((_) async => throw StateError('private-exception')));
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: Scaffold(body: ServiceConnection(api: api, id: 1, kind: 'postgres'))));
    await tester.pumpAndSettle();
    expect(find.text('Thử lại'), findsOneWidget);
    expect(find.textContaining('private-exception'), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets('Đổi dịch vụ không hiển thị kết quả yêu cầu cũ', (tester) async {
    final pending = Completer<http.Response>();
    final api = ApiClient(client: MockClient((request) => request.url.path.contains('/1/') ? pending.future : Future.value(response({'host': 'second.example.test', 'port': 23001, 'connection_string': connection.replaceAll('gateway.example.test:23000', 'second.example.test:23001')}))));
    Widget screen(int id) => MaterialApp(home: Scaffold(body: ServiceConnection(api: api, id: id, kind: 'postgres')));
    await tester.pumpWidget(screen(1)); await tester.pump();
    await tester.pumpWidget(screen(2)); await tester.pumpAndSettle();
    pending.complete(response({'host': 'old.example.test', 'port': 23000, 'connection_string': connection}));
    await tester.pumpAndSettle();
    expect(find.text('second.example.test'), findsOneWidget); expect(find.text('old.example.test'), findsNothing);
  });
}
