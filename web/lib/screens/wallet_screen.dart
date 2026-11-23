// Nguyễn Tâm Bình - 2324801030003
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../api/api_client.dart';
import '../api/browser.dart';
import '../api/cloud_state.dart';
import '../qr/qr_view.dart';
import '../theme/cloud_theme.dart';
import '../widgets/common.dart';

class WalletScreen extends StatefulWidget {
  final CloudState state;
  final String? orderCode;
  const WalletScreen({super.key, required this.state, this.orderCode});
  @override
  State<WalletScreen> createState() => _WalletScreenState();
}
class _WalletScreenState extends State<WalletScreen> {
  final amount = TextEditingController(text: '50000');
  final form = GlobalKey<FormState>();
  List<Json> transactions = [], orders = [];
  Json? active;
  String? error, pollError, historyError;
  bool busy = false, historyLoading = false;
  int? pollingGeneration;
  int transactionOffset = 0, orderOffset = 0, generation = 0;
  Timer? timer;
  @override
  void initState() { super.initState(); loadHistory(); if (widget.orderCode != null && RegExp(r'^\d+$').hasMatch(widget.orderCode!)) resume(widget.orderCode!); }
  @override
  void dispose() { generation++; timer?.cancel(); amount.dispose(); super.dispose(); }
  Future<void> loadHistory() async {
    setState(() { historyLoading = true; historyError = null; });
    await Future.wait([() async { try { final data = await widget.state.api.list('/billing/transactions?offset=$transactionOffset&limit=20'); if (mounted) setState(() => transactions = data); } catch (e) { if (mounted) setState(() => historyError = e.toString()); } }(), () async { try { final data = await widget.state.api.list('/billing/payos?offset=$orderOffset&limit=20'); if (mounted) setState(() => orders = data); } catch (e) { if (mounted) setState(() => historyError = e.toString()); } }()]);
    if (mounted) setState(() => historyLoading = false);
  }
  Future<void> createOrder() async {
    if (!form.currentState!.validate() || busy) return;
    generation++;
    setState(() { busy = true; error = null; pollError = null; });
    try { final data = await widget.state.api.post('/billing/payos', {'amount': int.parse(amount.text)}); if (mounted) { setState(() => active = data); openCheckout('${data['checkout_url']}'); startPolling(); await loadHistory(); } } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  Future<void> resume(String code) async {
    final ticket = ++generation;
    timer?.cancel();
    setState(() { busy = true; error = null; pollError = null; });
    try { final data = await widget.state.api.get('/billing/payos/$code'); if (mounted && ticket == generation) { setState(() => active = data); if (data['status'] == 'pending') startPolling(); if (data['status'] == 'paid') await widget.state.refresh(); } } catch (e) { if (mounted && ticket == generation) { setState(() => error = e.toString()); if (active?['status'] == 'pending') startPolling(); } }
    if (mounted && ticket == generation) setState(() => busy = false);
  }
  void startPolling() { timer?.cancel(); timer = Timer.periodic(const Duration(seconds: 3), (_) => poll()); }
  Future<void> poll() async {
    if (busy || pollingGeneration == generation || active == null || active!['status'] != 'pending') return;
    final ticket = generation;
    pollingGeneration = ticket;
    final code = active!['order_code'];
    try {
      final data = await widget.state.api.get('/billing/payos/$code');
      if (!mounted || ticket != generation || active?['order_code'] != code) return;
      setState(() { active = data; pollError = null; });
      if (data['status'] != 'pending') {
        timer?.cancel();
        await widget.state.refresh(); await loadHistory();
        if (mounted) message(context, data['status'] == 'paid' ? 'Thanh toán thành công. Tiền đã được cộng vào ví.' : 'Đơn nạp tiền ${stateName(data['status']).toLowerCase()}.');
      }
    } catch (e) { if (mounted && ticket == generation) setState(() => pollError = e.toString()); } finally { if (pollingGeneration == ticket) pollingGeneration = null; }
  }
  Future<void> cancel() async {
    if (busy || active?['status'] != 'pending') return;
    if (!await confirm(context, 'Hủy đơn nạp', 'Đơn chưa thanh toán sẽ bị hủy. Nếu ngân hàng đã xác nhận thanh toán, hệ thống vẫn đối soát và cộng tiền vào ví.')) return;
    if (!mounted) return;
    generation++;
    timer?.cancel();
    setState(() { busy = true; error = null; });
    try {
      final data = await widget.state.api.post('/billing/payos/${active!['order_code']}/cancel', {'cancellationReason': 'Khách hàng hủy đơn nạp tiền'});
      if (mounted) { setState(() => active = data); if (data['status'] != 'pending') timer?.cancel(); await widget.state.refresh(); await loadHistory(); if (mounted) message(context, data['status'] == 'paid' ? 'Đơn đã thanh toán. Ví đã được cập nhật.' : 'Đã hủy đơn nạp.'); }
    } catch (e) { if (mounted) { setState(() => error = e.toString()); if (active?['status'] == 'pending') startPolling(); } }
    if (mounted) setState(() => busy = false);
  }
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: widget.state, builder: (context, _) => PageBody(children: [const Heading('Ví của bạn', 'Biết còn bao nhiêu giờ chạy trước khi bắt đầu việc tiếp theo.'), Wrap(spacing: 56, runSpacing: 20, children: [Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('SỐ DƯ', style: figures.copyWith(fontSize: 18)), Text(money(widget.state.balance), style: Theme.of(context).textTheme.displayLarge)]), Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('THỜI GIAN CÒN LẠI', style: figures.copyWith(fontSize: 18)), Text(widget.state.hours == null ? 'Chưa có máy đang chạy' : 'Khoảng ${widget.state.hours!.floor()} giờ', style: Theme.of(context).textTheme.headlineLarge), Text('Tổng giá đang chạy: ${money(widget.state.hourly)} / giờ')])]), const SizedBox(height: 24), if (widget.state.hours != null && widget.state.hours! < 24) const Notice('Ví còn dưới 24 giờ chạy. Nạp thêm để máy chủ không bị tạm dừng khi hết số dư.'), if (error != null) Notice(error!), const SizedBox(height: 12), LayoutBuilder(builder: (context, c) {
    final inputs = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Nạp tiền qua payOS', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12), const Text('Bấm thanh toán để chuyển sang trang payOS. Trả xong hoặc bấm hủy, payOS tự đưa bạn về đây và số dư được cập nhật.'), const SizedBox(height: 20), Wrap(spacing: 8, runSpacing: 10, children: [for (final n in [20000, 50000, 100000, 200000]) ChoiceChip(label: Text(money(n)), selected: amount.text == '$n', onSelected: busy || active?['status'] == 'pending' ? null : (_) => setState(() => amount.text = '$n'))]), const SizedBox(height: 20), Form(key: form, child: TextFormField(controller: amount, enabled: !busy && active?['status'] != 'pending', keyboardType: TextInputType.number, inputFormatters: [FilteringTextInputFormatter.digitsOnly], onChanged: (_) => setState(() {}), decoration: const InputDecoration(labelText: 'Số tiền nạp', suffixText: 'đ', helperText: 'Từ 10.000đ đến 5.000.000đ.'), validator: (v) { final n = int.tryParse(v ?? ''); return n != null && n >= 10000 && n <= 5000000 ? null : 'Nhập số tiền từ 10.000đ đến 5.000.000đ.'; })), const SizedBox(height: 20), FilledButton.icon(onPressed: busy || active?['status'] == 'pending' ? null : createOrder, icon: const Icon(Icons.open_in_new_outlined), label: Text(busy ? 'Đang chuyển sang payOS…' : 'Thanh toán qua payOS'))]);
    final payment = active == null ? const Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(Icons.qr_code_2_outlined, size: 48), SizedBox(height: 16), Text('Mã thanh toán sẽ xuất hiện tại đây.'), SizedBox(height: 8), Text('Chọn số tiền rồi tạo mã. Mỗi đơn có mã riêng để đối soát chính xác.')])) : Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(stateName(active!['status']), style: Theme.of(context).textTheme.headlineMedium), DescriptionRow('Mã đơn', '${active!['order_code']}'), DescriptionRow('Số tiền', money(active!['amount'])), if (active!['status'] == 'pending') ...[const SizedBox(height: 16), Center(child: QrView('${active!['qr_code']}')), const SizedBox(height: 12), const Text('Đang tự kiểm tra thanh toán mỗi 3 giây.', style: TextStyle(fontSize: 12)), if (pollError != null) Notice(pollError!, retry: poll), const SizedBox(height: 12), Wrap(spacing: 8, runSpacing: 8, children: [FilledButton.icon(onPressed: () => openCheckout('${active!['checkout_url']}'), icon: const Icon(Icons.open_in_new_outlined), label: const Text('Mở lại trang payOS')), OutlinedButton(onPressed: busy ? null : cancel, child: const Text('Hủy đơn'))])] else if (active!['status'] == 'paid') const Padding(padding: EdgeInsets.only(top: 20), child: Text('Thanh toán thành công. Số dư đã được cập nhật.'))]));
    return c.maxWidth < 850 ? Column(children: [inputs, const SizedBox(height: 28), payment]) : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: inputs), const SizedBox(width: 56), Expanded(child: payment)]);
  }), const SizedBox(height: 44), Text('Giao dịch trong ví', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12), if (historyLoading) const LinearProgressIndicator(), if (historyError != null) Notice(historyError!, retry: loadHistory), if (!historyLoading && transactions.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 20), child: Text('Chưa có giao dịch trong trang này.')), for (final t in transactions) ListTile(contentPadding: const EdgeInsets.symmetric(vertical: 8), leading: Icon(t['kind'] == 'topup' ? Icons.south_west_outlined : Icons.north_east_outlined), title: Text(t['kind'] == 'topup' ? 'Nạp tiền vào ví' : 'Thanh toán sử dụng VPS'), subtitle: Text('${date(t['created_at'])}${t['instance_id'] == null ? '' : ' · Máy chủ ${t['instance_id']}'}'), trailing: Text('${number(t['amount']) > 0 ? '+' : ''}${money(t['amount'])}', style: figures.copyWith(fontSize: 25))), _pagination(transactionOffset, transactions.length, (offset) { transactionOffset = offset; loadHistory(); }), const SizedBox(height: 36), Text('Đơn nạp tiền', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12), if (!historyLoading && orders.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 20), child: Text('Chưa có đơn nạp trong trang này.')), for (final order in orders) ListTile(minVerticalPadding: 16, contentPadding: EdgeInsets.zero, title: Text('Đơn ${order['order_code']} · ${money(order['amount'])}'), subtitle: Text(stateName(order['status'])), trailing: OutlinedButton(onPressed: busy ? null : () => resume('${order['order_code']}'), child: const Text('Xem đơn'))), _pagination(orderOffset, orders.length, (offset) { orderOffset = offset; loadHistory(); })]));
  Widget _pagination(int offset, int count, ValueChanged<int> change) => Wrap(spacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: [OutlinedButton(onPressed: historyLoading || offset == 0 ? null : () => change(offset - 20), child: const Text('Trang trước')), Text('Trang ${offset ~/ 20 + 1}'), OutlinedButton(onPressed: historyLoading || count < 20 ? null : () => change(offset + 20), child: const Text('Trang sau'))]);
}

class PaymentResultScreen extends StatefulWidget {
  final CloudState state;
  final String? orderCode;
  const PaymentResultScreen({super.key, required this.state, this.orderCode});
  @override
  State<PaymentResultScreen> createState() => _PaymentResultScreenState();
}
class _PaymentResultScreenState extends State<PaymentResultScreen> {
  String text = 'Đang kiểm tra trạng thái thanh toán với payOS…';
  bool busy = true;
  Timer? redirect;
  @override
  void initState() { super.initState(); check(); }
  @override
  void dispose() { redirect?.cancel(); super.dispose(); }
  Future<void> check() async {
    setState(() => busy = true);
    try {
      if (widget.orderCode == null || !RegExp(r'^\d+$').hasMatch(widget.orderCode!)) throw const ApiException('Không tìm thấy mã đơn trong đường dẫn. Hãy xem lại đơn trong Ví.');
      final order = await widget.state.api.get('/billing/payos/${widget.orderCode}');
      await widget.state.refresh();
      if (mounted) { setState(() => text = '${stateName(order['status'])}. Đang trở về Ví…'); redirect = Timer(const Duration(seconds: 2), () { if (mounted) context.go('/vi?orderCode=${widget.orderCode}'); }); }
    } catch (e) { if (mounted) setState(() => text = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  @override
  Widget build(BuildContext context) => PageBody(children: [const Heading('Kết quả thanh toán', 'Trạng thái được xác minh từ máy chủ, không dựa vào nội dung đường dẫn.'), if (busy) const LinearProgressIndicator(), const SizedBox(height: 24), Text(text), const SizedBox(height: 24), Wrap(spacing: 12, children: [FilledButton(onPressed: () => context.go('/vi'), child: const Text('Về Ví')), OutlinedButton(onPressed: busy ? null : check, child: const Text('Kiểm tra lại'))])]);
}
