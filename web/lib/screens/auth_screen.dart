// Nguyễn Tâm Bình - 2324801030003
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../widgets/brand_logo.dart';
import '../api/api_client.dart';
import '../api/cloud_state.dart';
import '../widgets/common.dart';

class AuthScreen extends StatefulWidget {
  final CloudState state;
  final bool register;
  final String? next;
  const AuthScreen({super.key, required this.state, this.register = false, this.next});
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}
class _AuthScreenState extends State<AuthScreen> {
  final form = GlobalKey<FormState>(), codeForm = GlobalKey<FormState>();
  final fullName = TextEditingController(), username = TextEditingController(), email = TextEditingController(), password = TextEditingController(), repeat = TextEditingController(), code = TextEditingController();
  final codeFocus = FocusNode();
  bool hidden = true, hiddenRepeat = true, busy = false, verifying = false;
  int resendIn = 0;
  Timer? countdown;
  String? error, emailError, usernameError, codeError;
  String pendingEmail = '', maskedEmail = '';
  @override
  void dispose() { countdown?.cancel(); codeFocus.dispose(); fullName.dispose(); username.dispose(); email.dispose(); password.dispose(); repeat.dispose(); code.dispose(); super.dispose(); }
  void startCountdown(int seconds) {
    countdown?.cancel();
    resendIn = seconds;
    countdown = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted || resendIn <= 1) { timer.cancel(); if (mounted) setState(() => resendIn = 0); return; }
      setState(() => resendIn--);
    });
  }
  String? validatePassword(String? value) {
    if (!widget.register) return value != null && value.isNotEmpty ? null : 'Nhập mật khẩu.';
    if (value == null || value.runes.length < 8 || value.runes.length > 128) return 'Mật khẩu cần từ 8 đến 128 ký tự.';
    if (RegExp(r'\s', unicode: true).hasMatch(value) || !RegExp(r'\p{Lu}', unicode: true).hasMatch(value) || !RegExp(r'\p{Ll}', unicode: true).hasMatch(value) || !RegExp(r'[0-9]').hasMatch(value) || !RegExp(r'[^\p{L}\p{N}\s]', unicode: true).hasMatch(value)) return 'Cần chữ hoa, chữ thường, số, ký tự đặc biệt; không có khoảng trắng.';
    return null;
  }
  String? validateEmail(String? value) {
    final address = value?.trim() ?? '', parts = address.split('@');
    if (address.length > 254 || parts.length != 2) return 'Nhập địa chỉ email hợp lệ.';
    final local = parts[0], labels = parts[1].split('.');
    if (local.isEmpty || local.length > 64 || local.startsWith('.') || local.endsWith('.') || local.contains('..') || RegExp(r'''[^\p{L}\p{N}!#$%&'*+/=?^_`{|}~.-]''', unicode: true).hasMatch(local) || labels.length < 2 || labels.any((label) => !RegExp(r'^[\p{L}\p{N}](?:[\p{L}\p{N}-]{0,61}[\p{L}\p{N}])?$', unicode: true).hasMatch(label)) || !RegExp(r'\p{L}', unicode: true).hasMatch(labels.last)) return 'Nhập địa chỉ email hợp lệ.';
    return null;
  }
  void enterVerification(Json result) {
    setState(() {
      verifying = true; maskedEmail = result['email_masked'] as String; error = null; codeError = null; code.clear(); password.clear(); repeat.clear();
      hidden = true; hiddenRepeat = true; startCountdown((result['resend_after'] as num?)?.toInt() ?? 60);
    });
    WidgetsBinding.instance.addPostFrameCallback((_) { if (mounted) codeFocus.requestFocus(); });
  }
  Future<void> submit() async {
    if (busy || !form.currentState!.validate()) return;
    setState(() { busy = true; error = null; emailError = null; usernameError = null; });
    try {
      if (widget.register) {
        final address = email.text.trim().toLowerCase();
        final result = await widget.state.register({'ho_ten': fullName.text.trim(), 'username': username.text.toLowerCase(), 'password': password.text, 'password_confirm': repeat.text, 'email': address});
        if (mounted) { pendingEmail = address; enterVerification(result); }
      } else {
        await widget.state.login(email.text, password.text);
        if (mounted) context.go(widget.state.admin ? '/quan-tri' : widget.next != null && widget.next!.startsWith('/') && !widget.next!.startsWith('//') ? widget.next! : '/may-chu');
      }
    } catch (e) {
      if (mounted) { setState(() {
        final message = e.toString();
        if (widget.register && message.startsWith('Email đã')) { emailError = message; } else if (widget.register && message.startsWith('Tên tài khoản đã')) { usernameError = message; } else { error = message; }
      }); }
    }
    if (mounted) setState(() => busy = false);
  }
  Future<void> verify() async {
    if (busy || !codeForm.currentState!.validate()) return;
    setState(() { busy = true; error = null; codeError = null; });
    try {
      await widget.state.verifyRegistration(pendingEmail, code.text);
      if (mounted) { context.go('/may-chu'); }
    } catch (e) { if (mounted) setState(() => codeError = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  Future<void> resend() async {
    if (busy || resendIn > 0) return;
    setState(() { busy = true; error = null; });
    try {
      final result = await widget.state.resendRegistration(pendingEmail);
      if (mounted) enterVerification(result);
    } catch (e) { if (mounted) setState(() => error = e.toString()); }
    if (mounted) setState(() => busy = false);
  }
  void changeEmail() {
    countdown?.cancel();
    setState(() { verifying = false; error = null; codeError = null; password.clear(); repeat.clear(); code.clear(); hidden = true; hiddenRepeat = true; });
  }
  Widget passwordField({bool confirmation = false}) {
    final obscure = confirmation ? hiddenRepeat : hidden;
    return TextFormField(controller: confirmation ? repeat : password, enabled: !busy, obscureText: obscure, autocorrect: false, enableSuggestions: false, autofillHints: [widget.register ? AutofillHints.newPassword : AutofillHints.password], textInputAction: widget.register ? TextInputAction.next : TextInputAction.done, autovalidateMode: AutovalidateMode.onUserInteraction, decoration: InputDecoration(labelText: confirmation ? 'Xác nhận mật khẩu' : 'Mật khẩu', errorMaxLines: 3, suffixIcon: IconButton(tooltip: confirmation ? (obscure ? 'Hiện xác nhận mật khẩu' : 'Ẩn xác nhận mật khẩu') : (obscure ? 'Hiện mật khẩu' : 'Ẩn mật khẩu'), onPressed: busy ? null : () => setState(() { if (confirmation) { hiddenRepeat = !hiddenRepeat; } else { hidden = !hidden; } }), icon: Icon(obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined))), validator: confirmation ? (v) => v == password.text ? null : 'Xác nhận mật khẩu chưa khớp.' : validatePassword, onChanged: confirmation ? null : (_) { if (repeat.text.isNotEmpty) form.currentState?.validate(); }, onFieldSubmitted: (_) { if (!widget.register) submit(); });
  }
  Widget registrationForm() => Form(key: form, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(widget.register ? 'Đăng ký tài khoản' : 'Đăng nhập', style: Theme.of(context).textTheme.displayMedium), const SizedBox(height: 12), Text(widget.register ? 'Xác nhận email để tạo tài khoản, nạp ví và tự cấp máy chủ.' : 'Trở lại mạng máy chủ của bạn.'), const SizedBox(height: 32), if (error != null) Semantics(liveRegion: true, child: Notice(error!)),
    if (widget.register) ...[
      TextFormField(controller: fullName, autofocus: true, enabled: !busy, textCapitalization: TextCapitalization.words, autofillHints: const [AutofillHints.name], textInputAction: TextInputAction.next, autovalidateMode: AutovalidateMode.onUserInteraction, decoration: const InputDecoration(labelText: 'Họ và tên', errorMaxLines: 3), validator: (v) { final value = v?.trim() ?? ''; return value.runes.length >= 2 && value.runes.length <= 80 && RegExp(r'^(?:\p{L}\p{M}*| )+$', unicode: true).hasMatch(value) ? null : 'Họ tên cần 2 - 80 ký tự, chỉ gồm chữ và khoảng trắng.'; }), const SizedBox(height: 20),
      TextFormField(controller: username, enabled: !busy, autocorrect: false, enableSuggestions: false, autofillHints: const [AutofillHints.newUsername], textInputAction: TextInputAction.next, autovalidateMode: AutovalidateMode.onUserInteraction, decoration: InputDecoration(labelText: 'Tên tài khoản', helperText: '3 - 30 ký tự: a-z, 0-9, dấu chấm, gạch dưới; bắt đầu bằng chữ.', helperMaxLines: 3, errorText: usernameError, errorMaxLines: 3), onChanged: (_) { if (usernameError != null) setState(() => usernameError = null); }, validator: (v) => RegExp(r'^[a-z][a-z0-9._]{2,29}$').hasMatch((v ?? '').toLowerCase()) ? null : 'Tên tài khoản chưa đúng định dạng.'), const SizedBox(height: 20),
    ],
    if (!widget.register) ...[TextFormField(controller: email, autofocus: true, enabled: !busy, autofillHints: const [AutofillHints.username], textInputAction: TextInputAction.next, decoration: const InputDecoration(labelText: 'Tên tài khoản hoặc email', prefixIcon: Icon(Icons.person_outline)), validator: (v) => (v?.trim() ?? '').isNotEmpty ? null : 'Nhập tên tài khoản hoặc email.'), const SizedBox(height: 20)],
    passwordField(),
    if (widget.register) ...[const SizedBox(height: 8), const Text('Mật khẩu từ 8 đến 128 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt; không có khoảng trắng.'), const SizedBox(height: 20), passwordField(confirmation: true), const SizedBox(height: 20), TextFormField(controller: email, enabled: !busy, keyboardType: TextInputType.emailAddress, autofillHints: const [AutofillHints.email], textInputAction: TextInputAction.done, autovalidateMode: AutovalidateMode.onUserInteraction, decoration: InputDecoration(labelText: 'Gmail', errorText: emailError, errorMaxLines: 3), onChanged: (_) { if (emailError != null) setState(() => emailError = null); }, validator: validateEmail, onFieldSubmitted: (_) => submit())],
    const SizedBox(height: 28), SizedBox(width: double.infinity, child: FilledButton(onPressed: busy ? null : submit, child: Text(busy ? (widget.register ? 'Đang gửi mã…' : 'Đang đăng nhập…') : widget.register ? 'Đăng ký' : 'Đăng nhập'))), const SizedBox(height: 16), TextButton(onPressed: busy ? null : () => context.go(widget.register ? '/dang-nhap' : '/dang-ky'), child: Text(widget.register ? 'Đã có tài khoản? Đăng nhập' : 'Chưa có tài khoản? Đăng ký')),
  ]));
  Widget verificationForm() => Form(key: codeForm, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text('Xác nhận đăng ký', style: Theme.of(context).textTheme.displayMedium), const SizedBox(height: 12), Text('Mã gồm 6 chữ số đã gửi tới $maskedEmail. Mã có hiệu lực 10 phút.'), const SizedBox(height: 32), if (error != null) Semantics(liveRegion: true, child: Notice(error!)),
    TextFormField(controller: code, focusNode: codeFocus, enabled: !busy, keyboardType: TextInputType.number, textInputAction: TextInputAction.done, autofillHints: const [AutofillHints.oneTimeCode], inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)], autovalidateMode: AutovalidateMode.onUserInteraction, decoration: InputDecoration(labelText: 'Mã xác nhận', errorText: codeError, errorMaxLines: 3), onChanged: (_) { if (codeError != null) setState(() => codeError = null); }, validator: (v) => RegExp(r'^[0-9]{6}$').hasMatch(v ?? '') ? null : 'Nhập đủ 6 chữ số trong email.', onFieldSubmitted: (_) => verify()), const SizedBox(height: 28),
    SizedBox(width: double.infinity, child: FilledButton(onPressed: busy ? null : verify, child: Text(busy ? 'Đang xử lý…' : 'Xác nhận và tiếp tục'))), const SizedBox(height: 16), Wrap(spacing: 12, runSpacing: 8, children: [TextButton(onPressed: busy || resendIn > 0 ? null : resend, child: Text(resendIn > 0 ? 'Gửi lại mã sau $resendIn giây' : 'Gửi lại mã')), TextButton(onPressed: busy ? null : changeEmail, child: const Text('Đổi email'))]),
  ]));
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: TextButton(onPressed: () => context.go('/'), child: const BrandLogo())), body: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(24), child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 460), child: verifying ? verificationForm() : registrationForm()))));
}
