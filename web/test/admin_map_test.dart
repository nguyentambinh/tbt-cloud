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
import 'package:tbt_cloud/screens/admin_map.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';

http.Response response(dynamic data) => http.Response(jsonEncode(data), 200, headers: {'content-type': 'application/json'});

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    for (final font in [('Barlow Condensed', 'BarlowCondensed-SemiBold.ttf'), ('Be Vietnam Pro', 'BeVietnamPro-Regular.ttf'), ('Roboto', 'BeVietnamPro-Regular.ttf')]) {
      await (FontLoader(font.$1)..addFont(rootBundle.load('assets/fonts/${font.$2}'))).load();
    }
  });

  testWidgets('dịch vụ của khách thẳng hàng tiêu đề, 6 mục mỗi trang', (tester) async {
    tester.view.physicalSize = const Size(1440, 1400); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    final services = [for (var i = 1; i <= 8; i++) {'id': i, 'ten': 'dich-vu-$i', 'user_id': 7, 'node_id': 1, 'dich_vu': i.isEven ? 'postgres' : 'vps', 'trang_thai': i < 3 ? 'running' : 'deleted'}];
    final api = ApiClient(client: MockClient((request) async {
      if (request.url.path.endsWith('/admin/map')) return response({'nodes': [{'id': 1, 'ten': 'ASUS', 'proxmox_node': 'pve-asus', 'online': true, 'total_vcpu': 16, 'used_vcpu': 2, 'total_ram_mb': 16000, 'used_ram_mb': 2000, 'total_disk_gb': 90, 'used_disk_gb': 20}], 'items': [services.first], 'total': 1});
      if (request.url.path.endsWith('/admin/users/7')) return response({'id': 7, 'ho_ten': 'Nguyễn An', 'username': 'nguyen.an', 'email': 'an@example.test', 'created_at': '2026-11-20T00:00:00Z', 'balance': 250000, 'instances': {'items': services, 'total': 8}});
      return response([]);
    }))..token = 'token';
    final key = GlobalKey();
    await tester.pumpWidget(RepaintBoundary(key: key, child: MaterialApp(theme: cloudTheme(Brightness.dark), home: Scaffold(body: SingleChildScrollView(padding: const EdgeInsets.all(40), child: AdminMap(api: api))))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('dich-vu-1').first); await tester.pumpAndSettle();
    expect(find.text('dich-vu-6'), findsOneWidget);
    expect(find.text('dich-vu-7'), findsNothing);
    expect(find.text('1 - 6 / 8'), findsOneWidget);
    final heading = tester.getTopLeft(find.text('Dịch vụ của khách hàng')).dx;
    expect(tester.getTopLeft(find.text('dich-vu-3')).dx, closeTo(heading, 1));
    final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    await tester.runAsync(() async { final image = await boundary.toImage(); final bytes = (await image.toByteData(format: ui.ImageByteFormat.png))!.buffer.asUint8List(); await File('build/surfaces/admin/map-owner-trang-1440.png').writeAsBytes(bytes); image.dispose(); });
    await tester.ensureVisible(find.byKey(const ValueKey('owner-next'))); await tester.tap(find.byKey(const ValueKey('owner-next'))); await tester.pumpAndSettle();
    expect(find.text('dich-vu-7'), findsOneWidget);
    expect(find.text('dich-vu-3'), findsNothing);
    expect(find.text('7 - 8 / 8'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
