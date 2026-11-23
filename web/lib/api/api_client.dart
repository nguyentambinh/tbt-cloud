// Nguyễn Tâm Bình - 2324801030003
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'browser.dart';

typedef Json = Map<String, dynamic>;

class ApiException implements Exception {
  final String message;
  const ApiException(this.message);
  @override
  String toString() => message;
}

class ApiClient {
  final http.Client client;
  String? token = readToken();
  void Function()? onUnauthorized;
  static const base = String.fromEnvironment('API_BASE', defaultValue: '/api/v1');
  ApiClient({http.Client? client}) : client = client ?? http.Client();

  Future<dynamic> request(String path, {String method = 'GET', Object? body, bool authenticated = true, bool binary = false, int timeoutSeconds = 210}) async {
    final uri = Uri.base.resolve('${base.replaceFirst(RegExp(r'/$'), '')}$path');
    final req = http.Request(method, uri)..headers['Accept'] = 'application/json';
    if (authenticated && token != null) req.headers['Authorization'] = 'Bearer $token';
    if (body != null) {
      req.headers['Content-Type'] = 'application/json';
      req.body = jsonEncode(body);
    }
    try {
      final response = await http.Response.fromStream(await client.send(req).timeout(Duration(seconds: timeoutSeconds))).timeout(Duration(seconds: timeoutSeconds));
      if (binary && response.statusCode >= 200 && response.statusCode < 300) return response.bodyBytes;
      dynamic data;
      try { data = jsonDecode(utf8.decode(response.bodyBytes)); } catch (_) { data = null; }
      if (response.statusCode >= 200 && response.statusCode < 300) return data;
      if (response.statusCode == 401 && authenticated && req.headers['Authorization'] == 'Bearer $token') {
        token = null;
        writeToken(null);
        onUnauthorized?.call();
      }
      final detail = data is Map ? data['detail'] : null;
      final safe = detail is String && detail.length < 400 && RegExp(r'[À-ỹ]').hasMatch(detail) && !RegExp(r'(Traceback|https?://|token_secret|password_hash|<[^>]*>)', caseSensitive: false).hasMatch(detail);
      throw ApiException(safe ? detail : switch (response.statusCode) { 401 => 'Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.', 403 => 'Tài khoản chưa có quyền thực hiện thao tác này.', 404 => 'Không tìm thấy dữ liệu cần xem.', 422 => 'Thông tin chưa hợp lệ. Hãy kiểm tra lại các ô nhập.', _ => 'Chưa thể xử lý yêu cầu. Hãy thử lại sau ít phút.' });
    } on ApiException { rethrow; } on TimeoutException { throw const ApiException('Máy chủ phản hồi lâu hơn dự kiến. Hãy tải lại để kiểm tra kết quả trước khi thử lại.'); } catch (_) { throw const ApiException('Chưa kết nối được máy chủ. Hãy kiểm tra mạng và thử lại.'); }
  }

  Future<Json> get(String path) async => Map<String, dynamic>.from(await request(path) as Map);
  Future<List<Json>> list(String path, {bool authenticated = true}) async => (await request(path, authenticated: authenticated) as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
  Future<List<Json>> all(String path) async {
    final result = <Json>[];
    for (var offset = 0; ; offset += 200) {
      final page = await list('$path${path.contains('?') ? '&' : '?'}offset=$offset&limit=200');
      result.addAll(page);
      if (page.length < 200) return result;
    }
  }
  Future<Json> post(String path, [Json? body]) async => Map<String, dynamic>.from(await request(path, method: 'POST', body: body) as Map);
  Uri consoleUri(int id) => Uri.base.replace(scheme: Uri.base.scheme == 'https' ? 'wss' : 'ws', path: '/api/v1/instances/$id/console', queryParameters: {'token': token ?? ''}, fragment: '');
}
