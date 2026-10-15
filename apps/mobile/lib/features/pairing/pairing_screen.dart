import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../../core/api_client.dart';
import '../../core/auth_store.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';

class PairingScreen extends StatefulWidget {
  final AuthStore authStore;
  final ApiClient apiClient;
  final VoidCallback onPaired;
  const PairingScreen({super.key, required this.authStore, required this.apiClient, required this.onPaired});
  @override
  State<PairingScreen> createState() => _PairingScreenState();
}
class _PairingScreenState extends State<PairingScreen> {
  final url = TextEditingController();
  final email = TextEditingController();
  final password = TextEditingController();
  final code = TextEditingController();
  bool pair = false, busy = false;
  String? error;
  @override
  void initState() { super.initState(); widget.authStore.getApiBaseUrl().then((value) { if (mounted) url.text = value; }); }
  @override
  void dispose() { for (final c in [url,email,password,code]) { c.dispose(); } super.dispose(); }
  Future<void> submit() async {
    setState(() { busy = true; error = null; });
    try {
      await widget.authStore.setApiBaseUrl(url.text.trim());
      final response = await widget.apiClient.dio.post(pair ? '/api/v1/auth/pair' : '/api/v1/auth/login', data: pair ? {
        'code': code.text.trim(), 'device_name': 'SafeSpace mobile',
      } : {'username': email.text.trim(), 'password': password.text, 'device_name': 'SafeSpace mobile', 'client_type': 'mobile'});
      await widget.authStore.savePairingSession(deviceId: response.data['device_id'], deviceName: response.data['device_name'], deviceToken: response.data['device_token']);
      if (mounted) widget.onPaired();
    } catch (e) {
      if (mounted) setState(() => error = e is DioException ? (e.response?.data is Map ? e.response?.data['detail']?.toString() : null) ?? 'Cannot reach your PC. Check the address and Wi-Fi connection.' : e.toString());
    } finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(body: SafeArea(child: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(AppSpacing.xl), child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 480), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text('SafeSpace', style: AppTypography.screenTitle), const SizedBox(height: AppSpacing.sm),
    Text('Your space. In focus.', style: AppTypography.cardHeading), const SizedBox(height: AppSpacing.xl),
    Text('Connect to your PC on the same network. Use the server address shown by the launcher.', style: AppTypography.support), const SizedBox(height: AppSpacing.xl),
    field(url, 'Server address', hint: 'http://192.168.1.10:8000'),
    if (pair) field(code, 'Pairing code') else ...[field(email, 'Email'), field(password, 'Password', secret: true)],
    if (error != null) Padding(padding: const EdgeInsets.only(bottom: AppSpacing.lg), child: Text(error!, style: AppTypography.body)),
    AppButton(label: pair ? 'Pair device' : 'Sign in', expand: true, isLoading: busy, onPressed: busy ? null : submit),
    const SizedBox(height: AppSpacing.md), TextButton(onPressed: busy ? null : () => setState(() { pair = !pair; error = null; }), child: Text(pair ? 'Use email and password' : 'Use a single-use pairing code', style: AppTypography.support)),
  ]))))));
  Widget field(TextEditingController c, String label, {String? hint, bool secret = false}) => Padding(padding: const EdgeInsets.only(bottom: AppSpacing.lg), child: TextField(controller: c, obscureText: secret, autocorrect: false, decoration: InputDecoration(labelText: label, hintText: hint, border: OutlineInputBorder(borderRadius: BorderRadius.circular(AppRadii.card)))));
}
