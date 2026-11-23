// Nguyễn Tâm Bình - 2324801030003
import 'package:flutter/material.dart';
import '../api/cloud_state.dart';
import '../widgets/common.dart';
import 'admin_backups.dart';
import 'admin_data_screen.dart';
import 'admin_map.dart';
import 'admin_overview.dart';
import 'admin_settings.dart';
import 'admin_users.dart';

class AdminScreen extends StatefulWidget {
  final CloudState state;
  final String area;
  final int? userId;
  const AdminScreen({super.key, required this.state, this.area = 'tong-quan', this.userId});
  @override
  State<AdminScreen> createState() => _AdminScreenState();
}
class _AdminScreenState extends State<AdminScreen> {
  @override
  void initState() { super.initState(); if (widget.state.user == null) Future.microtask(widget.state.refresh); }
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: widget.state, builder: (context, _) {
    if (!widget.state.admin) return PageBody(children: [const Heading('Quản trị', 'Chức năng dành cho quản trị viên.'), if (widget.state.loading) const LinearProgressIndicator() else const Notice('Tài khoản của bạn không có quyền truy cập khu vực này.')]);
    final titles = {'tong-quan': 'Tổng quan hệ thống', 'ban-do': 'Bản đồ dịch vụ', 'nguoi-dung': widget.userId == null ? 'Người dùng' : 'Chi tiết người dùng', 'truy-xuat': 'Truy xuất dữ liệu', 'cap-nhat': 'Cập nhật dữ liệu', 'sao-luu': 'Sao lưu và khôi phục'};
    final descriptions = {'tong-quan': 'Theo dõi dòng tiền, khách hàng và hạ tầng máy cá nhân.', 'ban-do': 'Dịch vụ khách thuê trên từng node và thông tin chủ sở hữu.', 'nguoi-dung': 'Quản lý tài khoản, số dư, dịch vụ và lịch sử thao tác.', 'truy-xuat': 'Tìm kiếm và xuất dữ liệu công khai trong phạm vi quản trị.', 'cap-nhat': 'Quản lý gói, thông tin node và ánh xạ hệ điều hành.', 'sao-luu': 'Bản sao lưu cơ sở dữ liệu PostgreSQL và lịch sử tạo.'};
    final child = switch (widget.area) { 'ban-do' => AdminMap(api: widget.state.api), 'nguoi-dung' => AdminUsers(api: widget.state.api, userId: widget.userId, actorId: widget.state.user?['id'] as int?), 'truy-xuat' => AdminDataScreen(api: widget.state.api), 'cap-nhat' => AdminSettings(api: widget.state.api), 'sao-luu' => AdminBackups(state: widget.state), _ => AdminOverview(api: widget.state.api) };
    return PageBody(children: [Heading(titles[widget.area] ?? titles['tong-quan']!, descriptions[widget.area] ?? descriptions['tong-quan']!), KeyedSubtree(key: ValueKey('${widget.area}-${widget.userId}'), child: child)]);
  });
}
