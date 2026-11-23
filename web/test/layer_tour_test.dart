// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tbt_cloud/theme/cloud_theme.dart';
import 'package:tbt_cloud/widgets/layer_tour.dart';

const layers = [TourLayer('Máy cá nhân', 'Tầng một', 'Nội dung một', ['a']), TourLayer('Mạng kết nối', 'Tầng hai', 'Nội dung hai', ['b']), TourLayer('IaaS', 'Tầng ba', 'Nội dung ba', ['c'])];

Widget page() => MaterialApp(theme: cloudTheme(Brightness.light), home: Scaffold(body: SingleChildScrollView(child: Column(children: [const SizedBox(height: 200), const LayerTour(layers: layers), const SizedBox(height: 1200)]))));

void main() {
  testWidgets('lăn chuột trong khung chuyển tầng, hết tầng thì trang cuộn', (tester) async {
    tester.view.physicalSize = const Size(1440, 900); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(page()); await tester.pumpAndSettle();
    final scroll = tester.state<ScrollableState>(find.byType(Scrollable).first).position;
    final center = tester.getCenter(find.byType(LayerTour));
    final mouse = TestPointer(1, PointerDeviceKind.mouse);
    var stamp = 0;
    for (final expected in ['Tầng hai', 'Tầng ba']) {
      await tester.sendEventToBinding(mouse.hover(center));
      stamp += 1000;
      await tester.sendEventToBinding(mouse.scroll(const Offset(0, 120), timeStamp: Duration(milliseconds: stamp)));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));
      expect(find.text(expected), findsOneWidget);
      expect(scroll.pixels, 0);
    }
    await tester.sendEventToBinding(mouse.scroll(const Offset(0, 120), timeStamp: Duration(milliseconds: stamp + 1000)));
    await tester.pumpAndSettle();
    expect(scroll.pixels, greaterThan(0));
  });

  testWidgets('điện thoại dùng nút Tiếp và Trước', (tester) async {
    tester.view.physicalSize = const Size(390, 1400); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(page()); await tester.pumpAndSettle();
    expect(find.text('Tầng một'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('tour-next')).first); await tester.pumpAndSettle();
    expect(find.text('Tầng hai'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('tour-prev')).first); await tester.pumpAndSettle();
    expect(find.text('Tầng một'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
