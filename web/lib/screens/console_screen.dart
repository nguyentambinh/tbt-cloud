// Nguyễn Tâm Bình - 2324801030003
import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:xterm/xterm.dart';
import '../api/cloud_state.dart';
import '../theme/cloud_theme.dart';

class ConsoleScreen extends StatefulWidget {
  final CloudState state;
  final int id;
  const ConsoleScreen({super.key, required this.state, required this.id});
  @override
  State<ConsoleScreen> createState() => _ConsoleScreenState();
}
class _ConsoleScreenState extends State<ConsoleScreen> {
  final terminal = Terminal(maxLines: 5000);
  WebSocketChannel? socket;
  StreamSubscription<dynamic>? subscription;
  bool connected = false, connecting = false;
  String status = 'Đang kết nối console…';
  int generation = 0;
  @override
  void initState() {
    super.initState();
    terminal.onOutput = (data) { if (connected) socket?.sink.add('0:${utf8.encode(data).length}:$data'); };
    terminal.onResize = (cols, rows, pixelWidth, pixelHeight) { if (connected) socket?.sink.add('1:$cols:$rows:'); };
    connect();
  }
  Future<void> connect() async {
    final ticket = ++generation;
    setState(() { connecting = true; connected = false; status = 'Đang kết nối console…'; });
    try {
      await subscription?.cancel(); await socket?.sink.close();
      if (!mounted || ticket != generation) return;
      final next = WebSocketChannel.connect(widget.state.api.consoleUri(widget.id));
      socket = next;
      subscription = next.stream.listen((data) { if (mounted && ticket == generation) terminal.write(data is String ? data : utf8.decode(data as List<int>, allowMalformed: true)); }, onError: (_) => lost(ticket), onDone: () => lost(ticket), cancelOnError: true);
      await next.ready.timeout(const Duration(seconds: 15));
      if (!mounted || ticket != generation || !connecting) { await next.sink.close(); return; }
      setState(() { connected = true; connecting = false; status = 'Đã kết nối · Console máy chủ ${widget.id}'; });
      next.sink.add('1:${terminal.viewWidth}:${terminal.viewHeight}:');
    } catch (_) { lost(ticket); }
  }
  void lost(int ticket) { if (!mounted || ticket != generation) return; setState(() { connected = false; connecting = false; status = 'Kết nối console đã ngắt. Hãy kiểm tra máy đang chạy và đăng nhập còn hiệu lực, rồi kết nối lại.'; }); }
  @override
  void dispose() { generation++; subscription?.cancel(); socket?.sink.close(); terminal.onOutput = null; terminal.onResize = null; super.dispose(); }
  @override
  Widget build(BuildContext context) => Scaffold(backgroundColor: CloudColors.graphite, appBar: AppBar(backgroundColor: CloudColors.graphite, foregroundColor: Colors.white, leading: IconButton(tooltip: 'Về chi tiết máy chủ', onPressed: () => context.go('/may-chu/${widget.id}'), icon: const Icon(Icons.close_outlined)), title: Text('Console · Máy chủ ${widget.id}'), actions: [TextButton(onPressed: connecting ? null : connect, child: Text(connecting ? 'Đang kết nối…' : 'Kết nối lại', style: const TextStyle(color: Colors.white))), const SizedBox(width: 12)]), body: Column(children: [Container(width: double.infinity, padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12), color: connected ? CloudColors.olive.withValues(alpha: .22) : CloudColors.yellow.withValues(alpha: .18), child: Text(status, style: const TextStyle(color: Colors.white, fontSize: 13))), Expanded(child: Padding(padding: const EdgeInsets.all(12), child: TerminalView(terminal, autofocus: true, readOnly: !connected)))]));
}
