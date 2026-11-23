// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import '../theme/cloud_theme.dart';

class TourLayer {
  final String name, title, body;
  final List<String> facts;
  final String? action;
  final VoidCallback? onAction;
  const TourLayer(this.name, this.title, this.body, this.facts, {this.action, this.onAction});
}

class LayerTour extends StatefulWidget {
  final List<TourLayer> layers;
  const LayerTour({super.key, required this.layers});
  @override
  State<LayerTour> createState() => _LayerTourState();
}
class _LayerTourState extends State<LayerTour> {
  int active = 0;
  double wheel = 0;
  Duration? last;
  void go(int index) => setState(() => active = index.clamp(0, widget.layers.length - 1));
  // Lăn chuột trong khu này để chuyển tầng; tới tầng đầu/cuối thì nhường cho trang cuộn tiếp
  void scroll(PointerSignalEvent event) {
    if (event is! PointerScrollEvent) return;
    final down = event.scrollDelta.dy > 0;
    if (event.scrollDelta.dy == 0 || (down && active == widget.layers.length - 1) || (!down && active == 0)) return;
    GestureBinding.instance.pointerSignalResolver.register(event, (_) {
      wheel += event.scrollDelta.dy;
      if (wheel.abs() < 40 || (last != null && event.timeStamp - last! < const Duration(milliseconds: 380))) return;
      last = event.timeStamp;
      go(active + (wheel > 0 ? 1 : -1));
      wheel = 0;
    });
  }
  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
    final layer = widget.layers[active];
    final still = MediaQuery.disableAnimationsOf(context);
    final stack = TweenAnimationBuilder<double>(tween: Tween(end: active.toDouble()), duration: still ? Duration.zero : const Duration(milliseconds: 420), curve: Curves.easeOutCubic, builder: (context, value, _) => LayoutBuilder(builder: (context, box) {
      final size = Size(box.maxWidth, c.maxWidth < 850 ? 300 : 420);
      final painter = LayerStackPainter(names: [for (final l in widget.layers) l.name], active: value, ink: Theme.of(context).colorScheme.onSurface, muted: Theme.of(context).colorScheme.onSurfaceVariant, outline: Theme.of(context).colorScheme.outline, fill: Theme.of(context).colorScheme.surfaceContainerHighest, accent: Theme.of(context).brightness == Brightness.dark ? const Color(0xFFD5AFF1) : CloudColors.purple);
      return GestureDetector(onTapUp: (d) { final hit = painter.hit(d.localPosition, size); if (hit != null) go(hit); }, child: MouseRegion(cursor: SystemMouseCursors.click, child: CustomPaint(size: size, painter: painter)));
    }));
    final detail = AnimatedSwitcher(duration: still ? Duration.zero : const Duration(milliseconds: 260), child: Column(key: ValueKey(active), crossAxisAlignment: CrossAxisAlignment.start, children: [Text('TẦNG ${active + 1} / ${widget.layers.length} · ${layer.name.toUpperCase()}', style: figures.copyWith(fontSize: 18, color: Theme.of(context).colorScheme.onSurfaceVariant)), const SizedBox(height: 8), Text(layer.title, style: Theme.of(context).textTheme.headlineLarge), const SizedBox(height: 14), Text(layer.body, style: const TextStyle(fontSize: 16, height: 1.7)), const SizedBox(height: 18), for (final fact in layer.facts) Container(constraints: const BoxConstraints(minHeight: 44), padding: const EdgeInsets.symmetric(vertical: 8), decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Theme.of(context).dividerColor))), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Padding(padding: EdgeInsets.only(top: 3), child: Icon(Icons.check_outlined, size: 18, color: CloudColors.olive)), const SizedBox(width: 12), Expanded(child: Text(fact))])), if (layer.action != null) Padding(padding: const EdgeInsets.only(top: 20), child: OutlinedButton(onPressed: layer.onAction, child: Text(layer.action!)))]));
    final nav = Row(children: [IconButton(tooltip: 'Tầng trước', onPressed: active == 0 ? null : () => go(active - 1), icon: const Icon(Icons.south_outlined)), const SizedBox(width: 4), for (var i = 0; i < widget.layers.length; i++) Semantics(button: true, selected: i == active, label: 'Tầng ${i + 1}: ${widget.layers[i].name}', child: InkWell(onTap: () => go(i), customBorder: const CircleBorder(), child: Padding(padding: const EdgeInsets.all(6), child: AnimatedContainer(duration: still ? Duration.zero : const Duration(milliseconds: 200), width: i == active ? 22 : 10, height: 10, decoration: BoxDecoration(borderRadius: BorderRadius.circular(5), color: i == active ? CloudColors.purple : Theme.of(context).colorScheme.outline))))), const SizedBox(width: 4), IconButton(tooltip: 'Tầng tiếp theo', onPressed: active == widget.layers.length - 1 ? null : () => go(active + 1), icon: const Icon(Icons.north_outlined))]);
    if (c.maxWidth < 850) {
      final buttons = Row(children: [Expanded(child: OutlinedButton.icon(key: const ValueKey('tour-prev'), onPressed: active == 0 ? null : () => go(active - 1), icon: const Icon(Icons.arrow_back_outlined), label: const Text('Trước'))), const SizedBox(width: 12), Expanded(child: FilledButton.icon(key: const ValueKey('tour-next'), onPressed: active == widget.layers.length - 1 ? null : () => go(active + 1), icon: const Icon(Icons.arrow_forward_outlined), label: Text(active == widget.layers.length - 1 ? 'Hết' : 'Tiếp: ${widget.layers[active + 1].name}', maxLines: 1, overflow: TextOverflow.ellipsis)))]);
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [stack, const SizedBox(height: 8), buttons, const SizedBox(height: 20), detail, const SizedBox(height: 20), buttons]);
    }
    return Listener(onPointerSignal: scroll, child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(flex: 5, child: Column(children: [stack, nav])), const SizedBox(width: 48), Expanded(flex: 6, child: Padding(padding: const EdgeInsets.only(top: 24), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [detail, const SizedBox(height: 16), Text('Lăn chuột trong khung này để đi qua từng tầng', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.onSurfaceVariant))])))]));
  });
}

class LayerStackPainter extends CustomPainter {
  final List<String> names;
  final double active;
  final Color ink, muted, outline, fill, accent;
  LayerStackPainter({required this.names, required this.active, required this.ink, required this.muted, required this.outline, required this.fill, required this.accent});
  double gap(Size size) => (size.height - 70) / names.length;
  Path slab(int index, Size size) {
    final lift = (1 - (active - index).abs()).clamp(0.0, 1.0) * 14;
    final top = size.height - 60 - (index + 1) * gap(size) - lift;
    final w = size.width, h = 54.0, skew = w * .16;
    return Path()..moveTo(skew, top)..lineTo(w, top)..lineTo(w - skew, top + h)..lineTo(0, top + h)..close();
  }
  int? hit(Offset point, Size size) {
    for (var i = names.length - 1; i >= 0; i--) {
      if (slab(i, size).contains(point)) return i;
    }
    return null;
  }
  @override
  void paint(Canvas canvas, Size size) {
    for (var i = 0; i < names.length; i++) {
      final weight = (1 - (active - i).abs()).clamp(0.0, 1.0);
      final path = slab(i, size);
      final bounds = path.getBounds();
      canvas.drawPath(path.shift(const Offset(0, 6)), Paint()..color = outline.withValues(alpha: .35));
      canvas.drawPath(path, Paint()..color = Color.lerp(fill, accent.withValues(alpha: .22), weight)!);
      canvas.drawPath(path, Paint()..color = Color.lerp(outline, accent, weight)!..style = PaintingStyle.stroke..strokeWidth = 1 + weight);
      final center = Offset(bounds.left + bounds.width * .16 + 18, bounds.center.dy);
      canvas.drawCircle(center, 14, Paint()..color = Color.lerp(fill, accent, weight)!);
      canvas.drawCircle(center, 14, Paint()..color = Color.lerp(muted, accent, weight)!..style = PaintingStyle.stroke..strokeWidth = 1.5);
      final number = TextPainter(text: TextSpan(text: '${i + 1}', style: TextStyle(fontFamily: 'Barlow Condensed', fontWeight: FontWeight.w600, fontSize: 17, color: weight > .5 ? Colors.white : ink)), textDirection: TextDirection.ltr)..layout();
      number.paint(canvas, center - Offset(number.width / 2, number.height / 2));
      final label = TextPainter(text: TextSpan(text: names[i], style: TextStyle(fontFamily: 'Barlow Condensed', fontWeight: FontWeight.w600, fontSize: 20, color: Color.lerp(muted, ink, .4 + weight * .6))), textDirection: TextDirection.ltr, maxLines: 1, ellipsis: '…')..layout(maxWidth: bounds.width * .6);
      label.paint(canvas, Offset(center.dx + 26, bounds.center.dy - label.height / 2));
    }
  }
  @override
  bool shouldRepaint(LayerStackPainter old) => old.active != active || old.ink != ink || old.accent != accent || old.names.length != names.length;
}
