// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'qr_code.dart';

class QrView extends StatelessWidget {
  final String data;
  const QrView(this.data, {super.key});
  @override
  Widget build(BuildContext context) {
    try {
      final qr = QrCode.encode(data);
      return Semantics(label: 'Mã QR chuyển khoản ngân hàng. Có thể dùng nút mở payOS thay cho quét mã.', image: true, child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 300), child: AspectRatio(aspectRatio: 1, child: CustomPaint(painter: _QrPainter(qr)))));
    } on FormatException catch (e) { return Text(e.message); }
  }
}
class _QrPainter extends CustomPainter {
  final QrCode qr;
  _QrPainter(this.qr);
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = Colors.white);
    final cell = (size.shortestSide / (qr.size + 8)).floorToDouble();
    final origin = (size.shortestSide - cell * qr.size) / 2;
    final ink = Paint()..color = Colors.black..isAntiAlias = false;
    for (var y = 0; y < qr.size; y++) { for (var x = 0; x < qr.size; x++) { if (qr.modules[y][x]) canvas.drawRect(Rect.fromLTWH(origin + x * cell, origin + y * cell, cell, cell), ink); } }
  }
  @override
  bool shouldRepaint(_QrPainter old) => old.qr != qr;
}
