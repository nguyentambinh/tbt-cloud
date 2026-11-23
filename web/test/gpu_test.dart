// Nguyễn Tâm Bình - 2324801030003
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tbt_cloud/api/api_client.dart';
import 'package:tbt_cloud/api/cloud_state.dart';
import 'package:tbt_cloud/screens/create_screen.dart';
import 'package:tbt_cloud/screens/landing_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/common.dart';
import 'package:tbt_cloud/widgets/os_choices.dart';

http.Response response(dynamic data, [int status = 200]) => http.Response(jsonEncode(data), status, headers: {'content-type': 'application/json'});
final images = <Json>[
  {'ma': 'debian13', 'ten': 'Debian 13', 'ho': 'linux', 'min_ram_mb': 512, 'min_disk_gb': 10, 'ket_noi': 'ssh', 'san_sang': true, 'chi_gpu': false},
  {'ma': 'ubuntu2404ai', 'ten': 'Ubuntu 24.04 + CUDA + PyTorch', 'ho': 'linux', 'min_ram_mb': 8192, 'min_disk_gb': 30, 'ket_noi': 'ssh', 'san_sang': true, 'chi_gpu': true},
];
final plans = <Json>[
  {'id': 1, 'ten': 'Nano', 'dich_vu': 'vps', 'vcpu': 1, 'ram_mb': 512, 'disk_gb': 10, 'gia_theo_gio': '300', 'gpu': 0},
  {'id': 9, 'ten': 'AI Tiêu chuẩn', 'dich_vu': 'vps', 'vcpu': 6, 'ram_mb': 16384, 'disk_gb': 40, 'gia_theo_gio': '9000', 'gpu': 1, 'mo_ta': 'Huấn luyện mô hình vừa'},
];

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    for (final font in [('Barlow Condensed', 'BarlowCondensed-SemiBold.ttf'), ('Be Vietnam Pro', 'BeVietnamPro-Regular.ttf'), ('Roboto', 'BeVietnamPro-Regular.ttf')]) {
      await (FontLoader(font.$1)..addFont(rootBundle.load('assets/fonts/${font.$2}'))).load();
    }
  });

  test('gói GPU tách khỏi VPS thường', () {
    expect(plansForService(plans, 'vps').map((p) => p['id']), [1]);
    expect(plansForService(plans, 'ai').map((p) => p['id']), [9]);
    expect(serviceName('ai'), 'Máy chủ AI (GPU)');
  });

  for (final free in [1, 0]) {
    testWidgets('tạo máy AI khi GPU rảnh $free', (tester) async {
      tester.view.physicalSize = const Size(1440, 2000); tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
      Json? sent;
      final api = ApiClient(client: MockClient((request) async { if (request.method == 'POST') { sent = jsonDecode(request.body) as Json; return response({'id': 5, 'ten': 'ai-1', 'node_id': 2, 'trang_thai': 'running'}, 201); } return response([]); }));
      api.token = 'token';
      final state = CloudState(api)..osImages = images..plans = plans..balance = 100000..gpu = {'tong': 1, 'ranh': free, 'loai': ['NVIDIA GeForce RTX 5060 8 GB']};
      addTearDown(state.dispose);
      await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.dark), home: Scaffold(body: CreateScreen(state: state))));
      await tester.pumpAndSettle();
      expect(find.text('Ubuntu 24.04 + CUDA + PyTorch'), findsNothing);
      await tester.tap(find.byKey(const ValueKey('service-ai'))); await tester.pumpAndSettle();
      expect(find.byType(OSChoices), findsNothing);
      expect(tester.widget<PlanChoices>(find.byType(PlanChoices)).plans.map((p) => p['id']), [9]);
      expect(find.textContaining('NVIDIA GeForce RTX 5060 8 GB · còn rảnh $free/1'), findsOneWidget);
      final button = find.widgetWithText(FilledButton, 'Tạo dịch vụ');
      expect(tester.widget<FilledButton>(button).onPressed == null, free == 0);
      if (free == 1) {
        await tester.ensureVisible(button); await tester.tap(button); await tester.pump(); await tester.pump(const Duration(seconds: 2));
        expect(sent?['dich_vu'], 'vps'); expect(sent?['loai'], 'vm'); expect(sent?['os_ma'], 'ubuntu2404ai'); expect(sent?['plan_id'], 9); expect(sent!.keys.toSet().intersection({'ten', 'cloud_user', 'ssh_public_key'}), isEmpty);
      } else {
        expect(find.text('GPU đang được dùng hết, vui lòng thử lại sau.'), findsOneWidget);
      }
    });
  }

  testWidgets('trang chủ có nhu cầu máy chủ AI', (tester) async {
    tester.view.physicalSize = const Size(1440, 2400); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    final api = ApiClient(client: MockClient((request) async => request.url.path.endsWith('/plans') ? response(plans) : request.url.path.endsWith('/os') ? response(images) : request.url.path.endsWith('/public/gpu') ? response({'tong': 1, 'ranh': 1, 'loai': ['NVIDIA GeForce RTX 5060 8 GB']}) : response([])));
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: LandingScreen(api: api)));
    await tester.pumpAndSettle();
    expect(find.text('AI Tiêu chuẩn'), findsNothing);
    await tester.tap(find.byKey(const ValueKey('need-ai'))); await tester.pumpAndSettle();
    expect(find.text('AI Tiêu chuẩn'), findsOneWidget);
    expect(find.text('Nano'), findsNothing);
    expect(find.textContaining('còn rảnh 1/1'), findsOneWidget);
  });
}
