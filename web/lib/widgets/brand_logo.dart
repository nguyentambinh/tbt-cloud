// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import '../theme/cloud_theme.dart';

class BrandLogo extends StatelessWidget {
  final bool compact;
  const BrandLogo({super.key, this.compact = false});
  @override
  Widget build(BuildContext context) => Semantics(label: 'TBT Cloud', image: true, child: ExcludeSemantics(child: SizedBox(width: compact ? 42 : 170, height: 48, child: Row(children: [Container(width: 42, height: 42, padding: const EdgeInsets.all(3), decoration: BoxDecoration(color: Theme.of(context).brightness == Brightness.dark ? Colors.white : Colors.transparent, shape: BoxShape.circle), child: ClipOval(child: Image.asset('assets/brand/logo.png', filterQuality: FilterQuality.medium))), if (!compact) ...[const SizedBox(width: 10), Text('TBT Cloud', style: figures.copyWith(fontSize: 30, color: Theme.of(context).colorScheme.onSurface))]]))));
}

class BrandHero extends StatelessWidget {
  const BrandHero({super.key});
  @override
  Widget build(BuildContext context) => AspectRatio(aspectRatio: 1.3, child: Center(child: LayoutBuilder(builder: (context, c) {
    final size = c.biggest.shortestSide * .86;
    return Container(width: size, height: size, padding: EdgeInsets.all(size * .12), decoration: BoxDecoration(shape: BoxShape.circle, color: Theme.of(context).brightness == Brightness.dark ? Colors.white : CloudColors.purple.withValues(alpha: .05), border: Border.all(color: Theme.of(context).dividerColor)), child: Semantics(label: 'Logo TBT Cloud', image: true, child: ClipOval(child: Image.asset('assets/brand/logo.png', filterQuality: FilterQuality.medium))));
  })));
}
