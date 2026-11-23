// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import 'api_client.dart';
import 'browser.dart';

String serviceName(dynamic value) => switch (value) { 'postgres' => 'Cơ sở dữ liệu PostgreSQL', 'webapp' => 'Ứng dụng web từ Git', 'ai' => 'Máy chủ AI (GPU)', _ => 'Máy chủ ảo VPS' };
bool hasGpu(Json plan) => number(plan['gpu'] ?? 0) > 0;

double number(dynamic value) => double.tryParse('$value') ?? 0;

List<Json> plansForService(List<Json> plans, String service) => plans.where((plan) => service == 'ai' ? (plan['dich_vu'] ?? 'vps') == 'vps' && hasGpu(plan) : (plan['dich_vu'] ?? 'vps') == service && !hasGpu(plan)).toList()..sort((a, b) { final price = number(a['gia_theo_gio']).compareTo(number(b['gia_theo_gio'])); return price != 0 ? price : (a['id'] as int).compareTo(b['id'] as int); });

String? osPlanReason(Json plan, Json? os) {
  if (os == null) return null;
  if (number(plan['ram_mb']) < number(os['min_ram_mb'])) return 'Cần ít nhất ${os['min_ram_mb']} MB RAM cho ${os['ten']}.';
  if (number(plan['disk_gb']) < number(os['min_disk_gb'])) return 'Cần ít nhất ${os['min_disk_gb']} GB ổ đĩa cho ${os['ten']}.';
  return null;
}

class CloudState extends ChangeNotifier {
  final ApiClient api;
  Json? user;
  List<Json> instances = [], nodes = [], plans = [], osImages = [];
  Json gpu = {};
  double balance = 0;
  ThemeMode themeMode = switch (readPref('theme')) { 'light' => ThemeMode.light, 'dark' => ThemeMode.dark, _ => ThemeMode.system };
  List<Json> notifications = [];
  int unread = 0;
  void setTheme(ThemeMode mode) { themeMode = mode; writePref('theme', mode.name); notifyListeners(); }
  Future<void> loadNotifications() async { try { final data = await api.get('/notifications?limit=30'); notifications = [for (final item in (data['items'] as List? ?? const [])) Map<String, dynamic>.from(item as Map)]; unread = (data['chua_doc'] as num?)?.toInt() ?? 0; notifyListeners(); } catch (_) {} }
  Future<void> markNotificationsRead() async { if (unread == 0) return; try { await api.post('/notifications/read', {}); unread = 0; notifyListeners(); } catch (_) {} }
  bool loading = false;
  String? error;
  Future<void>? _pending;
  int _session = 0;
  CloudState(this.api);
  bool get signedIn => api.token != null;
  bool get admin => user?['role'] == 'admin';
  List<Json> get myInstances => instances.where((v) => v['user_id'] == user?['id']).toList();
  double get hourly => myInstances.where((v) => v['trang_thai'] == 'running').fold(0, (sum, v) => sum + number(v['gia_theo_gio']));
  double? get hours => hourly > 0 ? balance / hourly : null;
  String nodeName(dynamic id) => nodes.where((n) => n['id'] == id).map((n) => '${n['ten']}').firstOrNull ?? 'Node $id';
  Json? planOf(dynamic id) => plans.where((p) => p['id'] == id).firstOrNull;
  String specs(Json v) { final gpu = number(planOf(v['plan_id'])?['gpu']).toInt(); final names = ((this.gpu['loai'] as List?) ?? const []).join(', '); return '${gpu > 0 ? '$gpu × ${names.isEmpty ? 'GPU NVIDIA' : names} · ' : ''}${v['vcpu']} vCPU · ${v['ram_mb']} MB RAM · ${v['disk_gb']} GB'; }
  String planName(dynamic id) => plans.where((p) => p['id'] == id).map((p) => '${p['ten']}').firstOrNull ?? 'Gói $id';

  Future<void> login(String email, String password) async {
    final body = {'email': email.trim().toLowerCase(), 'password': password};
    final data = await api.request('/auth/login', method: 'POST', body: body, authenticated: false);
    await _acceptToken(data);
  }
  Future<Json> register(Json body) async => Map<String, dynamic>.from(await api.request('/auth/register', method: 'POST', body: body, authenticated: false) as Map);
  Future<Json> resendRegistration(String email) async => Map<String, dynamic>.from(await api.request('/auth/register/resend', method: 'POST', body: {'email': email}, authenticated: false) as Map);
  Future<void> verifyRegistration(String email, String code) async {
    final data = await api.request('/auth/register/verify', method: 'POST', body: {'email': email, 'code': code}, authenticated: false);
    await _acceptToken(data);
  }
  Future<void> _acceptToken(dynamic data) async {
    _session++;
    _pending = null;
    user = null; instances = []; nodes = []; plans = []; osImages = []; gpu = {}; balance = 0; notifications = []; unread = 0;
    api.token = data['access_token'] as String;
    writeToken(api.token);
    await refresh();
  }
  Future<void> refresh() {
    if (_pending != null) return _pending!;
    final session = _session;
    return _pending = _refresh(session).whenComplete(() { if (session == _session) _pending = null; });
  }
  Future<void> _refresh(int session) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final me = await api.get('/auth/me');
      if (session != _session) return;
      user = me;
      final result = await Future.wait<dynamic>([api.all('/instances'), admin ? api.list('/nodes/map') : Future.value(<Json>[]), api.list('/plans'), admin ? Future.value({'balance': 0}) : api.get('/billing/balance'), api.list('/os', authenticated: false), api.get('/public/gpu').catchError((_) => <String, dynamic>{})]);
      if (session != _session) return;
      instances = result[0] as List<Json>;
      nodes = result[1] as List<Json>;
      plans = result[2] as List<Json>;
      balance = number(result[3]['balance']);
      osImages = result[4] as List<Json>;
      gpu = result[5] as Json;
      await loadNotifications();
    } catch (e) { if (session != _session) return; error = e.toString(); }
    loading = false;
    notifyListeners();
  }
  void logout() {
    _session++;
    _pending = null;
    api.token = null;
    writeToken(null);
    user = null;
    instances = []; nodes = []; plans = []; osImages = []; gpu = {}; balance = 0; notifications = []; unread = 0;
    error = null; loading = false;
    notifyListeners();
  }
}
