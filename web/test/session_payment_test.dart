// Nguyễn Tâm Bình - 2324801030003
import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tbt_cloud/api/api_client.dart';
import 'package:tbt_cloud/api/cloud_state.dart';
import 'package:tbt_cloud/qr/qr_view.dart';
import 'package:tbt_cloud/screens/wallet_screen.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';

http.Response jsonResponse(dynamic body, [int status = 200]) => http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

void main() {
  test('Ví admin chỉ quy đổi thời gian từ máy thuộc tài khoản hiện tại', () {
    final state = CloudState(ApiClient(client: MockClient((_) async => jsonResponse([]))))..user = {'id': 1, 'role': 'admin'}..balance = 99500..instances = [{'id': 1, 'user_id': 1, 'trang_thai': 'running', 'gia_theo_gio': '500'}, {'id': 2, 'user_id': 2, 'trang_thai': 'running', 'gia_theo_gio': '10000'}, {'id': 3, 'user_id': 1, 'trang_thai': 'stopped', 'gia_theo_gio': '1000'}];
    expect(state.myInstances.map((v) => v['id']), [1, 3]);
    expect(state.hourly, 500);
    expect(state.hours, 199);
    expect(state.instances.length, 3);
    state.dispose();
  });
  test('Phản hồi 401 của token cũ không đăng xuất phiên mới', () async {
    final response = Completer<http.Response>();
    final api = ApiClient(client: MockClient((_) => response.future))..token = 'old-token';
    var expired = 0;
    api.onUnauthorized = () => expired++;
    final request = api.get('/auth/me');
    final result = expectLater(request, throwsA(isA<ApiException>()));
    api.token = 'new-token';
    response.complete(jsonResponse({'detail': 'Phiên đăng nhập đã hết hạn.'}, 401));
    await result;
    expect(api.token, 'new-token');
    expect(expired, 0);
  });
  test('Phản hồi 401 của phiên hiện tại xóa token và yêu cầu đăng nhập', () async {
    final api = ApiClient(client: MockClient((_) async => jsonResponse({}, 401)))..token = 'current-token';
    var expired = 0;
    api.onUnauthorized = () => expired++;
    await expectLater(api.get('/auth/me'), throwsA(isA<ApiException>()));
    expect(api.token, isNull);
    expect(expired, 1);
  });
  test('Kết quả tải phiên cũ không khôi phục dữ liệu sau đăng xuất', () async {
    final response = Completer<http.Response>();
    final state = CloudState(ApiClient(client: MockClient((_) => response.future))..token = 'test-token');
    final loading = state.refresh();
    state.logout();
    response.complete(jsonResponse({'id': 1, 'role': 'user'}));
    await loading;
    expect(state.user, isNull);
    expect(state.instances, isEmpty);
    expect(state.loading, isFalse);
    state.dispose();
  });
  testWidgets('QR giữ vùng trắng và nằm gọn trong khung điện thoại hẹp', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: Center(child: SizedBox(width: 232, child: QrView('TBT Cloud'))))));
    expect(tester.getSize(find.descendant(of: find.byType(QrView), matching: find.byType(CustomPaint))), const Size(232, 232));
    expect(tester.takeException(), isNull);
  });
  testWidgets('Phản hồi pending đến muộn không ghi đè đơn vừa hủy', (tester) async {
    tester.view.physicalSize = const Size(1440, 1200); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    final delayed = Completer<http.Response>();
    var polls = 0;
    final pending = {'order_code': 123, 'amount': 50000, 'status': 'pending', 'qr_code': 'TBT Cloud', 'checkout_url': 'https://pay.payos.vn/web/test'};
    final api = ApiClient(client: MockClient((request) async {
      final path = request.url.path;
      if (path.endsWith('/cancel')) return jsonResponse({...pending, 'status': 'cancelled'});
      if (path.endsWith('/payos/123')) { polls++; return polls == 1 ? jsonResponse(pending) : await delayed.future; }
      if (path.endsWith('/auth/me')) return jsonResponse({'id': 1, 'role': 'user'});
      if (path.endsWith('/balance')) return jsonResponse({'balance': '50000'});
      return jsonResponse([]);
    }))..token = 'test-token';
    final state = CloudState(api)..user = {'id': 1, 'role': 'user'}..balance = 50000;
    await tester.pumpWidget(MaterialApp(theme: cloudTheme(Brightness.light), home: Scaffold(body: WalletScreen(state: state, orderCode: '123'))));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(seconds: 3));
    expect(polls, 2);
    await tester.ensureVisible(find.text('Hủy đơn'));
    await tester.tap(find.text('Hủy đơn'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Hủy đơn nạp'));
    await tester.pumpAndSettle();
    expect(find.text('Đã hủy'), findsOneWidget);
    delayed.complete(jsonResponse(pending));
    await tester.pumpAndSettle();
    expect(find.text('Đã hủy'), findsOneWidget);
    expect(find.text('Chờ thanh toán'), findsNothing);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });
}
