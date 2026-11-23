// Nguyễn Tâm Bình - 2324801030003
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../theme/cloud_theme.dart';

class NetworkMap extends StatefulWidget {
  final List<Json> nodes, instances;
  final int? selected;
  final ValueChanged<int>? onSelect;
  final double height;
  final bool illustration;
  const NetworkMap({super.key, required this.nodes, this.instances = const [], this.selected, this.onSelect, this.height = 420, this.illustration = false});
  @override
  State<NetworkMap> createState() => _NetworkMapState();
}
class _NetworkMapState extends State<NetworkMap> with SingleTickerProviderStateMixin {
  late final AnimationController controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 850));
  @override
  void didChangeDependencies() { super.didChangeDependencies(); _animate(); }
  @override
  void didUpdateWidget(NetworkMap old) { super.didUpdateWidget(old); if (old.selected != widget.selected || old.nodes != widget.nodes) _animate(); }
  void _animate() { if (MediaQuery.disableAnimationsOf(context)) { controller.value = 1; } else { controller.forward(from: 0); } }
  @override
  void dispose() { controller.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return ClipRRect(borderRadius: BorderRadius.circular(8), child: Container(height: widget.height, decoration: BoxDecoration(color: dark ? const Color(0xFF1B201D) : const Color(0xFFFAFBF7), border: Border.all(color: Theme.of(context).dividerColor), borderRadius: BorderRadius.circular(8)), child: LayoutBuilder(builder: (context, c) {
      final size = Size(c.maxWidth, widget.height);
      final layout = MapLayout(size, widget.nodes, widget.instances);
      return Stack(children: [Positioned.fill(child: AnimatedBuilder(animation: controller, builder: (context, _) => CustomPaint(painter: TerrainPainter(layout, widget.nodes, widget.instances, widget.selected, Curves.easeOutExpo.transform(controller.value), dark)))), Positioned(top: 14, left: 16, child: Text(widget.illustration ? 'BẢN ĐỒ MẠNG · MINH HỌA' : 'BẢN ĐỒ MẠNG', style: figures.copyWith(fontSize: 17, letterSpacing: .8))), Positioned(bottom: 12, left: 16, right: 16, child: Wrap(spacing: 18, runSpacing: 4, children: [legend('Máy cá nhân', CloudColors.olive), legend('Mạng mesh', CloudColors.mesh), legend('Đường đang chọn', dark ? const Color(0xFFBB7CEE) : CloudColors.purple)])), for (var i = 0; i < widget.nodes.length; i++) Positioned(left: (layout.nodes[i].dx - 65).clamp(0, math.max(0, size.width - 130)), top: layout.nodes[i].dy + (size.height < 240 ? 16 : 36), width: 130, child: Center(child: Text('${widget.nodes[i]['ten']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontFamily: 'Barlow Condensed', fontSize: size.height < 240 ? 14 : 20, fontWeight: FontWeight.w600, color: Theme.of(context).colorScheme.onSurface)))), Positioned(left: layout.gateway.dx - 43, top: layout.gateway.dy + 20, child: Text('Gateway', style: figures.copyWith(fontSize: 18))), for (var i = 0; i < widget.instances.length; i++) if (layout.vps.containsKey(widget.instances[i]['id'])) Positioned(left: layout.vps[widget.instances[i]['id']]!.dx - 22, top: layout.vps[widget.instances[i]['id']]!.dy - 22, width: 44, height: 44, child: Semantics(selected: widget.selected == widget.instances[i]['id'], label: 'Chọn máy chủ ${widget.instances[i]['ten']}', button: true, child: Tooltip(message: '${widget.instances[i]['ten']}', child: Material(color: Colors.transparent, child: InkWell(borderRadius: BorderRadius.circular(24), onTap: widget.onSelect == null ? null : () => widget.onSelect!(widget.instances[i]['id'] as int), child: Center(child: Container(width: 31, height: 31, alignment: Alignment.center, decoration: BoxDecoration(shape: BoxShape.circle, color: widget.selected == widget.instances[i]['id'] ? CloudColors.purple : Theme.of(context).colorScheme.surface, border: Border.all(color: widget.selected == widget.instances[i]['id'] ? CloudColors.purple : CloudColors.brown, width: 2)), child: Text('${i + 1}', style: figures.copyWith(fontSize: 21, color: widget.selected == widget.instances[i]['id'] ? Colors.white : Theme.of(context).colorScheme.onSurface))))))))) ]);
    })));
  }
  Widget legend(String text, Color color) => Row(mainAxisSize: MainAxisSize.min, children: [Container(width: 12, height: 3, color: color), const SizedBox(width: 5), Text(text, style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.onSurfaceVariant))]);
}

class MapLayout {
  final Size size;
  final List<Offset> nodes = [];
  final Map<int, Offset> vps = {};
  late final Offset gateway;
  MapLayout(this.size, List<Json> data, List<Json> instances) {
    gateway = Offset(size.width * .5, size.height * .49);
    for (var i = 0; i < data.length; i++) {
      final angle = -math.pi * .8 + i * math.pi * 2 / math.max(3, data.length);
      final ring = i ~/ 8;
      nodes.add(gateway + Offset(math.cos(angle) * size.width * (.31 - ring * .035), math.sin(angle) * size.height * .27));
    }
    for (var i = 0; i < data.length; i++) {
      final children = instances.where((v) => v['node_id'] == data[i]['id']).toList();
      for (var j = 0; j < children.length; j++) {
        final per = math.min(6, children.length - (j ~/ 6) * 6);
        final angle = per == 1 ? -math.pi / 2 : -math.pi + .45 + (j % 6) * (math.pi - .9) / (per - 1);
        final r = size.height < 240 ? 25.0 : 48.0 + (j ~/ 6) * 12;
        final p = nodes[i] + Offset(math.cos(angle) * r, math.sin(angle) * r);
        vps[children[j]['id'] as int] = Offset(p.dx.clamp(24, size.width - 24), p.dy.clamp(48, size.height - 50));
      }
    }
  }
}
class TerrainPainter extends CustomPainter {
  final MapLayout layout;
  final List<Json> nodes, instances;
  final int? selected;
  final double progress;
  final bool dark;
  TerrainPainter(this.layout, this.nodes, this.instances, this.selected, this.progress, this.dark);
  Path contour(Offset center, double rx, double ry, double seed) {
    final p = Path();
    for (var i = 0; i <= 100; i++) {
      final a = i / 100 * math.pi * 2;
      final r = 1 + .1 * math.sin(3 * a + seed) + .06 * math.cos(5 * a - seed) + .035 * math.sin(9 * a);
      final point = center + Offset(math.cos(a) * rx * r, math.sin(a) * ry * r);
      if (i == 0) { p.moveTo(point.dx, point.dy); } else { p.lineTo(point.dx, point.dy); }
    }
    return p..close();
  }
  @override
  void paint(Canvas canvas, Size size) {
    canvas.save(); canvas.clipRect(Offset.zero & size);
    final brown = Paint()..color = CloudColors.brown.withValues(alpha: dark ? .24 : .18)..style = PaintingStyle.stroke..strokeWidth = .7;
    for (var k = 0; k < 5; k++) {
      final center = Offset(size.width * (k % 3) * .48, size.height * (k ~/ 3) * .9);
      for (var j = 0; j < 13; j++) { canvas.drawPath(contour(center, 25 + j * 23, 22 + j * 18, k.toDouble()), brown); }
    }
    final mesh = Paint()..color = CloudColors.mesh.withValues(alpha: .7)..strokeWidth = 1.3..style = PaintingStyle.stroke;
    for (var i = 0; i < nodes.length; i++) {
      final point = layout.nodes[i];
      canvas.drawPath(contour(point, size.height < 240 ? 27 : 58, size.height < 240 ? 17 : 38, i + .2), Paint()..color = (nodes[i]['online'] == true ? CloudColors.olive : CloudColors.yellow).withValues(alpha: .4));
      canvas.drawLine(layout.gateway, point, mesh);
      if (i > 0) canvas.drawLine(layout.nodes[i - 1], point, mesh..color = CloudColors.mesh.withValues(alpha: .35));
      mesh.color = CloudColors.mesh.withValues(alpha: .7);
      canvas.drawCircle(point, 4, Paint()..color = dark ? Colors.white : const Color(0xFF343A2B));
      for (var j = 0; j < 12; j++) {
        final dx = math.sin(j * 8.3 + i) * (size.height < 240 ? 20 : 40);
        final dy = math.cos(j * 3.7) * (size.height < 240 ? 10 : 23);
        canvas.drawCircle(point + Offset(dx, dy), 1, Paint()..color = CloudColors.brown.withValues(alpha: .5));
      }
    }
    final triangle = Path()..moveTo(layout.gateway.dx, layout.gateway.dy - 14)..lineTo(layout.gateway.dx - 13, layout.gateway.dy + 9)..lineTo(layout.gateway.dx + 13, layout.gateway.dy + 9)..close();
    canvas.drawPath(triangle, Paint()..color = dark ? CloudColors.graphite : Colors.white);
    canvas.drawPath(triangle, Paint()..color = CloudColors.brown..strokeWidth = 2..style = PaintingStyle.stroke);
    final chosen = instances.where((v) => v['id'] == selected).firstOrNull;
    if (chosen != null && layout.vps.containsKey(selected)) {
      final idx = nodes.indexWhere((n) => n['id'] == chosen['node_id']);
      if (idx >= 0) {
        final node = layout.nodes[idx], vps = layout.vps[selected]!;
        final route = Path()..moveTo(layout.gateway.dx, layout.gateway.dy)..lineTo(node.dx, node.dy)..lineTo(vps.dx, vps.dy);
        final metric = route.computeMetrics().first;
        final active = metric.extractPath(0, metric.length * progress);
        canvas.drawPath(active, Paint()..color = dark ? const Color(0xFFD5AFF1) : Colors.white..strokeWidth = 7..style = PaintingStyle.stroke);
        canvas.drawPath(active, Paint()..color = CloudColors.purple..strokeWidth = 3..strokeCap = StrokeCap.round..strokeJoin = StrokeJoin.round..style = PaintingStyle.stroke);
      }
    }
    canvas.restore();
  }
  @override
  bool shouldRepaint(TerrainPainter old) => true;
}
