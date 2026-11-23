// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../theme/cloud_theme.dart';
import '../widgets/brand_logo.dart';
import '../widgets/header_tools.dart';
import '../widgets/layer_tour.dart';
import '../widgets/common.dart';

class LandingScreen extends StatefulWidget {
  final ApiClient api;
  final CloudState? state;
  const LandingScreen({super.key, required this.api, this.state});
  @override
  State<LandingScreen> createState() => _LandingScreenState();
}
class _LandingScreenState extends State<LandingScreen> {
  List<Json> plans = [], osImages = [];
  Json gpu = {};
  bool loading = true;
  String? priceError, osError, need;
  final choicesKey = GlobalKey(), tourKey = GlobalKey();
  @override
  void initState() { super.initState(); widget.state?.addListener(sessionChanged); load(); }
  void sessionChanged() { if (mounted) setState(() {}); }
  @override
  void didUpdateWidget(LandingScreen oldWidget) { super.didUpdateWidget(oldWidget); if (oldWidget.state != widget.state) { oldWidget.state?.removeListener(sessionChanged); widget.state?.addListener(sessionChanged); } }
  @override
  void dispose() { widget.state?.removeListener(sessionChanged); super.dispose(); }
  Future<void> load() async {
    if (mounted) setState(() { loading = true; priceError = null; osError = null; });
    await Future.wait([() async { try { final data = await widget.api.get('/public/gpu'); if (mounted) setState(() => gpu = data); } catch (_) {} }(), () async { try { final data = await widget.api.list('/plans', authenticated: false); if (mounted) setState(() => plans = data); } catch (e) { if (mounted) setState(() => priceError = e.toString()); } }(), () async { try { final data = await widget.api.list('/os', authenticated: false); if (mounted) setState(() => osImages = data); } catch (_) { if (mounted) setState(() => osError = 'Chưa lấy được danh sách hệ điều hành. Hãy thử lại.'); } }()]);
    if (mounted) setState(() => loading = false);
  }
  void pick(String value) { setState(() => need = value); WidgetsBinding.instance.addPostFrameCallback((_) { if (mounted && choicesKey.currentContext != null) Scrollable.ensureVisible(choicesKey.currentContext!, duration: MediaQuery.disableAnimationsOf(context) ? Duration.zero : const Duration(milliseconds: 300)); }); }
  List<TourLayer> get tourLayers {
    final ready = osImages.where((os) => os['san_sang'] == true && os['chi_gpu'] != true).map((os) => '${os['ten']}').toList();
    final gpuNames = ((gpu['loai'] as List?) ?? const []).join(', ');
    int count(String service) => plans.where((p) => (p['dich_vu'] ?? 'vps') == service && number(p['gpu'] ?? 0) == 0).length;
    return [
      const TourLayer('Máy cá nhân', 'Tài nguyên đến từ máy tính của các thành viên', 'Mỗi máy tính cá nhân cài Proxmox VE và trở thành một node. Node góp CPU, RAM, ổ đĩa và cả GPU vào kho chung; máy ảo chạy bằng KVM nên mỗi khách có hệ điều hành riêng, tách biệt với nhau.', ['Mỗi node là một Proxmox VE độc lập, đặt ở nhiều nơi khác nhau', 'Hệ thống tự chọn node còn đủ tài nguyên khi bạn tạo máy', 'Máy ảo tự bật lại khi node khởi động lại']),
      const TourLayer('Mạng kết nối', 'Một mạng riêng nối các máy ở nhiều nơi', 'Các node nối với nhau bằng WireGuard do Headscale điều phối, nên vẫn chạy được sau CGNAT của nhà mạng. Trạm chuyển tiếp có IP công cộng đưa SSH và dịch vụ ra Internet; mỗi VPS Linux còn có IPv6 công cộng riêng.', ['Mạng riêng mã hóa giữa các node', 'SSH từ mọi nơi qua IP công cộng của trạm chuyển tiếp', 'IPv6 riêng: ssh root@<IPv6>, cổng 22, mở mọi cổng']),
      TourLayer('IaaS · Hạ tầng', 'Máy chủ ảo và máy chủ AI, toàn quyền root', 'Bạn nhận một máy chủ riêng để cài gì cũng được. Chọn hệ điều hành, chọn gói rồi bấm tạo; tài khoản root và mật khẩu được đặt sẵn, đổi được bất cứ lúc nào.', [ready.isEmpty ? 'Nhiều hệ điều hành Linux và Windows' : '${ready.length} hệ điều hành: ${ready.join(', ')}', gpuNames.isEmpty ? 'Máy chủ AI có GPU NVIDIA, dựng sẵn CUDA, PyTorch, JupyterLab' : 'Máy chủ AI có GPU $gpuNames, dựng sẵn CUDA, PyTorch, JupyterLab', 'Cài lại, đổi hệ điều hành hoặc đổi gói ngay trên web'], action: 'Xem gói máy chủ ảo', onAction: () => pick('vps')),
      TourLayer('PaaS · Nền tảng', 'Dịch vụ dựng sẵn, chỉ việc dùng', 'Không cần tự cài đặt máy chủ: tạo cơ sở dữ liệu PostgreSQL hoặc đưa ứng dụng web từ kho Git lên chạy, hệ thống tự cấp cổng và chuỗi kết nối.', ['${count('postgres') == 0 ? 'Cơ sở dữ liệu' : '${count('postgres')} gói cơ sở dữ liệu'} PostgreSQL có chuỗi kết nối sẵn', '${count('webapp') == 0 ? 'Ứng dụng web' : '${count('webapp')} gói ứng dụng web'} triển khai từ kho Git công khai', 'Mỗi dịch vụ một cổng riêng, mở được từ Internet'], action: 'Xem gói dịch vụ nền tảng', onAction: () => pick('postgres')),
      TourLayer('Cổng tự phục vụ', 'Tự tạo, tự quản lý, trả theo giờ', 'Mọi thao tác nằm trên web: tạo máy, bật tắt, console ngay trong trình duyệt, xem tài nguyên. Ví nạp qua payOS, mỗi giờ chạy trừ đúng giá gói; máy tắt không phát sinh kỳ mới.', ['Tạo máy một bước, tên và mật khẩu đặt sẵn', 'Nạp tiền bằng chuyển khoản qua payOS', 'Theo dõi CPU, RAM và chi phí của từng máy'], action: widget.state?.signedIn == true ? 'Vào trang máy chủ' : 'Tạo tài khoản', onAction: begin),
    ];
  }
  void begin() => context.go(widget.state?.admin == true ? '/quan-tri' : widget.state?.signedIn == true ? '/tao-vps' : '/dang-ky');
  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final state = widget.state;
    final mobile = width < 700;
    final intro = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Máy cá nhân.\nĐám mây chung.', style: mobile ? Theme.of(context).textTheme.displayMedium : Theme.of(context).textTheme.displayLarge), const SizedBox(height: 24), const Text('TBT Cloud kết nối máy tính cá nhân của các thành viên thành nền tảng máy chủ ảo và dịch vụ ứng dụng.', style: TextStyle(fontSize: 17, height: 1.7)), const SizedBox(height: 12), const Text('Tự tạo, tự quản lý. Trả theo từng giờ sử dụng.'), const SizedBox(height: 24), Wrap(spacing: 12, runSpacing: 12, children: [FilledButton(onPressed: begin, child: Text(state?.admin == true ? 'Mở quản trị' : 'Bắt đầu')), OutlinedButton(key: const ValueKey('explore-tour'), onPressed: () => Scrollable.ensureVisible(tourKey.currentContext!, duration: MediaQuery.disableAnimationsOf(context) ? Duration.zero : const Duration(milliseconds: 250)), child: const Text('Khám phá dịch vụ'))])]);
    final header = Row(children: [InkWell(onTap: () => context.go('/'), child: BrandLogo(compact: width < 430)), const Spacer(), if (widget.state != null) ThemeButton(state: widget.state!), if (state?.signedIn == true) ...[NotificationBell(state: widget.state!), if (state?.admin != true) TextButton(onPressed: () => context.go('/vi'), child: Text(money(state!.balance), style: figures.copyWith(fontSize: 24))), IconButton(key: const ValueKey('public-account'), tooltip: 'Tài khoản', onPressed: () => context.go(state?.admin == true ? '/quan-tri' : '/may-chu'), icon: const Icon(Icons.account_circle_outlined))] else ...[TextButton(onPressed: () => context.go('/dang-nhap'), child: const Text('Đăng nhập')), const SizedBox(width: 8), FilledButton(key: const ValueKey('public-account'), onPressed: () => context.go('/dang-ky'), child: const Text('Đăng ký'))]]);
    return Scaffold(appBar: PreferredSize(preferredSize: const Size.fromHeight(82), child: SafeArea(child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1440), child: Padding(padding: EdgeInsets.symmetric(horizontal: mobile ? 20 : 40), child: SizedBox(height: 82, child: header)))))), body: PageBody(children: [LayoutBuilder(builder: (context, c) => c.maxWidth < 850 ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [intro, const SizedBox(height: 20), const SizedBox(height: 240, child: Center(child: BrandHero()))]) : Row(children: [Expanded(flex: 6, child: intro), const SizedBox(width: 48), const Expanded(flex: 5, child: BrandHero())])), const SizedBox(height: 48), const Divider(), const SizedBox(height: 32), Heading('Khám phá dịch vụ', 'Đi qua từng tầng của TBT Cloud, từ máy cá nhân dưới cùng tới dịch vụ bạn dùng.', key: tourKey), LayerTour(layers: tourLayers), const SizedBox(height: 48), const Divider(), const SizedBox(height: 32), Heading('Bạn cần gì?', 'Chọn một nhu cầu để xem gói phù hợp. Chỉ trả cho thời gian dịch vụ chạy.', key: choicesKey), Wrap(spacing: 12, runSpacing: 12, children: [for (final choice in const [('vps', 'Máy chủ ảo VPS'), ('postgres', 'Cơ sở dữ liệu PostgreSQL'), ('webapp', 'Ứng dụng web'), ('ai', 'Máy chủ AI (GPU)'), ('all', 'Xem tất cả')]) ChoiceChip(key: ValueKey('need-${choice.$1}'), label: Text(choice.$2), selected: need == choice.$1, onSelected: (_) => setState(() => need = choice.$1))]), const SizedBox(height: 24), if (loading) const LinearProgressIndicator(color: CloudColors.olive, minHeight: 3), if (priceError != null) Notice(priceError!, retry: load), if (need == null) const Padding(padding: EdgeInsets.symmetric(vertical: 24), child: Text('VPS cho môi trường riêng, PostgreSQL cho dữ liệu, ứng dụng web cho mã nguồn, máy chủ AI có GPU để huấn luyện mô hình.')), if (need != null) ...[const Heading('Bảng giá', 'Giá theo giờ; ước tính tháng dùng 720 giờ. Chi phí thực tế tùy thời gian chạy.'), for (final group in const [('vps', 'Máy chủ ảo', CloudColors.brown), ('postgres', 'Cơ sở dữ liệu PostgreSQL', CloudColors.mesh), ('webapp', 'Ứng dụng web', CloudColors.olive), ('ai', 'Máy chủ AI (GPU)', CloudColors.purple)]) if (need == 'all' || need == group.$1) ...[Row(children: [Container(width: 12, height: 12, decoration: BoxDecoration(color: group.$3, shape: BoxShape.circle)), const SizedBox(width: 12), Expanded(child: Text(group.$2, style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: Color.lerp(group.$3, Theme.of(context).colorScheme.onSurface, Theme.of(context).brightness == Brightness.dark ? .5 : .4))))]), const SizedBox(height: 18), if (group.$1 == 'vps') ...[Text('Hệ điều hành hỗ trợ', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 12), if (osError != null) Notice(osError!, retry: load) else if (!loading && !osImages.any((os) => os['san_sang'] == true)) const Text('Chưa có node sẵn sàng cho hệ điều hành VM.') else Wrap(spacing: 16, runSpacing: 12, children: [for (final os in osImages.where((os) => os['san_sang'] == true)) Text('${os['ten']} · ${os['ket_noi'] == 'rdp' ? 'RDP' : 'SSH'}')]), const SizedBox(height: 24)], if (group.$1 == 'ai') ...[Text('Ubuntu 24.04 + CUDA + PyTorch dựng sẵn, đăng nhập SSH, mở JupyterLab qua đường hầm SSH.'), const SizedBox(height: 8), Text(((gpu['loai'] as List?) ?? const []).isEmpty ? 'Chưa có GPU sẵn sàng.' : 'GPU ${((gpu['loai'] as List?) ?? const []).join(', ')} · còn rảnh ${number(gpu['ranh']).toInt()}/${number(gpu['tong']).toInt()}', key: const ValueKey('landing-gpu')), const SizedBox(height: 24)], if (!loading && priceError == null && plansForService(plans, group.$1).isEmpty) const Notice('Chưa có gói cho dịch vụ này. Hãy quay lại sau.'), PlanChoices(plans: plansForService(plans, group.$1), tiers: true, onSelect: (_) => begin()), const SizedBox(height: 40)]], const SizedBox(height: 40), const Heading('Hạ tầng của các thành viên', 'Mỗi máy cá nhân là một node độc lập. Mạng phủ kết nối các node; Control API điều phối dịch vụ và tính phí.'), const Text('Máy chủ ảo VPS · PostgreSQL · Ứng dụng web từ Git'), const SizedBox(height: 40), const Divider(), const Padding(padding: EdgeInsets.symmetric(vertical: 24), child: Wrap(spacing: 32, runSpacing: 12, children: [BrandLogo(), Text('Máy cá nhân · Tự phục vụ · Tính tiền theo giờ')]))]));
  }
}
