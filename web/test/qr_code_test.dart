// Nguyễn Tâm Bình - 2324801030003
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:tbt_cloud/qr/qr_code.dart';

void main() {
  final vectors = jsonDecode(File('test/fixtures/qr_m_vectors.json').readAsStringSync()) as List;
  for (final v in vectors) {
    test('Byte / M / phiên bản ${v['version']} / mặt nạ ${v['mask']} khớp vector độc lập', () {
      final qr = QrCode.encode(v['text'] as String, mask: v['mask'] as int, minVersion: v['version'] as int);
      expect(qr.version, v['version']);
      expect(qr.codewords, v['codewords']);
      expect(qr.modules.map((row) => row.map((b) => b ? '1' : '0').join()).toList(), v['rows']);
    });
  }
  test('Tự chọn phiên bản nhỏ nhất và chuyển độ dài byte ở phiên bản 10', () {
    expect(QrCode.encode('a' * 14).version, 1);
    expect(QrCode.encode('a' * 15).version, 2);
    expect(QrCode.encode('a' * 180).version, 9);
    expect(QrCode.encode('a' * 181).version, 10);
    expect(QrCode.encode('a' * 2331).version, 40);
    expect(() => QrCode.encode('a' * 2332), throwsFormatException);
  });
  test('UTF-8 dùng số byte và các byte đúng trong trường dữ liệu', () {
    final qr = QrCode.encode('Việt');
    expect(qr.dataCodewords.take(7).toList(), [0x40, 0x65, 0x66, 0x9E, 0x1B, 0xB8, 0x77]);
  });
  test('Reed Solomon vector 16 byte dữ liệu, 10 byte sửa lỗi', () {
    final qr = QrCode.encode('HELLO WORLD', mask: 0);
    expect(qr.dataCodewords, [64, 180, 132, 84, 196, 196, 242, 5, 116, 245, 36, 196, 64, 236, 17, 236]);
    expect(qr.codewords.sublist(16), vectors.first['codewords'].sublist(16));
  });
  test('Tự chọn mặt nạ hợp lệ, không thay đổi các vùng chức năng', () {
    final qr = QrCode.encode('TBT Cloud');
    expect(qr.mask, inInclusiveRange(0, 7));
    expect(qr.modules[0].take(7), [true, true, true, true, true, true, true]);
    expect(qr.modules[qr.size - 8][8], true);
  });
}
