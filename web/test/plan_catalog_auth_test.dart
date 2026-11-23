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
import 'package:tbt_cloud/screens/auth_screen.dart';
import 'package:tbt_cloud/screens/create_screen.dart';
import 'package:tbt_cloud/screens/landing_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/common.dart';

http.Response response(dynamic data, [int status = 200]) => http.Response(jsonEncode(data), status, headers: {'content-type': 'application/json'});
final catalog = <Json>[
  for (final group in [('vps', 'Máy'), ('postgres', 'CSDL'), ('webapp', 'Web')])
    for (final price in [2000, 300, 1000])
      {'id': (group.$1 == 'vps' ? 0 : group.$1 == 'postgres' ? 10 : 20) + price, 'ten': '${group.$2} $price', 'dich_vu': group.$1, 'mo_ta': 'Ứng dụng thử và môi trường học tập', 'vcpu': 2, 'ram_mb': 2048, 'disk_gb': 10, 'gia_theo_gio': '$price'},
];

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    for (final font in [('Barlow Condensed', 'BarlowCondensed-SemiBold.ttf'), ('Be Vietnam Pro', 'BeVietnamPro-Regular.ttf'), ('Roboto', 'BeVietnamPro-Regular.ttf')]) {
      await (FontLoader(font.$1)..addFont(rootBundle.load('assets/fonts/${font.$2}'))).load();
    }
  });

  for (final width in [390.0, 1440.0]) {
    for (final brightness in [Brightness.light, Brightness.dark]) {
      testWidgets('Lọc và chọn gói rẻ nhất $width $brightness', (tester) async {
        tester.view.physicalSize = Size(width, 1000); tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
        final state = CloudState(ApiClient(client: MockClient((_) async => response([]))))..plans = catalog;
        addTearDown(state.dispose);
        final capture = GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key: capture, child: MaterialApp(theme: cloudTheme(brightness), home: Scaffold(body: CreateScreen(state: state)))));
        await tester.pumpAndSettle();
        for (final service in ['vps', 'postgres', 'webapp', 'vps']) {
          final choice = find.widgetWithText(ChoiceChip, serviceName(service));
          await tester.ensureVisible(choice); await tester.tap(choice); await tester.pumpAndSettle();
          var choices = tester.widget<PlanChoices>(find.byType(PlanChoices));
          expect(choices.plans.map((p) => p['dich_vu']), everyElement(service));
          expect(choices.plans.map((p) => number(p['gia_theo_gio'])), [300, 1000, 2000]);
          expect(choices.selected, choices.plans.first['id']);
          final expensive = find.text(choices.plans.last['ten'] as String);
          await tester.ensureVisible(expensive); await tester.tap(expensive); await tester.pump();
          choices = tester.widget<PlanChoices>(find.byType(PlanChoices));
          expect(choices.selected, choices.plans.last['id']);
          expect(find.textContaining('216.000đ / tháng'), findsOneWidget);
          expect(find.text('Ứng dụng thử và môi trường học tập'), findsNWidgets(3));
          expect(tester.takeException(), isNull);
        }
        await tester.ensureVisible(find.text('Loại dịch vụ')); await tester.pumpAndSettle();
        await saveCapture(tester, capture, 'create-$width-${brightness.name}');
      });

      testWidgets('Landing bảng giá ba dịch vụ $width $brightness', (tester) async {
        tester.view.physicalSize = Size(width, 1000); tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
        final api = ApiClient(client: MockClient((request) async {
          expect(request.headers.containsKey('Authorization'), isFalse);
          return response(request.url.path.endsWith('/plans') ? catalog : []);
        }))..token = 'private-session';
        final capture = GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key: capture, child: MaterialApp(theme: cloudTheme(brightness), home: LandingScreen(api: api))));
        await tester.pumpAndSettle();
        expect(find.byType(PlanChoices), findsNothing);
        final all = find.byKey(const ValueKey('need-all')); await tester.ensureVisible(all); await tester.tap(all); await tester.pumpAndSettle();
        expect(find.text('Bảng giá'), findsOneWidget);
        for (final title in ['Máy chủ ảo', 'Cơ sở dữ liệu PostgreSQL', 'Ứng dụng web']) {
          expect(find.text(title), title == 'Máy chủ ảo' ? findsOneWidget : findsNWidgets(2));
        }
        expect(find.byType(PlanChoices), findsNWidgets(4));
        for (final service in ['vps', 'postgres', 'webapp']) {
          final choices = tester.widgetList<PlanChoices>(find.byType(PlanChoices)).firstWhere((w) => w.plans.first['dich_vu'] == service);
          expect(choices.plans.length, 3);
          expect(choices.plans.map((p) => p['dich_vu']), everyElement(service));
        }
        await tester.ensureVisible(find.text('Bảng giá')); await tester.pumpAndSettle();
        await saveCapture(tester, capture, 'pricing-$width-${brightness.name}');
        expect(tester.takeException(), isNull);
      });
    }
  }

  testWidgets('Loại chưa có gói không gửi yêu cầu tạo', (tester) async {
    var calls = 0;
    final state = CloudState(ApiClient(client: MockClient((_) async { calls++; return response({}); })))..plans = catalog.where((p) => p['dich_vu'] == 'vps').toList();
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: CreateScreen(state: state))));
    await tester.ensureVisible(find.widgetWithText(ChoiceChip, serviceName('postgres'))); await tester.tap(find.widgetWithText(ChoiceChip, serviceName('postgres'))); await tester.pump();
    final choices = tester.widget<PlanChoices>(find.byType(PlanChoices));
    expect(choices.plans, isEmpty); expect(choices.selected, isNull);
    expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Tạo dịch vụ')).onPressed, isNull);
    expect(calls, 0);
  });

  testWidgets('Đăng nhập admin/admin gửi đúng body', (tester) async {
    Json? body;
    final api = ApiClient(client: MockClient((request) async {
      if (request.url.path.endsWith('/auth/login')) {
        body = Map<String, dynamic>.from(jsonDecode(request.body) as Map);
        expect(request.headers.containsKey('Authorization'), isFalse);
        return response({'access_token': 'fixture-token'});
      }
      if (request.url.path.endsWith('/me')) return response({'id': 1, 'role': 'admin'});
      if (request.url.path.endsWith('/balance')) return response({'balance': 0});
      return response([]);
    }));
    final state = CloudState(api);
    final router = GoRouter(initialLocation: '/dang-nhap', routes: [GoRoute(path: '/dang-nhap', builder: (_, _) => AuthScreen(state: state)), GoRoute(path: '/quan-tri', builder: (_, _) => const Scaffold(body: Text('Quản trị thử')))]);
    addTearDown(router.dispose); addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp.router(theme: cloudTheme(Brightness.light), routerConfig: router));
    await tester.enterText(find.widgetWithText(TextFormField, 'Tên tài khoản hoặc email'), 'admin');
    await tester.enterText(find.widgetWithText(TextFormField, 'Mật khẩu'), 'admin');
    await tester.tap(find.widgetWithText(FilledButton, 'Đăng nhập')); await tester.pumpAndSettle();
    expect(body, {'email': 'admin', 'password': 'admin'});
    expect(find.text('Quản trị thử'), findsOneWidget);
  });

  for (final input in [('admin', 'Valid-password-123', 'Nhập địa chỉ email hợp lệ.'), ('a b@example.test', 'Valid-password-123', 'Nhập địa chỉ email hợp lệ.'), ('valid@example.test', 'admin', 'Mật khẩu cần từ 8 đến 128 ký tự.'), ('valid@example.test', 'a' * 129, 'Mật khẩu cần từ 8 đến 128 ký tự.')]) {
    testWidgets('Đăng ký chặn ${input.$1} dài ${input.$2.length}', (tester) async {
      var calls = 0;
      final state = CloudState(ApiClient(client: MockClient((_) async { calls++; return response({}); })));
      addTearDown(state.dispose);
      await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: AuthScreen(state: state, register: true)));
      await tester.enterText(find.widgetWithText(TextFormField, 'Họ và tên'), 'Nguyễn Tâm Bình');
      await tester.enterText(find.widgetWithText(TextFormField, 'Tên tài khoản'), 'binh.003');
      await tester.enterText(find.widgetWithText(TextFormField, 'Gmail'), input.$1);
      await tester.enterText(find.widgetWithText(TextFormField, 'Mật khẩu'), input.$2);
      await tester.enterText(find.widgetWithText(TextFormField, 'Xác nhận mật khẩu'), input.$2);
      final submit = find.widgetWithText(FilledButton, 'Đăng ký');
      await tester.ensureVisible(submit); await tester.tap(submit); await tester.pump();
      expect(find.text(input.$3), findsOneWidget); expect(calls, 0);
    });
  }

  testWidgets('Đăng ký email hợp lệ gửi được yêu cầu', (tester) async {
    Json? body;
    final state = CloudState(ApiClient(client: MockClient((request) async {
      expect(request.url.path, endsWith('/auth/register'));
      body = Map<String, dynamic>.from(jsonDecode(request.body) as Map);
      return response({'detail': 'Email này đã được đăng ký.'}, 409);
    })));
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: AuthScreen(state: state, register: true)));
    await tester.enterText(find.widgetWithText(TextFormField, 'Họ và tên'), 'Nguyễn Tâm Bình');
    await tester.enterText(find.widgetWithText(TextFormField, 'Tên tài khoản'), 'binh.003');
    await tester.enterText(find.widgetWithText(TextFormField, 'Gmail'), 'valid@example.test');
    await tester.enterText(find.widgetWithText(TextFormField, 'Mật khẩu'), 'Valid-password-123');
    await tester.enterText(find.widgetWithText(TextFormField, 'Xác nhận mật khẩu'), 'Valid-password-123');
    final submit = find.widgetWithText(FilledButton, 'Đăng ký');
    await tester.ensureVisible(submit); await tester.tap(submit); await tester.pumpAndSettle();
    expect(body, {'ho_ten': 'Nguyễn Tâm Bình', 'username': 'binh.003', 'email': 'valid@example.test', 'password': 'Valid-password-123', 'password_confirm': 'Valid-password-123'});
  });
}

Future<void> saveCapture(WidgetTester tester, GlobalKey key, String name) async {
  await tester.runAsync(() async {
    final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final picture = await boundary.toImage();
    final bytes = (await picture.toByteData(format: ui.ImageByteFormat.png))!;
    final file = File('build/surfaces/catalog-$name.png');
    await file.parent.create(recursive: true); await file.writeAsBytes(bytes.buffer.asUint8List()); picture.dispose();
  });
}
