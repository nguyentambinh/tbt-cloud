// Nguyễn Tâm Bình - 2324801030003
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tbt_cloud/api/api_client.dart';
import 'package:tbt_cloud/api/cloud_state.dart';
import 'package:tbt_cloud/screens/create_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/ai_advisor.dart';

http.Response response(dynamic data, [int status = 200]) => http.Response(jsonEncode(data), status, headers: {'content-type': 'application/json'});
final suggestions = {'tom_tat': 'Chuỗi cửa hàng cần quản lý đơn hàng tập trung', 'goi_y': [
  {'dich_vu': 'vps', 'ten_dich_vu': 'Máy chủ ảo VPS', 'plan_id': 2, 'ten_goi': 'Vừa', 'vcpu': 2, 'ram_mb': 2048, 'disk_gb': 20, 'gpu': 0, 'gia_theo_gio': '800', 'os_ma': 'ubuntu2404', 'ten_he_dieu_hanh': 'Ubuntu 24.04 LTS', 'ly_do': 'Đủ chạy phần mềm bán hàng cho 3 chi nhánh.'},
  {'dich_vu': 'postgres', 'ten_dich_vu': 'Cơ sở dữ liệu PostgreSQL', 'plan_id': 5, 'ten_goi': 'Postgres Nhỏ', 'vcpu': 1, 'ram_mb': 1024, 'disk_gb': 10, 'gpu': 0, 'gia_theo_gio': '400', 'os_ma': null, 'ten_he_dieu_hanh': null, 'ly_do': 'Lưu đơn hàng tập trung.'},
]};
final images = <Json>[{'ma': 'debian13', 'ten': 'Debian 13', 'ho': 'linux', 'min_ram_mb': 512, 'min_disk_gb': 10, 'ket_noi': 'ssh', 'san_sang': true, 'chi_gpu': false}, {'ma': 'ubuntu2404', 'ten': 'Ubuntu 24.04 LTS', 'ho': 'linux', 'min_ram_mb': 1024, 'min_disk_gb': 10, 'ket_noi': 'ssh', 'san_sang': true, 'chi_gpu': false}];
final plans = <Json>[{'id': 1, 'ten': 'Nhỏ', 'dich_vu': 'vps', 'vcpu': 1, 'ram_mb': 1024, 'disk_gb': 10, 'gia_theo_gio': '500', 'gpu': 0}, {'id': 2, 'ten': 'Vừa', 'dich_vu': 'vps', 'vcpu': 2, 'ram_mb': 2048, 'disk_gb': 20, 'gia_theo_gio': '800', 'gpu': 0}, {'id': 5, 'ten': 'Postgres Nhỏ', 'dich_vu': 'postgres', 'vcpu': 1, 'ram_mb': 1024, 'disk_gb': 10, 'gia_theo_gio': '400', 'gpu': 0}];

void main() {
  testWidgets('AI gợi ý: gửi mô tả và tệp, hiện cái tốt nhất, xem thêm, tạo đúng cấu hình', (tester) async {
    tester.view.physicalSize = const Size(1440, 2600); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    Json? asked, created;
    final api = ApiClient(client: MockClient((request) async {
      if (request.url.path.endsWith('/ai/goi-y')) { asked = jsonDecode(request.body) as Json; return response(suggestions); }
      if (request.url.path.endsWith('/instances') && request.method == 'POST') { created = jsonDecode(request.body) as Json; return response({'id': 31, 'ten': 'khach1-4'}, 201); }
      return response([]);
    }))..token = 'token';
    final state = CloudState(api)..osImages = images..plans = plans..balance = 100000..user = {'id': 7, 'role': 'user'};
    addTearDown(state.dispose);
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: Scaffold(body: CreateScreen(state: state))));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('ai-need')), 'Ba chi nhánh ghi đơn bằng sổ tay, cuối ngày cộng sổ lệch');
    await tester.tap(find.byKey(const ValueKey('ai-ask'))); await tester.pumpAndSettle();
    expect(asked, {'mo_ta': 'Ba chi nhánh ghi đơn bằng sổ tay, cuối ngày cộng sổ lệch'});
    expect(find.text('PHÙ HỢP NHẤT'), findsOneWidget);
    expect(find.text('Lưu đơn hàng tập trung.'), findsNothing);
    await tester.tap(find.byKey(const ValueKey('ai-more'))); await tester.pumpAndSettle();
    expect(find.text('Lưu đơn hàng tập trung.'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('ai-create-2-ubuntu2404'))); await tester.pump(); await tester.pump(const Duration(seconds: 2));
    expect(created?['plan_id'], 2); expect(created?['os_ma'], 'ubuntu2404'); expect(created?['dich_vu'], 'vps');
  });

  testWidgets('đính kèm tệp gửi base64 và tên tệp', (tester) async {
    Json? asked;
    final api = ApiClient(client: MockClient((request) async { asked = jsonDecode(request.body) as Json; return response(suggestions); }))..token = 'token';
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: AiAdvisor(api: api, onCreate: (_) {}, onChoose: (_) {}, picker: () async => ('nhu_cau.pdf', utf8.encode('%PDF-1.4')))))));
    await tester.tap(find.byKey(const ValueKey('ai-attach'))); await tester.pumpAndSettle();
    expect(find.text('nhu_cau.pdf'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('ai-ask'))); await tester.pumpAndSettle();
    expect(asked?['tep_ten'], 'nhu_cau.pdf'); expect(base64Decode('${asked?['tep_base64']}'), utf8.encode('%PDF-1.4'));
    expect(tester.takeException(), isNull);
  });
}
