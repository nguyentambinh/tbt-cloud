// Nguyễn Tâm Bình - 2324801030003
import 'dart:convert';

class QrCode {
  static const _ecc = [0,10,16,26,18,24,16,18,22,22,26,30,22,22,24,24,28,28,26,26,26,26,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28];
  static const _blocks = [0,1,1,1,2,2,4,4,4,5,5,5,8,9,9,10,10,11,13,14,16,17,17,18,20,21,23,25,26,28,29,31,33,35,37,38,40,43,45,47,49];
  final int version;
  late final int size = version * 4 + 17;
  late final List<List<bool>> modules = List.generate(size, (_) => List.filled(size, false));
  late final List<List<bool>> _function = List.generate(size, (_) => List.filled(size, false));
  late final List<int> dataCodewords;
  late final List<int> codewords;
  late final int mask;

  factory QrCode.encode(String text, {int? mask, int? minVersion}) {
    final bytes = utf8.encode(text);
    for (var v = minVersion ?? 1; v <= 40; v++) {
      if (v < 1 || bytes.length >= 1 << (v < 10 ? 8 : 16)) continue;
      if (4 + (v < 10 ? 8 : 16) + bytes.length * 8 <= _capacity(v) * 8) return QrCode._(v, bytes, mask);
    }
    throw const FormatException('Nội dung quá dài để tạo mã QR. Hãy mở trang thanh toán.');
  }
  QrCode._(this.version, List<int> bytes, int? chosenMask) {
    if (chosenMask != null && (chosenMask < 0 || chosenMask > 7)) throw ArgumentError.value(chosenMask);
    final bits = <bool>[];
    void append(int value, int count) { for (var i = count - 1; i >= 0; i--) { bits.add((value >> i) & 1 != 0); } }
    append(4, 4); append(bytes.length, version < 10 ? 8 : 16);
    for (final b in bytes) { append(b, 8); }
    final capacity = _capacity(version) * 8;
    append(0, (capacity - bits.length).clamp(0, 4));
    while (bits.length % 8 != 0) { bits.add(false); }
    dataCodewords = [for (var i = 0; i < bits.length; i += 8) List.generate(8, (j) => bits[i + j] ? 1 << (7 - j) : 0).fold(0, (a, b) => a | b)];
    for (var pad = 0; dataCodewords.length < capacity ~/ 8; pad++) { dataCodewords.add(pad.isEven ? 0xEC : 0x11); }
    codewords = _interleave(dataCodewords);
    _drawFunctions();
    _drawData();
    var best = 1 << 30, bestMask = 0;
    for (var m = 0; m < 8; m++) {
      if (chosenMask != null && chosenMask != m) continue;
      _applyMask(m); _format(m);
      final score = _penalty();
      if (score < best) { best = score; bestMask = m; }
      _applyMask(m);
    }
    mask = bestMask; _applyMask(mask); _format(mask);
  }
  static int _raw(int v) {
    var count = (16 * v + 128) * v + 64;
    if (v >= 2) { final n = v ~/ 7 + 2; count -= (25 * n - 10) * n - 55; if (v >= 7) count -= 36; }
    return count;
  }
  static int _capacity(int v) => _raw(v) ~/ 8 - _ecc[v] * _blocks[v];
  static int multiply(int x, int y) {
    var z = 0;
    for (var i = 7; i >= 0; i--) { z = (z << 1) ^ ((z >> 7) * 0x11D); z ^= ((y >> i) & 1) * x; }
    return z;
  }
  static List<int> reedSolomon(List<int> data, int degree) {
    final divisor = List.filled(degree, 0)..[degree - 1] = 1;
    var root = 1;
    for (var i = 0; i < degree; i++) {
      for (var j = 0; j < degree; j++) { divisor[j] = multiply(divisor[j], root); if (j + 1 < degree) divisor[j] ^= divisor[j + 1]; }
      root = multiply(root, 2);
    }
    final result = List.filled(degree, 0);
    for (final b in data) {
      final factor = b ^ result[0];
      for (var i = 0; i < degree - 1; i++) { result[i] = result[i + 1]; }
      result[degree - 1] = 0;
      for (var i = 0; i < degree; i++) { result[i] ^= multiply(divisor[i], factor); }
    }
    return result;
  }
  List<int> _interleave(List<int> data) {
    final count = _blocks[version], ec = _ecc[version], raw = _raw(version) ~/ 8;
    final shortLength = raw ~/ count, shortCount = count - raw % count;
    final blocks = <List<int>>[];
    var offset = 0;
    for (var i = 0; i < count; i++) {
      final length = shortLength - ec + (i < shortCount ? 0 : 1);
      final block = data.sublist(offset, offset + length);
      offset += length;
      final remainder = reedSolomon(block, ec);
      if (i < shortCount) block.add(0);
      blocks.add([...block, ...remainder]);
    }
    return [for (var i = 0; i < blocks[0].length; i++) for (var j = 0; j < count; j++) if (i != shortLength - ec || j >= shortCount) blocks[j][i]];
  }
  void _set(int x, int y, bool value) { modules[y][x] = value; _function[y][x] = true; }
  void _drawFunctions() {
    for (var i = 0; i < size; i++) { _set(6, i, i.isEven); _set(i, 6, i.isEven); }
    for (final center in [(3,3), (size - 4,3), (3,size - 4)]) {
      for (var dy = -4; dy <= 4; dy++) {
        for (var dx = -4; dx <= 4; dx++) {
          final x = center.$1 + dx, y = center.$2 + dy;
          final distance = dx.abs() > dy.abs() ? dx.abs() : dy.abs();
          if (x >= 0 && y >= 0 && x < size && y < size) _set(x, y, distance != 2 && distance != 4);
        }
      }
    }
    if (version > 1) {
      final count = version ~/ 7 + 2;
      final step = version == 32 ? 26 : (version * 4 + count * 2 + 1) ~/ (count * 2 - 2) * 2;
      final positions = [6, for (var i = count - 2; i >= 0; i--) size - 7 - i * step];
      for (var i = 0; i < count; i++) {
        for (var j = 0; j < count; j++) {
          if ((i == 0 && j == 0) || (i == 0 && j == count - 1) || (i == count - 1 && j == 0)) continue;
          for (var dy = -2; dy <= 2; dy++) { for (var dx = -2; dx <= 2; dx++) { _set(positions[i] + dx, positions[j] + dy, dx.abs() != 1 && dy.abs() != 1 || dx.abs() == 2 || dy.abs() == 2); } }
        }
      }
    }
    _format(0);
    if (version >= 7) {
      var remainder = version;
      for (var i = 0; i < 12; i++) { remainder = (remainder << 1) ^ ((remainder >> 11) * 0x1F25); }
      final bits = version << 12 | remainder;
      for (var i = 0; i < 18; i++) { final a = size - 11 + i % 3, b = i ~/ 3; _set(a, b, (bits >> i) & 1 != 0); _set(b, a, (bits >> i) & 1 != 0); }
    }
  }
  void _format(int m) {
    var remainder = m;
    for (var i = 0; i < 10; i++) { remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537); }
    final bits = ((m << 10) | remainder) ^ 0x5412;
    bool bit(int i) => (bits >> i) & 1 != 0;
    for (var i = 0; i <= 5; i++) { _set(8, i, bit(i)); }
    _set(8, 7, bit(6)); _set(8, 8, bit(7)); _set(7, 8, bit(8));
    for (var i = 9; i < 15; i++) { _set(14 - i, 8, bit(i)); }
    for (var i = 0; i < 8; i++) { _set(size - 1 - i, 8, bit(i)); }
    for (var i = 8; i < 15; i++) { _set(8, size - 15 + i, bit(i)); }
    _set(8, size - 8, true);
  }
  void _drawData() {
    var i = 0;
    for (var right = size - 1; right >= 1; right -= 2) {
      if (right == 6) right = 5;
      for (var vertical = 0; vertical < size; vertical++) {
        final y = ((right + 1) & 2) == 0 ? size - 1 - vertical : vertical;
        for (var j = 0; j < 2; j++) {
          final x = right - j;
          if (!_function[y][x] && i < codewords.length * 8) { modules[y][x] = (codewords[i >> 3] >> (7 - (i & 7))) & 1 != 0; i++; }
        }
      }
    }
  }
  void _applyMask(int m) {
    for (var y = 0; y < size; y++) { for (var x = 0; x < size; x++) {
      final invert = switch (m) { 0 => (x + y) % 2 == 0, 1 => y % 2 == 0, 2 => x % 3 == 0, 3 => (x + y) % 3 == 0, 4 => (x ~/ 3 + y ~/ 2) % 2 == 0, 5 => x * y % 2 + x * y % 3 == 0, 6 => (x * y % 2 + x * y % 3) % 2 == 0, _ => ((x + y) % 2 + x * y % 3) % 2 == 0 };
      if (!_function[y][x] && invert) modules[y][x] = !modules[y][x];
    } }
  }
  int _penalty() {
    var score = 0, dark = 0;
    for (var axis = 0; axis < 2; axis++) {
      for (var a = 0; a < size; a++) {
        var run = 0; bool? last;
        final line = <bool>[...List.filled(4, false), for (var b = 0; b < size; b++) axis == 0 ? modules[a][b] : modules[b][a], ...List.filled(4, false)];
        for (var b = 0; b < size; b++) {
          final color = line[b + 4];
          if (color == last) { run++; if (run == 5) score += 3; if (run > 5) score++; } else { last = color; run = 1; }
        }
        for (var i = 0; i + 10 < line.length; i++) {
          final pattern = line.sublist(i, i + 11).map((v) => v ? '1' : '0').join();
          if (pattern == '00001011101' || pattern == '10111010000') score += 40;
        }
      }
    }
    for (var y = 0; y < size; y++) { for (var x = 0; x < size; x++) {
      if (modules[y][x]) dark++;
      if (x + 1 < size && y + 1 < size && modules[y][x] == modules[y][x + 1] && modules[y][x] == modules[y + 1][x] && modules[y][x] == modules[y + 1][x + 1]) score += 3;
    } }
    return score + ((dark * 20 - size * size * 10).abs() ~/ (size * size)) * 10;
  }
}
