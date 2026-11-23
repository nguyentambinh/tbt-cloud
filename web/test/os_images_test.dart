// Nguyễn Tâm Bình - 2324801030003
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tbt_cloud/api/api_client.dart';
import 'package:tbt_cloud/api/cloud_state.dart';
import 'package:tbt_cloud/screens/create_screen.dart';
import 'package:tbt_cloud/screens/detail_screen.dart';
import 'package:tbt_cloud/screens/landing_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/common.dart';
import 'package:tbt_cloud/widgets/os_choices.dart';

http.Response response(dynamic data, [int status = 200]) => http.Response(jsonEncode(data), status, headers: {'content-type': 'application/json'});
final images = <Json>[
  {'ma': 'debian13', 'ten': 'Debian 13', 'ho': 'linux', 'min_ram_mb': 512, 'min_disk_gb': 10, 'ket_noi': 'ssh', 'san_sang': true},
  {'ma': 'ubuntu2404', 'ten': 'Ubuntu 24.04 LTS', 'ho': 'linux', 'min_ram_mb': 1024, 'min_disk_gb': 10, 'ket_noi': 'ssh', 'san_sang': true},
  {'ma': 'kali', 'ten': 'Kali Linux', 'ho': 'linux', 'min_ram_mb': 2048, 'min_disk_gb': 25, 'ket_noi': 'ssh', 'san_sang': false},
  {'ma': 'winserver2022', 'ten': 'Windows Server 2022', 'ho': 'windows', 'min_ram_mb': 2048, 'min_disk_gb': 40, 'ket_noi': 'rdp', 'san_sang': false},
  {'ma': 'windows11', 'ten': 'Windows 11', 'ho': 'windows', 'min_ram_mb': 4096, 'min_disk_gb': 64, 'ket_noi': 'rdp', 'san_sang': true},
];
final plans = <Json>[
  {'id': 1, 'ten': 'Nano', 'dich_vu': 'vps', 'vcpu': 1, 'ram_mb': 512, 'disk_gb': 10, 'gia_theo_gio': '300'},
  {'id': 2, 'ten': 'Vừa', 'dich_vu': 'vps', 'vcpu': 2, 'ram_mb': 2048, 'disk_gb': 20, 'gia_theo_gio': '1000'},
  {'id': 3, 'ten': 'Windows Tiêu chuẩn', 'dich_vu': 'vps', 'vcpu': 2, 'ram_mb': 4096, 'disk_gb': 64, 'gia_theo_gio': '2500'},
  {'id': 4, 'ten': 'Windows Hiệu năng', 'dich_vu': 'vps', 'vcpu': 4, 'ram_mb': 8192, 'disk_gb': 80, 'gia_theo_gio': '4500'},
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
      testWidgets('OS và gói phù hợp $width $brightness', (tester) async {
        tester.view.physicalSize = Size(width, 1200); tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
        final state = CloudState(ApiClient(client: MockClient((_) async => response([]))))..osImages = images..plans = plans;
        addTearDown(state.dispose);
        final capture = GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key: capture, child: MaterialApp(theme: cloudTheme(brightness), home: Scaffold(body: CreateScreen(state: state)))));
        await tester.pumpAndSettle();
        expect(tester.getTopLeft(find.text('Hệ điều hành')).dy, lessThan(tester.getTopLeft(find.text('Chọn gói tài nguyên')).dy));
        expect(tester.widget<PlanChoices>(find.byType(PlanChoices)).selected, 1);
        await tester.ensureVisible(find.text('Windows Server 2022')); await tester.tap(find.text('Windows Server 2022')); await tester.pump();
        expect(tester.widget<OSChoices>(find.byType(OSChoices)).selected, 'debian13');
        await tester.ensureVisible(find.text('Windows 11')); await tester.tap(find.text('Windows 11')); await tester.pump();
        var choices = tester.widget<PlanChoices>(find.byType(PlanChoices));
        expect(choices.selected, 3);
        expect(choices.disabledReason!(plans[0]), contains('RAM'));
        expect(find.byKey(const ValueKey('advanced-ssh')), findsNothing);
        expect(tester.widget<Text>(find.byKey(const ValueKey('login-summary'))).data, contains('tbtadmin'));
        await tester.ensureVisible(find.text('Nano')); await tester.tap(find.text('Nano')); await tester.pump();
        expect(tester.widget<PlanChoices>(find.byType(PlanChoices)).selected, 3);
        await tester.ensureVisible(find.text('Hệ điều hành')); await tester.pumpAndSettle();
        await saveCapture(tester, capture, 'os-create-$width-${brightness.name}');
        expect(find.textContaining('Container LXC'), findsNothing);
        expect(find.text('IaaS · Hạ tầng'), findsOneWidget); expect(find.text('PaaS · Nền tảng'), findsOneWidget);
        for (final kind in ['postgres', 'webapp']) {
          final choice = find.widgetWithText(ChoiceChip, serviceName(kind));
          await tester.ensureVisible(choice); await tester.tap(choice); await tester.pump();
          expect(find.byType(OSChoices), findsNothing);
        }
        expect(tester.takeException(), isNull);
      });

      testWidgets('Windows RDP và mật khẩu $width $brightness', (tester) async {
        tester.view.physicalSize = Size(width, 1200); tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
        String? copied;
        tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async { if (call.method == 'Clipboard.setData') copied = (call.arguments as Map)['text'] as String; return null; });
        addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
        final api = ApiClient(client: MockClient((request) async {
          final path = request.url.path;
          if (path.endsWith('/credentials')) return response({'username': 'tbtadmin', 'password': 'FixturePassword123', 'ket_noi': 'rdp', 'dia_chi': 'gateway.test:22000', 'ssh_host': 'gateway.test', 'ssh_port': 22000});
          if (path.endsWith('/detail')) return response({'id': 1, 'ten': 'windows-thu', 'dich_vu': 'vps', 'loai': 'vm', 'trang_thai': 'running', 'ten_he_dieu_hanh': 'Windows 11', 'ket_noi': 'rdp', 'node_ten': 'node-thu', 'vcpu': 2, 'ram_mb': 4096, 'disk_gb': 64, 'ssh_port': 22000, 'gia_theo_gio': 2500});
          if (path.endsWith('/status-now')) return response({'cpu': 0, 'mem': 0});
          return response([]);
        }));
        final state = CloudState(api);
        addTearDown(state.dispose);
        final capture = GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key: capture, child: MaterialApp(theme: cloudTheme(brightness), home: Scaffold(body: DetailScreen(state: state, id: 1)))));
        await tester.pumpAndSettle();
        expect(find.text('Lệnh SSH'), findsNothing);
        final address = find.text('gateway.test:22000');
        await tester.ensureVisible(address); await tester.pump();
        expect(address, findsOneWidget);
        expect(find.text('FixturePassword123'), findsNothing);
        await tester.ensureVisible(find.byTooltip('Hiện mật khẩu')); await tester.tap(find.byTooltip('Hiện mật khẩu')); await tester.pump();
        expect(find.text('FixturePassword123'), findsOneWidget);
        await tester.tap(find.byTooltip('Sao chép mật khẩu')); await tester.pump();
        expect(copied, 'FixturePassword123');
        await tester.tap(find.byTooltip('Ẩn mật khẩu')); await tester.pump();
        expect(find.text('FixturePassword123'), findsNothing);
        await tester.ensureVisible(find.text('Thông tin đăng nhập')); await tester.pumpAndSettle();
        await saveCapture(tester, capture, 'os-rdp-$width-${brightness.name}');
        expect(tester.takeException(), isNull);
      });
    }
  }

  testWidgets('Windows gửi OS và không gửi khóa SSH', (tester) async {
    Json? body;
    final state = CloudState(ApiClient(client: MockClient((request) async { body = Map<String, dynamic>.from(jsonDecode(request.body) as Map); return response({'detail': 'Kiểm thử cấu hình đã nhận.'}, 422); })))..osImages = images..plans = plans..balance = 10000;
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: CreateScreen(state: state))));
    await tester.ensureVisible(find.text('Windows 11')); await tester.tap(find.text('Windows 11')); await tester.pump();
    final submit = find.widgetWithText(FilledButton, 'Tạo dịch vụ');
    await tester.ensureVisible(submit); await tester.tap(submit); await tester.pumpAndSettle();
    expect(body?['os_ma'], 'windows11'); expect(body!.containsKey('cloud_user'), isFalse); expect(body!.containsKey('ten'), isFalse); expect(body?['plan_id'], 3);
    expect(body!.containsKey('ssh_public_key'), isFalse);
  });

  testWidgets('Không có OS sẵn sàng thì không tạo được VM', (tester) async {
    final state = CloudState(ApiClient(client: MockClient((_) async => response([]))))..osImages = [for (final os in images) {...os, 'san_sang': false}]..plans = plans;
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: CreateScreen(state: state))));
    expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Tạo dịch vụ')).onPressed, isNull);
  });

  testWidgets('Bảng giá chỉ công bố OS sẵn sàng', (tester) async {
    final api = ApiClient(client: MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      return response(request.url.path.endsWith('/os') ? images : []);
    }))..token = 'fixture-token';
    await tester.pumpWidget(MaterialApp(home: LandingScreen(api: api)));
    await tester.pumpAndSettle();
    final need = find.byKey(const ValueKey('need-vps')); await tester.ensureVisible(need); await tester.tap(need); await tester.pumpAndSettle();
    expect(find.text('Hệ điều hành hỗ trợ'), findsOneWidget);
    expect(find.text('Windows 11 · RDP'), findsOneWidget);
    expect(find.text('Windows Server 2022 · RDP'), findsNothing);
    expect(find.text('Kali Linux · SSH'), findsNothing);
  });

  test('Gói đủ RAM nhưng thiếu đĩa vẫn bị loại', () {
    expect(osPlanReason({...plans[2], 'disk_gb': 40}, images.last), contains('64 GB'));
    expect(osPlanReason(plans[2], images.last), isNull);
  });
}

Future<void> saveCapture(WidgetTester tester, GlobalKey key, String name) async {
  await tester.runAsync(() async {
    final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final picture = await boundary.toImage();
    final bytes = (await picture.toByteData(format: ui.ImageByteFormat.png))!;
    final file = File('build/surfaces/$name.png');
    await file.parent.create(recursive: true); await file.writeAsBytes(bytes.buffer.asUint8List()); picture.dispose();
  });
}
