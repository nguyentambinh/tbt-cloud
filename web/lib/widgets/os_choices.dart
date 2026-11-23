// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../theme/cloud_theme.dart';

class OSChoices extends StatelessWidget {
  final List<Json> images;
  final String? selected;
  final ValueChanged<Json>? onSelect;
  const OSChoices({super.key, required this.images, required this.selected, required this.onSelect});
  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
    final columns = c.maxWidth < 600 ? 1 : c.maxWidth < 1000 ? 2 : 3;
    final width = (c.maxWidth - (columns - 1) * 20) / columns;
    return Wrap(spacing: 20, runSpacing: 20, children: [for (final os in images) SizedBox(width: width, child: Semantics(selected: selected == os['ma'], enabled: os['san_sang'] == true && onSelect != null, child: Opacity(opacity: os['san_sang'] == true ? 1 : .55, child: Material(color: selected == os['ma'] ? CloudColors.purple.withValues(alpha: .07) : Colors.transparent, child: InkWell(onTap: os['san_sang'] == true && onSelect != null ? () => onSelect!(os) : null, borderRadius: BorderRadius.circular(8), child: Container(padding: const EdgeInsets.all(24), decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), border: Border.all(color: selected == os['ma'] ? CloudColors.purple : Theme.of(context).dividerColor, width: selected == os['ma'] ? 2 : 1)), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${os['ten']}', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 12), Text('${os['ket_noi'] == 'rdp' ? 'RDP · Remote Desktop' : 'SSH'} · ${os['min_ram_mb']} MB RAM · ${os['min_disk_gb']} GB'), if (os['san_sang'] != true) ...[const SizedBox(height: 8), const Text('Chưa có node sẵn sàng')]])))))))]);
  });
}
