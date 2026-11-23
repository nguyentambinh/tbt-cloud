// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../api/api_client.dart';
import '../api/browser.dart';
import 'common.dart';

class ServiceConnection extends StatefulWidget {
  final ApiClient api;
  final int id;
  final String kind;
  const ServiceConnection({super.key, required this.api, required this.id, required this.kind});
  @override
  State<ServiceConnection> createState() => _ServiceConnectionState();
}

class _ServiceConnectionState extends State<ServiceConnection> {
  Json? service;
  String? error;
  bool hidden = true, loading = true;
  int generation = 0;
  @override
  void initState() { super.initState(); load(); }
  @override
  void didUpdateWidget(ServiceConnection old) { super.didUpdateWidget(old); if (old.id != widget.id || old.api != widget.api) { service = null; hidden = true; load(); } }
  Future<void> load() async {
    final ticket = ++generation;
    setState(() { loading = true; error = null; });
    try {
      final result = await widget.api.get('/instances/${widget.id}/service');
      if (mounted && ticket == generation) setState(() => service = result);
    } catch (e) {
      if (mounted && ticket == generation) setState(() => error = e is ApiException ? e.message : 'Chưa lấy được thông tin kết nối. Hãy thử lại.');
    }
    if (mounted && ticket == generation) setState(() => loading = false);
  }
  @override
  Widget build(BuildContext context) {
    final data = service;
    final connection = data?['connection_string'] as String?;
    final displayed = connection == null ? '' : hidden ? connection.replaceFirst(RegExp(r'(?<=://)[^@]*@'), 'app:••••••••@') : connection;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Kết nối dịch vụ', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12), const Text('Dịch vụ cần ít phút để cấu hình sau khi máy khởi động. Nếu chưa kết nối được, hãy thử lại sau.'), const SizedBox(height: 12), if (loading) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), if (data != null) ...[DescriptionRow('Máy chủ', '${data['host']}', copy: true), DescriptionRow('Cổng', '${data['port']}', copy: true), if (widget.kind == 'webapp' && data['url'] != null) ...[DescriptionRow('URL', '${data['url']}', copy: true), TextButton.icon(onPressed: () => openService('${data['url']}'), icon: const Icon(Icons.open_in_new_outlined), label: const Text('Mở ứng dụng web')), DescriptionRow('Kho Git', '${data['repo_url']}'), DescriptionRow('Nhánh', '${data['branch']}')] else if (connection != null) ...[const SizedBox(height: 12), const Text('Chuỗi kết nối PostgreSQL'), const SizedBox(height: 8), SelectableText(displayed), const SizedBox(height: 8), Wrap(spacing: 12, runSpacing: 8, children: [TextButton.icon(onPressed: () => setState(() => hidden = !hidden), icon: Icon(hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined), label: Text(hidden ? 'Hiện mật khẩu' : 'Ẩn mật khẩu')), OutlinedButton.icon(onPressed: () async { await Clipboard.setData(ClipboardData(text: connection)); if (context.mounted) message(context, 'Đã sao chép chuỗi kết nối.'); }, icon: const Icon(Icons.content_copy_outlined), label: const Text('Sao chép chuỗi kết nối'))])]]]);
  }
}
