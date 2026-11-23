// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../theme/cloud_theme.dart';
import '../widgets/common.dart';
import '../widgets/instance_actions.dart';
import '../widgets/os_choices.dart';
import '../widgets/resource_chart.dart';
import '../widgets/service_connection.dart';
import 'logs_screen.dart';

class DetailScreen extends StatefulWidget {
  final CloudState state;
  final int id;
  const DetailScreen({super.key, required this.state, required this.id});
  @override
  State<DetailScreen> createState() => _DetailScreenState();
}
class _DetailScreenState extends State<DetailScreen> {
  Json? detail, credentials, status;
  List<Json> points = [];
  String? error, credentialsError, statsError, statusError;
  bool loading = true, hidden = true, busy = false, statsLoading = false;
  int tab = 0, generation = 0;
  String timeframe = 'hour';
  String get path => '/instances/${widget.id}';
  @override
  void initState() { super.initState(); load(); }
  @override
  void didUpdateWidget(DetailScreen old) { super.didUpdateWidget(old); if (old.id != widget.id) { detail = null; credentials = null; hidden = true; status = null; points = []; tab = 0; load(); } }
  Future<void> load() async {
    setState(() { loading = true; error = null; });
    try { final data = await widget.state.api.get('$path/detail'); if (mounted) setState(() => detail = data); } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => loading = false);
    if (!mounted || detail == null) return;
    await Future.wait([loadCredentials(), loadStatus(), loadStats()]);
  }
  Future<void> loadCredentials() async {
    try { final data = await widget.state.api.get('$path/credentials'); if (mounted) setState(() { credentials = data; hidden = true; credentialsError = null; }); } catch (e) { if (mounted) setState(() => credentialsError = e.toString()); }
  }
  Future<void> loadStatus() async {
    try { final data = await widget.state.api.get('$path/status-now'); if (mounted) setState(() { status = data; statusError = null; }); } catch (e) { if (mounted) setState(() => statusError = e.toString()); }
  }
  Future<void> loadStats() async {
    final ticket = ++generation;
    setState(() { statsLoading = true; statsError = null; });
    try { final data = await widget.state.api.list('$path/stats?timeframe=$timeframe'); if (mounted && ticket == generation) setState(() => points = data); } catch (e) { if (mounted && ticket == generation) setState(() { statsError = e.toString(); points = []; }); }
    if (mounted && ticket == generation) setState(() => statsLoading = false);
  }
  Future<void> destructive(String action) async {
    final d = detail!;
    final title = action == 'delete' ? 'Hủy dịch vụ' : action == 'reinstall' ? 'Cài lại hệ điều hành' : 'Đổi mật khẩu';
    final text = action == 'delete' ? 'Toàn bộ dữ liệu và máy chủ sẽ bị xóa vĩnh viễn. Các cổng kết nối được thu hồi. Phần giờ đã trả không hoàn lại. Thao tác này không thể hoàn tác.' : action == 'reinstall' ? 'Toàn bộ dữ liệu trên đĩa sẽ bị xóa và cài lại từ template gốc. VMID, gói, cổng và cấu hình dịch vụ được giữ; mật khẩu đăng nhập VM sẽ thay đổi.' : 'Hệ thống sẽ sinh mật khẩu mới và khởi động lại máy để áp dụng. Máy đang tắt sẽ được bật và có thể bắt đầu kỳ tính tiền mới.';
    if (!await confirm(context, title, text, typedName: action == 'password' ? null : '${d['ten']}')) return;
    if (!mounted) return;
    setState(() => busy = true);
    try {
      if (action == 'delete') { await widget.state.api.request(path, method: 'DELETE'); } else { await widget.state.api.post('$path/$action'); }
      await widget.state.refresh();
      if (!mounted) return;
      if (action == 'delete') { context.go('/may-chu'); return; }
      await load();
      if (mounted) message(context, action == 'password' ? 'Mật khẩu mới đã sẵn sàng trong thông tin đăng nhập.' : 'Đã cài lại hệ điều hành.');
    } catch (e) { if (mounted) message(context, e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  Json? options;
  String? optionsError, reinstallOs;
  int? reinstallPlan;
  Future<void> loadOptions() async {
    try { final data = await widget.state.api.get('$path/reinstall-options'); if (mounted) setState(() { options = data; optionsError = null; reinstallOs = data['os_ma'] as String?; reinstallPlan = data['plan_id'] as int?; }); } catch (e) { if (mounted) setState(() => optionsError = e is ApiException ? e.message : 'Chưa tải được lựa chọn cài lại.'); }
  }
  List<Json> get optionOs => [for (final os in (options?['os'] as List? ?? const [])) {...Map<String, dynamic>.from(os as Map), 'san_sang': true}];
  List<Json> get optionPlans => [for (final plan in (options?['plans'] as List? ?? const [])) Map<String, dynamic>.from(plan as Map)];
  Json? get chosenOs => optionOs.where((os) => os['ma'] == reinstallOs).firstOrNull;
  Json? get chosenPlan => optionPlans.where((plan) => plan['id'] == reinstallPlan).firstOrNull;
  String? planReason(Json plan) => plan['du_tai_nguyen'] != true ? 'Máy chủ đang chạy dịch vụ của bạn không còn đủ tài nguyên cho gói này.' : osPlanReason(plan, chosenOs);
  String priceNote() {
    final oldPrice = number(options?['gia_theo_gio']), newPrice = number(chosenPlan?['gia_theo_gio'] ?? oldPrice);
    if (newPrice == oldPrice) return 'Giá giữ nguyên ${money(oldPrice)} / giờ.';
    return 'Giá đổi từ ${money(oldPrice)} sang ${money(newPrice)} / giờ (${newPrice > oldPrice ? 'tăng' : 'giảm'} ${money((newPrice - oldPrice).abs())} / giờ). Giờ đang dùng đã trả theo giá cũ, từ kỳ tính tiền tiếp theo ví bị trừ theo giá mới.';
  }
  Future<void> reinstall() async {
    final d = detail!, os = chosenOs, plan = chosenPlan;
    final changed = options != null && (reinstallOs != options!['os_ma'] || reinstallPlan != options!['plan_id']);
    final text = 'Toàn bộ dữ liệu trên đĩa sẽ bị xóa và cài ${os?['ten'] ?? d['ten_he_dieu_hanh']}${plan == null ? '' : ', gói ${plan['ten']}'}. Mật khẩu đăng nhập sẽ được sinh mới.\n\n${priceNote()}';
    if (!await confirm(context, 'Cài lại hệ điều hành', text, typedName: '${d['ten']}')) return;
    if (!mounted) return;
    setState(() => busy = true);
    try {
      await widget.state.api.post('$path/reinstall', changed ? {if (reinstallOs != null) 'os_ma': reinstallOs, if (reinstallPlan != null) 'plan_id': reinstallPlan} : null);
      await widget.state.refresh();
      if (!mounted) return;
      final note = priceNote();
      await load(); await loadOptions();
      if (mounted) message(context, changed ? 'Đã cài lại. $note' : 'Đã cài lại hệ điều hành.');
    } catch (e) { if (mounted) message(context, e is ApiException ? e.message : 'Chưa cài lại được. Hãy tải lại trang để kiểm tra trạng thái.'); }
    if (mounted) setState(() => busy = false);
  }
  List<Widget> reinstallTab(Json d) {
    if (options == null && optionsError == null) { Future.microtask(loadOptions); return [const LinearProgressIndicator()]; }
    final ready = !busy && ['running', 'stopped'].contains(d['trang_thai']) && (chosenPlan == null || chosenPlan!['id'] == options?['plan_id'] && reinstallOs == options?['os_ma'] || planReason(chosenPlan!) == null);
    return [Text('Cài lại, đổi hệ điều hành hoặc gói', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 16), const Notice('Cài lại sẽ xóa toàn bộ dữ liệu. Hãy sao lưu dữ liệu cần giữ trước khi tiếp tục.'), if (optionsError != null) Notice(optionsError!, retry: loadOptions), if (optionOs.isEmpty) Text('Hệ điều hành: ${d['ten_he_dieu_hanh']}. Dịch vụ này cài lại đúng hệ điều hành đang dùng.') else ...[Text('Hệ điều hành', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 12), OSChoices(images: optionOs, selected: reinstallOs, onSelect: busy ? null : (os) => setState(() { reinstallOs = os['ma'] as String; if (chosenPlan != null && planReason(chosenPlan!) != null) reinstallPlan = optionPlans.where((p) => planReason(p) == null).firstOrNull?['id'] as int?; })), const SizedBox(height: 28), Text('Gói tài nguyên', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 12), PlanChoices(plans: optionPlans, selected: reinstallPlan, gpuName: ((widget.state.gpu['loai'] as List?) ?? const []).join(', '), disabledReason: (p) => busy ? 'Đang cài lại.' : planReason(p), onSelect: (id) => setState(() => reinstallPlan = id))], const SizedBox(height: 20), Text(priceNote(), key: const ValueKey('reinstall-price'), style: const TextStyle(fontWeight: FontWeight.w600)), const SizedBox(height: 20), FilledButton(key: const ValueKey('reinstall-submit'), onPressed: ready ? reinstall : null, child: Text(busy ? 'Đang cài lại…' : 'Cài lại hệ điều hành'))];
  }
  Future<void> setPassword() async {
    final windows = (credentials?['ket_noi'] ?? detail?['ket_noi']) == 'rdp';
    final value = await showDialog<String>(context: context, builder: (_) => PasswordDialog(windows: windows));
    if (value == null || !mounted) return;
    setState(() => busy = true);
    try {
      final data = await widget.state.api.post('$path/password', {'password': value});
      if (mounted) { setState(() { credentials = {...?credentials, ...data}; hidden = true; }); message(context, 'Đã đổi mật khẩu. Máy đang khởi động lại để áp dụng.'); }
      await widget.state.refresh();
    } catch (e) { if (mounted) message(context, e is ApiException ? e.message : 'Chưa đổi được mật khẩu. Hãy thử lại sau.'); }
    if (mounted) setState(() => busy = false);
  }
  @override
  Widget build(BuildContext context) {
    final d = detail;
    if (d == null) return PageBody(children: [const Heading('Chi tiết máy chủ', 'Đang lấy thông tin dịch vụ.'), if (loading) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load)]);
    final mobile = MediaQuery.sizeOf(context).width < 700;
    return PageBody(children: [TextButton.icon(onPressed: () => context.go('/may-chu'), icon: const Icon(Icons.dns_outlined, size: 18), label: const Text('Danh sách máy chủ')), const SizedBox(height: 16), Heading('${d['ten']}', '${serviceName(d['gpu'] != null ? 'ai' : d['dich_vu'])} · ${widget.state.planName(d['plan_id'])} · ${d['ten_he_dieu_hanh']}', trailing: StatusMark('${d['trang_thai']}')), if (loading) const LinearProgressIndicator(), if (error != null) Notice(error!, retry: load), Wrap(spacing: mobile ? 32 : 64, runSpacing: 20, children: [_metric('Giá mỗi giờ', money(d['gia_theo_gio'])), _metric('Tổng chi phí đã trả', money(d['tong_chi_phi'])), _metric('Ngày tạo', date(d['ngay_tao'])), _metric('Đã trả tới', date(d['paid_until']))]), const SizedBox(height: 24), InstanceActions(state: widget.state, instance: d, details: false, onChanged: load), const SizedBox(height: 12), if (d['loai'] == 'lxc') const Text('LXC đăng nhập bằng khóa SSH; console trình duyệt và đổi mật khẩu hiện chỉ hỗ trợ VM.', style: TextStyle(fontSize: 12)), const SizedBox(height: 16), TextButton.icon(onPressed: busy ? null : () => destructive('delete'), icon: const Icon(Icons.delete_outline), label: const Text('Hủy dịch vụ')), const SizedBox(height: 20), const Divider(), Wrap(spacing: 14, children: [for (var i = 0; i < 3; i++) TextButton(onPressed: () => setState(() => tab = i), child: Padding(padding: const EdgeInsets.symmetric(vertical: 10), child: Text(['Tổng quan', 'Cài lại hệ điều hành', 'Nhật ký thao tác'][i], style: TextStyle(fontWeight: tab == i ? FontWeight.w600 : FontWeight.w400, color: tab == i ? (Theme.of(context).brightness == Brightness.dark ? const Color(0xFFD5AFF1) : CloudColors.purple) : Theme.of(context).colorScheme.onSurface, decoration: tab == i ? TextDecoration.underline : null, decorationColor: CloudColors.purple))))]), const SizedBox(height: 24), if (tab == 0) ...overview(d) else if (tab == 1) ...reinstallTab(d) else LogList(api: widget.state.api, path: '$path/logs')]);
  }
  Widget _metric(String title, String value) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title.toUpperCase(), style: figures.copyWith(fontSize: 17, color: Theme.of(context).colorScheme.onSurfaceVariant)), const SizedBox(height: 4), Text(value, style: figures.copyWith(fontSize: title.contains('Giá') || title.contains('chi phí') ? 36 : 24))]);
  List<Widget> overview(Json d) {
    final mem = status == null || number(d['ram_mb']) <= 0 ? null : number(status!['mem']) / (number(d['ram_mb']) * 1024 * 1024);
    return [if (d['dich_vu'] != null && d['dich_vu'] != 'vps') ...[ServiceConnection(key: ValueKey('${widget.id}-${d['trang_thai']}-${d['paid_until']}'), api: widget.state.api, id: widget.id, kind: '${d['dich_vu']}'), const SizedBox(height: 32)], if (statusError != null) Notice('Chưa đọc được tài nguyên trực tiếp. ${statusError!}', retry: loadStatus), LayoutBuilder(builder: (context, c) {
      final bars = [ResourceBar('CPU · ${d['vcpu']} vCPU', status == null ? 'Chưa có số đo' : '${number(status!['cpu']).toStringAsFixed(1)}%', status == null ? null : number(status!['cpu']) / 100), ResourceBar('RAM · ${d['ram_mb']} MB', status == null ? 'Chưa có số đo' : '${(number(status!['mem']) / 1024 / 1024).round()} MB', mem), ResourceBar('Ổ đĩa', '${d['disk_gb']} GB được cấp', null)];
      return c.maxWidth < 700 ? Column(children: bars) : Row(children: [for (var i = 0; i < bars.length; i++) ...[if (i > 0) const SizedBox(width: 36), Expanded(child: bars[i])]]);
    }), const SizedBox(height: 32), Text('Thông tin đăng nhập', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12), if (credentialsError != null) Notice(credentialsError!, retry: loadCredentials), if (credentials != null) ...[DescriptionRow('Tài khoản', '${credentials!['username']}', copy: true), Container(constraints: const BoxConstraints(minHeight: 56), decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Theme.of(context).dividerColor))), child: Row(children: [SizedBox(width: MediaQuery.sizeOf(context).width < 420 ? 100 : 145, child: Text('MẬT KHẨU', style: figures.copyWith(fontSize: 17, color: Theme.of(context).colorScheme.onSurfaceVariant))), Expanded(child: SelectableText(credentials!['password'] == null ? 'Đăng nhập bằng khóa SSH' : hidden ? '••••••••••••••••' : '${credentials!['password']}')), if (credentials!['password'] != null) ...[IconButton(tooltip: hidden ? 'Hiện mật khẩu' : 'Ẩn mật khẩu', onPressed: () => setState(() => hidden = !hidden), icon: Icon(hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined)), IconButton(tooltip: 'Sao chép mật khẩu', onPressed: () async { await Clipboard.setData(ClipboardData(text: '${credentials!['password']}')); if (mounted) message(context, 'Đã sao chép mật khẩu.'); }, icon: const Icon(Icons.content_copy_outlined, size: 18))]])), if ((credentials!['ket_noi'] ?? d['ket_noi']) == 'rdp') ...[DescriptionRow('Địa chỉ RDP', '${credentials!['dia_chi']}', copy: true), const SizedBox(height: 12), const Text('Mở Remote Desktop trên máy tính, nhập địa chỉ và cổng ở trên rồi đăng nhập bằng tài khoản, mật khẩu này.', style: TextStyle(fontSize: 13))] else ...[if (credentials!['ipv6'] != null) ...[DescriptionRow('IPv6 công cộng', '${credentials!['ipv6']}', copy: true), DescriptionRow('SSH qua IPv6', 'ssh ${credentials!['username']}@${credentials!['ipv6']}', copy: true)], if (credentials!['ssh_port'] != null) DescriptionRow(credentials!['ipv6'] != null ? 'SSH qua IPv4' : 'Lệnh SSH', 'ssh -p ${credentials!['ssh_port']} ${credentials!['username']}@${credentials!['ssh_host'].toString().contains(':') ? '[${credentials!['ssh_host']}]' : credentials!['ssh_host']}', copy: true), if (d['gpu'] != null && credentials!['ssh_port'] != null) ...[DescriptionRow('Kiểm tra GPU', 'nvidia-smi', copy: true), DescriptionRow('Đường hầm JupyterLab', 'ssh -L 8888:localhost:8888 -p ${credentials!['ssh_port']} ${credentials!['username']}@${credentials!['ssh_host'].toString().contains(':') ? '[${credentials!['ssh_host']}]' : credentials!['ssh_host']}', copy: true), DescriptionRow('Chạy trong máy', 'jupyter lab --no-browser --port 8888', copy: true), const Text('Mở http://localhost:8888 trên máy của bạn sau khi đường hầm đã kết nối. PyTorch có sẵn ở /opt/ai.', style: TextStyle(fontSize: 13))], const SizedBox(height: 12), Text(credentials!['ipv6'] != null ? 'Máy có IPv6 công cộng riêng: mở sẵn mọi cổng, SSH cổng 22 không cần -p. Mạng của bạn chưa có IPv6 thì dùng lệnh SSH qua IPv4. Tự bật tường lửa (ufw) trong máy nếu cần. IP nội bộ chỉ dùng trong mạng VPS.' : 'Mở ứng dụng dòng lệnh trên máy tính, dán lệnh SSH rồi xác thực bằng khóa hoặc mật khẩu. IP nội bộ chỉ dùng trong mạng VPS.', style: const TextStyle(fontSize: 13))], if (d['loai'] == 'vm') Padding(padding: const EdgeInsets.only(top: 12), child: Wrap(spacing: 12, runSpacing: 8, children: [OutlinedButton.icon(key: const ValueKey('set-password'), onPressed: busy ? null : setPassword, icon: const Icon(Icons.edit_outlined), label: const Text('Đặt mật khẩu')), OutlinedButton.icon(onPressed: busy ? null : () => destructive('password'), icon: const Icon(Icons.lock_reset_outlined), label: Text(busy ? 'Đang xử lý…' : 'Sinh mật khẩu mới'))]))], const SizedBox(height: 36), Text('Chi tiết máy chủ', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12), DescriptionRow('Dịch vụ', serviceName(d['dich_vu'])), DescriptionRow('IP nội bộ', d['ip'] ?? 'Đang chờ cấp IP', copy: d['ip'] != null), DescriptionRow('Hệ điều hành', '${d['ten_he_dieu_hanh']}'), if (d['gpu'] != null) DescriptionRow('GPU', '${d['gpu']}'), DescriptionRow('Cấu hình', '${d['vcpu']} vCPU · ${d['ram_mb']} MB RAM · ${d['disk_gb']} GB ổ đĩa'), DescriptionRow('Tên máy chủ', '${d['ten']}'), DescriptionRow('VMID', '${d['vmid']}'), DescriptionRow(d['ket_noi'] == 'rdp' ? 'Cổng RDP' : 'Cổng SSH', '${d['ssh_port'] ?? 'Chưa cấp'}'), DescriptionRow('Console', d['ket_noi'] == 'rdp' ? 'Windows dùng Remote Desktop (RDP)' : d['loai'] == 'vm' ? 'Console trình duyệt · Máy cần đang chạy' : 'LXC dùng SSH'), const SizedBox(height: 40), Heading('Lịch sử tài nguyên', 'CPU và RAM cùng thang đo 0–100%. Khoảng thiếu số đo được để trống.', trailing: SegmentedButton<String>(showSelectedIcon: false, segments: const [ButtonSegment(value: 'hour', label: Text('Giờ')), ButtonSegment(value: 'day', label: Text('Ngày')), ButtonSegment(value: 'week', label: Text('Tuần'))], selected: {timeframe}, onSelectionChanged: (value) { setState(() => timeframe = value.first); loadStats(); })), if (statsLoading) const LinearProgressIndicator(), if (statsError != null) Notice(statsError!, retry: loadStats), LayoutBuilder(builder: (context, c) {
      final cpu = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('CPU', style: figures.copyWith(fontSize: 22)), const SizedBox(height: 12), ResourceChart(points: points)]);
      final ram = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('RAM', style: figures.copyWith(fontSize: 22)), const SizedBox(height: 12), ResourceChart(points: points, memory: true)]);
      return c.maxWidth < 850 ? Column(children: [cpu, const SizedBox(height: 32), ram]) : Row(children: [Expanded(child: cpu), const SizedBox(width: 36), Expanded(child: ram)]);
    })];
  }
}

class PasswordDialog extends StatefulWidget {
  final bool windows;
  const PasswordDialog({super.key, required this.windows});
  @override
  State<PasswordDialog> createState() => _PasswordDialogState();
}
class _PasswordDialogState extends State<PasswordDialog> {
  final form = GlobalKey<FormState>();
  final password = TextEditingController(), again = TextEditingController();
  bool hidden = true;
  @override
  void dispose() { password.dispose(); again.dispose(); super.dispose(); }
  String? validate(String? v) {
    final value = v ?? '';
    if (value.length < 8 || value.length > 128) return 'Mật khẩu cần 8 - 128 ký tự.';
    if (value.trim() != value || value.runes.any((c) => c < 32 || c == 127)) return 'Không để khoảng trắng ở đầu, cuối hay ký tự điều khiển.';
    if (widget.windows && [RegExp('[A-Z]'), RegExp('[a-z]'), RegExp('[0-9]'), RegExp('[^A-Za-z0-9]')].where((r) => r.hasMatch(value)).length < 3) return 'Windows cần ít nhất 3 trong 4 loại: chữ hoa, chữ thường, số, ký tự đặc biệt.';
    return null;
  }
  void submit() { if (form.currentState!.validate()) Navigator.pop(context, password.text); }
  @override
  Widget build(BuildContext context) => AlertDialog(titlePadding: const EdgeInsets.fromLTRB(24, 16, 8, 0), title: Row(children: [const Expanded(child: Text('Đặt mật khẩu')), IconButton(tooltip: 'Đóng', onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close))]), content: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 420), child: Form(key: form, child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [Text(widget.windows ? 'Mật khẩu cho tài khoản tbtadmin. Máy đang chạy sẽ khởi động lại để áp dụng.' : 'Mật khẩu cho tài khoản đăng nhập, ít nhất 8 ký tự. Máy đang chạy sẽ khởi động lại để áp dụng.'), const SizedBox(height: 16), TextFormField(key: const ValueKey('new-password'), controller: password, obscureText: hidden, autofocus: true, decoration: InputDecoration(labelText: 'Mật khẩu mới', suffixIcon: IconButton(tooltip: hidden ? 'Hiện mật khẩu' : 'Ẩn mật khẩu', onPressed: () => setState(() => hidden = !hidden), icon: Icon(hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined))), validator: validate), const SizedBox(height: 12), TextFormField(key: const ValueKey('new-password-again'), controller: again, obscureText: hidden, decoration: const InputDecoration(labelText: 'Nhập lại mật khẩu'), validator: (v) => v == password.text ? null : 'Hai mật khẩu chưa khớp.', onFieldSubmitted: (_) => submit())]))), actions: [FilledButton(key: const ValueKey('password-submit'), onPressed: submit, child: const Text('Lưu mật khẩu'))]);
}
