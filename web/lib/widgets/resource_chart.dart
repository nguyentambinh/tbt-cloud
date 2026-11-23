// Nguyễn Tâm Bình - 2324801030003
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../theme/cloud_theme.dart';

class ResourceChart extends StatelessWidget {
  final List<Json> points;
  final bool memory;
  const ResourceChart({super.key, required this.points, this.memory = false});
  @override
  Widget build(BuildContext context) {
    final spots = points.map((p) {
      final raw = memory ? p['mem_used'] : p['cpu'];
      if (raw == null || memory && number(p['mem_total']) == 0) return FlSpot.nullSpot;
      final value = memory ? number(raw) / number(p['mem_total']) * 100 : number(raw);
      return FlSpot(number(p['time']), value.clamp(0, 100));
    }).toList();
    if (spots.where((p) => p != FlSpot.nullSpot).isEmpty) return const SizedBox(height: 200, child: Center(child: Text('Chưa có số đo trong khoảng thời gian này.')));
    final ink = Theme.of(context).colorScheme.onSurfaceVariant;
    final color = Theme.of(context).brightness == Brightness.dark ? const Color(0xFFCBA1EA) : CloudColors.purple;
    return Semantics(label: 'Biểu đồ ${memory ? 'RAM' : 'CPU'} theo thời gian, thang đo từ 0 đến 100 phần trăm', child: SizedBox(height: 220, child: LineChart(LineChartData(minY: 0, maxY: 100, gridData: FlGridData(show: true, drawVerticalLine: false, horizontalInterval: 25, getDrawingHorizontalLine: (_) => FlLine(color: ink.withValues(alpha: .15), strokeWidth: 1)), borderData: FlBorderData(show: false), titlesData: FlTitlesData(topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)), rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)), leftTitles: AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 38, interval: 25, getTitlesWidget: (v, _) => Text('${v.toInt()}%', style: TextStyle(color: ink, fontSize: 11)))), bottomTitles: AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 28, interval: _interval(), getTitlesWidget: (v, meta) { if (v == meta.max || v == meta.min) return const SizedBox.shrink(); final d = DateTime.fromMillisecondsSinceEpoch((v * 1000).round()).toLocal(); return Padding(padding: const EdgeInsets.only(top: 8), child: Text('${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}\n${d.day}/${d.month}', style: TextStyle(color: ink, fontSize: 10))); }))), lineBarsData: [LineChartBarData(spots: spots, color: color, barWidth: 1.6, isCurved: false, dotData: const FlDotData(show: false), belowBarData: BarAreaData(show: true, color: color.withValues(alpha: .13)))], lineTouchData: LineTouchData(touchTooltipData: LineTouchTooltipData(getTooltipItems: (items) => items.map((item) => LineTooltipItem('${item.y.toStringAsFixed(1)}%', TextStyle(color: color, fontWeight: FontWeight.w600))).toList()))), duration: Duration.zero)));
  }
  double _interval() { if (points.length < 2) return 60; return ((number(points.last['time']) - number(points.first['time'])) / 4).clamp(1, double.infinity); }
}
