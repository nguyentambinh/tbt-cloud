// Nguyễn Tâm Bình - 2324801030003
import 'dart:async';
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
import 'package:tbt_cloud/screens/admin_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/app_shell.dart';

http.Response response(dynamic value, [int status = 200]) => http.Response(jsonEncode(value), status, headers: {'content-type': 'application/json'});
Finder field(String label) => find.widgetWithText(TextFormField, label);
final pending = {'email_masked': 'b***@example.com', 'resend_after': 60, 'expires_in': 600};
final account = {'id': 1, 'email': 'binh@example.com', 'username': 'binh.003', 'ho_ten': 'Nguyễn Tâm Bình', 'role': 'admin', 'created_at': '2026-11-23T00:00:00Z'};

Future<void> fill(WidgetTester tester) async {
  for (final value in [('Họ và tên', 'Nguyễn Tâm Bình'), ('Tên tài khoản', 'Binh.003'), ('Mật khẩu', 'Binh@123'), ('Xác nhận mật khẩu', 'Binh@123'), ('Gmail', 'Binh@Example.com')]) {
    await tester.ensureVisible(field(value.$1)); await tester.enterText(field(value.$1), value.$2); await tester.pumpAndSettle();
  }
}
Future<void> press(WidgetTester tester, String label) async {
  final button = find.widgetWithText(FilledButton, label);
  await tester.pumpAndSettle(); await tester.ensureVisible(button); await tester.pumpAndSettle(); await tester.tap(button); await tester.pumpAndSettle();
}
Future<void> capture(WidgetTester tester, GlobalKey key, String name) async {
  await tester.runAsync(() async {
    final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final picture = await boundary.toImage();
    final data = await picture.toByteData(format: ui.ImageByteFormat.png);
    final file = File('build/surfaces/registration-$name.png');
    await file.parent.create(recursive: true); await file.writeAsBytes(data!.buffer.asUint8List()); picture.dispose();
  });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    for (final font in [('Barlow Condensed', 'BarlowCondensed-SemiBold.ttf'), ('Be Vietnam Pro', 'BeVietnamPro-Regular.ttf'), ('Roboto', 'BeVietnamPro-Regular.ttf')]) {
      await (FontLoader(font.$1)..addFont(rootBundle.load('assets/fonts/${font.$2}'))).load();
    }
  });
  for (final width in [390.0, 1440.0]) {
    for (final brightness in [Brightness.light, Brightness.dark]) {
      testWidgets('Đăng ký rồi xác nhận vào máy chủ $width $brightness', (tester) async {
        tester.view.physicalSize = Size(width, 1100); tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
        final calls = <String>[];
        final state = CloudState(ApiClient(client: MockClient((request) async {
          calls.add(request.url.path);
          if (request.url.path.endsWith('/auth/register')) {
            expect(request.headers.containsKey('Authorization'), isFalse);
            expect(jsonDecode(request.body), {'ho_ten': 'Nguyễn Tâm Bình', 'username': 'binh.003', 'password': 'Binh@123', 'password_confirm': 'Binh@123', 'email': 'binh@example.com'});
            return response(pending, 202);
          }
          if (request.url.path.endsWith('/auth/register/verify')) { expect(jsonDecode(request.body), {'email': 'binh@example.com', 'code': '012345'}); return response({'access_token': 'verified-token'}); }
          if (request.url.path.endsWith('/me')) return response(account);
          if (request.url.path.endsWith('/balance')) return response({'balance': 0});
          return response([]);
        })))..api.token = null;
        final router = GoRouter(initialLocation: '/dang-ky', routes: [GoRoute(path: '/dang-ky', builder: (_, _) => AuthScreen(state: state, register: true, next: '/vi')), GoRoute(path: '/may-chu', builder: (_, _) => const Scaffold(body: Text('Máy chủ đã xác nhận')))]);
        addTearDown(router.dispose); addTearDown(state.dispose);
        final key = GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key: key, child: MaterialApp.router(theme: cloudTheme(brightness), routerConfig: router)));
        expect(tester.widgetList<TextField>(find.byType(TextField)).map((w) => w.decoration?.labelText), ['Họ và tên', 'Tên tài khoản', 'Mật khẩu', 'Xác nhận mật khẩu', 'Gmail']);
        await fill(tester); await tester.ensureVisible(find.text('Đăng ký tài khoản')); await tester.pumpAndSettle();
        await capture(tester, key, 'form-$width-${brightness.name}');
        await press(tester, 'Đăng ký');
        expect(find.textContaining('b***@example.com'), findsOneWidget); expect(state.signedIn, isFalse); expect(calls.length, 1);
        expect(tester.widget<TextButton>(find.widgetWithText(TextButton, 'Gửi lại mã sau 60 giây')).onPressed, isNull);
        await capture(tester, key, 'code-$width-${brightness.name}');
        await tester.enterText(field('Mã xác nhận'), 'abc01234567');
        expect(tester.widget<TextFormField>(field('Mã xác nhận')).controller!.text, '012345');
        await press(tester, 'Xác nhận và tiếp tục');
        expect(find.text('Máy chủ đã xác nhận'), findsOneWidget); expect(state.api.token, 'verified-token'); expect(state.user?['username'], 'binh.003');
        expect(calls.any((path) => path.endsWith('/auth/login')), isFalse); expect(tester.takeException(), isNull);
      });
    }
  }

  testWidgets('Sai mã, gửi lại sau 60 giây và đổi email giữ thông tin', (tester) async {
    final calls = <String>[];
    final state = CloudState(ApiClient(client: MockClient((request) async {
      calls.add(request.url.path);
      if (request.url.path.endsWith('/verify')) return response({'detail': 'Mã xác nhận chưa đúng. Còn 4 lần thử.'}, 400);
      return response(pending, 202);
    })))..api.token = null;
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.dark), home: AuthScreen(state: state, register: true)));
    await fill(tester); await press(tester, 'Đăng ký');
    await tester.enterText(field('Mã xác nhận'), '123'); await press(tester, 'Xác nhận và tiếp tục');
    expect(find.text('Nhập đủ 6 chữ số trong email.'), findsOneWidget); expect(calls.length, 1);
    await tester.enterText(field('Mã xác nhận'), '123456'); await press(tester, 'Xác nhận và tiếp tục');
    expect(find.text('Mã xác nhận chưa đúng. Còn 4 lần thử.'), findsOneWidget);
    await tester.pump(const Duration(seconds: 60)); await tester.pump();
    await tester.tap(find.widgetWithText(TextButton, 'Gửi lại mã')); await tester.pumpAndSettle();
    expect(calls.last, endsWith('/auth/register/resend')); expect(find.textContaining('Còn 4 lần'), findsNothing);
    expect(find.text('Gửi lại mã sau 60 giây'), findsOneWidget);
    await tester.tap(find.text('Đổi email')); await tester.pumpAndSettle();
    for (final value in [('Họ và tên', 'Nguyễn Tâm Bình'), ('Tên tài khoản', 'Binh.003'), ('Gmail', 'Binh@Example.com'), ('Mật khẩu', ''), ('Xác nhận mật khẩu', '')]) {
      expect(tester.widget<TextFormField>(field(value.$1)).controller!.text, value.$2);
    }
    expect(tester.takeException(), isNull);
  });

  for (final invalid in [('Họ và tên', 'Bình 123'), ('Họ và tên', 'A'), ('Tên tài khoản', '1binh'), ('Tên tài khoản', 'bình'), ('Tên tài khoản', 'a' * 31), ('Mật khẩu', 'abcdefgh1@'), ('Mật khẩu', 'ABCDEFGH1@'), ('Mật khẩu', 'Abcdefgh@'), ('Mật khẩu', 'Abcdefgh1'), ('Mật khẩu', 'Abcd 123@'), ('Xác nhận mật khẩu', 'Another@123'), ('Gmail', 'not-an-email'), ('Gmail', 'a..b@example.com'), ('Gmail', 'a@b..com'), ('Gmail', 'a@-b.com')]) {
    testWidgets('Form chặn ${invalid.$1}: ${invalid.$2}', (tester) async {
      var calls = 0;
      final state = CloudState(ApiClient(client: MockClient((_) async { calls++; return response(pending, 202); })));
      addTearDown(state.dispose);
      await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: AuthScreen(state: state, register: true)));
      await fill(tester); await tester.enterText(field(invalid.$1), invalid.$2); await press(tester, 'Đăng ký');
      expect(tester.widget<Form>(find.byType(Form)).key, isNotNull); expect(calls, 0);
      expect(find.byType(TextFormField), findsNWidgets(5)); expect(tester.takeException(), isNull);
    });
  }

  testWidgets('Ẩn hiện hai mật khẩu và báo trùng ngay dưới ô', (tester) async {
    final state = CloudState(ApiClient(client: MockClient((_) async => response({'detail': 'Tên tài khoản đã được sử dụng. Hãy chọn tên khác.'}, 409))));
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: AuthScreen(state: state, register: true)));
    await fill(tester);
    for (final value in [('Mật khẩu', 'Hiện mật khẩu'), ('Xác nhận mật khẩu', 'Hiện xác nhận mật khẩu')]) {
      expect(tester.widget<TextField>(find.descendant(of: field(value.$1), matching: find.byType(TextField))).obscureText, isTrue);
      await tester.ensureVisible(find.byTooltip(value.$2)); await tester.pumpAndSettle(); await tester.tap(find.byTooltip(value.$2)); await tester.pumpAndSettle();
      expect(tester.widget<TextField>(find.descendant(of: field(value.$1), matching: find.byType(TextField))).obscureText, isFalse);
    }
    await press(tester, 'Đăng ký');
    expect(tester.widget<TextField>(find.descendant(of: field('Tên tài khoản'), matching: find.byType(TextField))).decoration?.errorText, contains('đã được sử dụng'));
  });

  testWidgets('Gửi một lần khi bấm liên tiếp và xử lý SMTP lỗi', (tester) async {
    final result = Completer<http.Response>(); var calls = 0;
    final state = CloudState(ApiClient(client: MockClient((_) { calls++; return result.future; })));
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: AuthScreen(state: state, register: true)));
    await fill(tester);
    final button = find.widgetWithText(FilledButton, 'Đăng ký');
    await tester.ensureVisible(button); await tester.pumpAndSettle(); await tester.tap(button); await tester.tap(button); await tester.pump();
    expect(calls, 1); expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed, isNull);
    result.complete(response({'detail': 'Chưa gửi được mã xác nhận. Vui lòng thử lại sau ít phút.'}, 503)); await tester.pumpAndSettle();
    expect(find.textContaining('Chưa gửi được mã xác nhận.'), findsOneWidget);
    expect(find.byType(TextFormField), findsNWidgets(5));
  });

  testWidgets('Menu tài khoản và quản trị hiển thị họ tên, username, email', (tester) async {
    final state = CloudState(ApiClient(client: MockClient((request) async => response(request.url.path.endsWith('/data/users') ? {'items': [account], 'columns': ['ho_ten', 'username', 'email'], 'total': 1} : <String, dynamic>{}))))..user = account;
    final router = GoRouter(initialLocation: '/quan-tri', routes: [GoRoute(path: '/quan-tri', builder: (_, _) => AppShell(state: state, child: AdminScreen(state: state))), GoRoute(path: '/quan-tri/nguoi-dung', builder: (_, _) => AppShell(state: state, child: AdminScreen(state: state, area: 'nguoi-dung')))]);
    addTearDown(state.dispose); addTearDown(router.dispose);
    await tester.pumpWidget(MaterialApp.router(theme: cloudTheme(Brightness.dark), routerConfig: router)); await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Tài khoản')); await tester.pumpAndSettle();
    for (final text in ['Nguyễn Tâm Bình', '@binh.003', 'binh@example.com']) { expect(find.text(text), findsOneWidget); }
    await tester.tapAt(const Offset(10, 500)); await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Mở điều hướng')); await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: find.byType(Drawer), matching: find.text('Người dùng'))); await tester.pumpAndSettle();
    for (final text in ['Nguyễn Tâm Bình', 'binh.003', 'binh@example.com']) { expect(find.text(text), findsOneWidget); }
  });
}
