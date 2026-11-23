// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../widgets/common.dart';
import '../widgets/os_choices.dart';

class CreateScreen extends StatefulWidget {
  final CloudState state;
  const CreateScreen({super.key, required this.state});
  @override
  State<CreateScreen> createState() => _CreateScreenState();
}
class _CreateScreenState extends State<CreateScreen> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController(), ssh = TextEditingController();
  final repo = TextEditingController(), branch = TextEditingController(text: 'main');
  String service = 'vps';
  int? planId;
  String osMa = 'debian13';
  bool advanced = false;
  bool get choosesOS => service == 'vps';
  bool get ai => service == 'ai';
  List<Json> get vpsImages => widget.state.osImages.where((os) => os['chi_gpu'] != true).toList();
  Json? get selectedOS => ai ? widget.state.osImages.where((os) => os['chi_gpu'] == true && os['san_sang'] == true).firstOrNull : choosesOS ? vpsImages.where((os) => os['ma'] == osMa && os['san_sang'] == true).firstOrNull ?? vpsImages.where((os) => os['san_sang'] == true).firstOrNull : null;
  int get freeGpu => number(widget.state.gpu['ranh']).toInt();
  String get gpuName => ((widget.state.gpu['loai'] as List?) ?? const []).join(', ');
  bool get windows => selectedOS?['ho'] == 'windows';
  String? error;
  bool busy = false;
  Json? created;
  @override
  void dispose() { name.dispose(); ssh.dispose(); repo.dispose(); branch.dispose(); super.dispose(); }
  String? validateRepo(String? value) {
    final text = value?.trim() ?? '';
    final uri = Uri.tryParse(text);
    if (uri == null || uri.scheme != 'https' || uri.host.isEmpty || uri.authority.contains('@') || RegExp(r'^https://[^/]*@').hasMatch(text) || text.length > 300 || !RegExp(r"^https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$").hasMatch(text) || RegExp(r'%(?![0-9A-Fa-f]{2})').hasMatch(text)) return 'Nhập địa chỉ HTTPS của kho Git công khai, không kèm tài khoản hay mật khẩu.';
    return null;
  }
  String? validateKey(String? v) { final value = v?.trim() ?? ''; if (value.isEmpty) return null; if (value.length < 30 || value.length > 8192 || value.contains('\n') || value.contains('\r') || !RegExp(r'^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+) [A-Za-z0-9+/]+=*( .*)?$').hasMatch(value)) return 'Dán một khóa SSH công khai hợp lệ trên một dòng.'; return null; }
  List<Json> get servicePlans => plansForService(widget.state.plans, service);
  List<Json> get eligiblePlans => servicePlans.where((p) => osPlanReason(p, selectedOS) == null).toList();
  int? get selectedPlanId => eligiblePlans.any((p) => p['id'] == planId) ? planId : eligiblePlans.firstOrNull?['id'] as int?;
  void chooseOS(Json os) => setState(() { osMa = os['ma'] as String; planId = null; error = null; });
  void chooseService(String value) => setState(() { service = value; planId = null; error = null; });
  Future<void> create() async {
    if (!form.currentState!.validate() || busy) { if (!advanced && (name.text.isNotEmpty || ssh.text.isNotEmpty)) setState(() => advanced = true); return; }
    if (choosesOS && selectedOS == null) { setState(() => error = 'Chưa có máy chủ sẵn sàng cho hệ điều hành này. Hãy thử lại sau.'); return; }
    if (ai && (selectedOS == null || freeGpu < 1)) { setState(() => error = 'GPU đang được dùng hết, vui lòng thử lại sau.'); return; }
    final selected = selectedPlanId;
    if (selected == null) { setState(() => error = 'Hãy chọn một gói tài nguyên.'); return; }
    final plan = servicePlans.firstWhere((p) => p['id'] == selected);
    if (widget.state.balance < number(plan['gia_theo_gio'])) { setState(() => error = 'Ví chưa đủ trả trước một giờ. Hãy nạp thêm tiền.'); return; }
    setState(() { busy = true; error = null; });
    try {
      final result = await widget.state.api.post('/instances', {if (name.text.trim().isNotEmpty) 'ten': name.text.trim(), 'plan_id': selected, 'loai': 'vm', 'dich_vu': ai ? 'vps' : service, if (service == 'webapp') ...{'repo_url': repo.text.trim(), 'branch': branch.text}, if (choosesOS || ai) 'os_ma': selectedOS!['ma'], if (!windows && ssh.text.trim().isNotEmpty) 'ssh_public_key': ssh.text.trim()});
      await widget.state.refresh();
      if (!mounted) return;
      setState(() => created = result);
      await Future<void>.delayed(Duration(milliseconds: MediaQuery.disableAnimationsOf(context) ? 0 : 1100));
      if (mounted) context.go('/may-chu/${result['id']}');
    } catch (e) { if (mounted) setState(() => error = e is ApiException ? e.message : 'Chưa tạo được dịch vụ. Hãy tải lại để kiểm tra kết quả trước khi thử lại.'); }
    if (mounted) setState(() => busy = false);
  }
  Widget group(String title, String subtitle, List<String> values) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: Theme.of(context).textTheme.titleLarge), Text(subtitle, style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.onSurfaceVariant)), const SizedBox(height: 12), Wrap(spacing: 12, runSpacing: 8, children: [for (final value in values) ChoiceChip(key: ValueKey('service-$value'), label: Text(serviceName(value)), selected: service == value, onSelected: busy ? null : (_) => chooseService(value))])]);
  String get loginSummary => windows ? 'Đăng nhập Remote Desktop: tbtadmin · mật khẩu do hệ thống sinh, xem và đổi ở trang chi tiết máy.' : 'Đăng nhập: root · mật khẩu ngẫu nhiên 8 ký tự (hoa, thường, số, ký tự đặc biệt), xem và đổi ở trang chi tiết máy.';
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: widget.state, builder: (context, _) {
    if (created != null) return PageBody(children: [Heading('Đã tạo ${created!['ten']}.', 'Máy chủ đang khởi động. Đang mở trang thông tin máy chủ…'), const LinearProgressIndicator()]);
    final ready = !(busy || selectedPlanId == null || (choosesOS && selectedOS == null) || (ai && (selectedOS == null || freeGpu < 1)));
    return PageBody(children: [Heading('Tạo dịch vụ', 'Chọn loại dịch vụ và gói rồi bấm tạo, mọi thứ khác đã được đặt sẵn.', trailing: TextButton(onPressed: () => context.go('/vi'), child: Text('Ví: ${money(widget.state.balance)}'))), if (error != null) Notice(error!), Text('Loại dịch vụ', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 20), LayoutBuilder(builder: (context, c) {
      final iaas = group('IaaS · Hạ tầng', 'Máy chủ riêng, toàn quyền quản trị', ['vps', 'ai']);
      final paas = group('PaaS · Nền tảng', 'Dịch vụ dựng sẵn, chỉ việc dùng', ['postgres', 'webapp']);
      return c.maxWidth < 760 ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [iaas, const SizedBox(height: 24), paas]) : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: iaas), const SizedBox(width: 36), Expanded(child: paas)]);
    }), const SizedBox(height: 32), if (choosesOS) ...[Text('Hệ điều hành', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 18), OSChoices(images: vpsImages, selected: selectedOS?['ma'] as String?, onSelect: busy ? null : chooseOS), if (selectedOS == null && !widget.state.loading) const Notice('Chưa có máy chủ sẵn sàng cho hệ điều hành này. Hãy thử lại sau.'), const SizedBox(height: 32)], if (ai) ...[Text('GPU', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12), Text(gpuName.isEmpty ? 'GPU: chưa khai báo' : '$gpuName · còn rảnh $freeGpu/${number(widget.state.gpu['tong']).toInt()}', key: const ValueKey('gpu-status'), style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 6), Text(selectedOS == null ? 'Chưa có máy chủ GPU sẵn sàng.' : '${selectedOS!['ten']} · driver NVIDIA, CUDA, PyTorch và JupyterLab dựng sẵn'), if (freeGpu < 1 && !widget.state.loading) const Notice('GPU đang được dùng hết, vui lòng thử lại sau.'), const SizedBox(height: 32)], Text('Chọn gói tài nguyên', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 18), PlanChoices(plans: servicePlans, selected: selectedPlanId, gpuName: gpuName, disabledReason: (p) => busy ? 'Đang cấp phát dịch vụ.' : osPlanReason(p, selectedOS), onSelect: (id) { if (!busy) setState(() => planId = id); }), if (servicePlans.isEmpty && !widget.state.loading) const Notice('Chưa có gói tài nguyên cho dịch vụ này. Hãy chọn dịch vụ khác hoặc quay lại sau.'), const SizedBox(height: 36), ConstrainedBox(constraints: const BoxConstraints(maxWidth: 760), child: Form(key: form, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [if (service == 'webapp') ...[TextFormField(controller: repo, enabled: !busy, autovalidateMode: AutovalidateMode.onUserInteraction, keyboardType: TextInputType.url, maxLength: 300, decoration: const InputDecoration(labelText: 'Kho Git công khai', hintText: 'https://github.com/ten/ung-dung.git', helperText: 'Dùng HTTPS, không kèm tài khoản hoặc mật khẩu.'), validator: validateRepo), const SizedBox(height: 24), TextFormField(controller: branch, enabled: !busy, decoration: const InputDecoration(labelText: 'Nhánh Git'), validator: (v) => RegExp(r'^[A-Za-z0-9._/-]{1,100}$').hasMatch(v ?? '') ? null : 'Nhánh chỉ gồm chữ, số và các dấu . _ / -; tối đa 100 ký tự.'), const SizedBox(height: 24)], Row(children: [const Icon(Icons.key_outlined, size: 20), const SizedBox(width: 10), Expanded(child: Text(loginSummary, key: const ValueKey('login-summary')))]), const SizedBox(height: 12), Theme(data: Theme.of(context).copyWith(dividerColor: Colors.transparent), child: ExpansionTile(key: const ValueKey('advanced-options'), initiallyExpanded: advanced, onExpansionChanged: (v) => advanced = v, tilePadding: EdgeInsets.zero, childrenPadding: const EdgeInsets.only(bottom: 12), expandedCrossAxisAlignment: CrossAxisAlignment.start, title: const Text('Tùy chọn nâng cao'), subtitle: const Text('Không bắt buộc: đặt tên máy, thêm khóa SSH', style: TextStyle(fontSize: 12)), children: [TextFormField(key: const ValueKey('advanced-name'), controller: name, enabled: !busy, inputFormatters: [FilteringTextInputFormatter.allow(RegExp('[a-z0-9-]')), LengthLimitingTextInputFormatter(63)], decoration: const InputDecoration(labelText: 'Tên máy', helperText: 'Để trống: hệ thống tự đặt theo tên tài khoản.', hintText: 'may-chu-cua-toi'), validator: (v) => (v ?? '').isEmpty || RegExp(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$').hasMatch(v!) ? null : 'Tên máy gồm chữ thường, số, gạch nối; bắt đầu và kết thúc bằng chữ hoặc số.'), if (!windows) ...[const SizedBox(height: 20), TextFormField(key: const ValueKey('advanced-ssh'), controller: ssh, enabled: !busy, minLines: 2, maxLines: 4, decoration: const InputDecoration(labelText: 'Khóa SSH công khai', helperText: 'Thêm nếu muốn đăng nhập bằng khóa. Tuyệt đối không dán khóa riêng.', hintText: 'ssh-ed25519 AAAA…'), validator: validateKey)]])), const SizedBox(height: 20), const Notice('Ví cần đủ số dư cho một giờ trước khi tạo. Máy đang tắt không phát sinh kỳ mới; phần giờ đã trả không hoàn lại.'), FilledButton.icon(key: const ValueKey('create-submit'), onPressed: ready ? create : null, icon: const Icon(Icons.add_circle_outline), label: Text(busy ? 'Đang cấp phát, vui lòng chờ…' : 'Tạo dịch vụ'))])))]);
  });
}
