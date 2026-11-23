// Nguyễn Tâm Bình - 2324801030003
// ignore_for_file: deprecated_member_use, avoid_web_libraries_in_flutter
import 'dart:html' as html;

String? readToken() => html.window.localStorage['tbt_cloud_jwt'];
void writeToken(String? token) {
  if (token == null) {
    html.window.localStorage.remove('tbt_cloud_jwt');
  } else {
    html.window.localStorage['tbt_cloud_jwt'] = token;
  }
}
String? readPref(String key) { try { return html.window.localStorage['tbt_$key']; } catch (_) { return null; } }
void writePref(String key, String value) { try { html.window.localStorage['tbt_$key'] = value; } catch (_) {} }
void openCheckout(String url) {
  final uri = Uri.tryParse(url);
  if (uri?.scheme == 'https' && (uri!.host == 'pay.payos.vn' || uri.host.endsWith('.payos.vn'))) {
    html.window.location.assign(url);
  }
}

void openService(String url) {
  final uri = Uri.tryParse(url);
  if (uri != null && ['http', 'https'].contains(uri.scheme) && uri.host.isNotEmpty && uri.userInfo.isEmpty) {
    html.window.open(url, '_blank', 'noopener,noreferrer');
  }
}

void saveDownload(List<int> bytes, String name) {
  final url = html.Url.createObjectUrlFromBlob(html.Blob([bytes]));
  final anchor = html.AnchorElement(href: url)..download = name;
  html.document.body?.append(anchor); anchor.click(); anchor.remove();
  Future.delayed(const Duration(seconds: 30), () => html.Url.revokeObjectUrl(url));
}
