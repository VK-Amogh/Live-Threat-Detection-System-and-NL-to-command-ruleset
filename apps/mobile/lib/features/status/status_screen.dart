import 'package:flutter/material.dart';
import '../../core/auth_store.dart';
import '../../core/api_client.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_button.dart';

class StatusScreen extends StatefulWidget {
  final AuthStore authStore;
  final VoidCallback onUnpaired;
  const StatusScreen({super.key, required this.authStore, required this.onUnpaired});
  @override
  State<StatusScreen> createState() => _StatusScreenState();
}
class _StatusScreenState extends State<StatusScreen> {
  Map<String, dynamic>? data;
  String? error;
  String host = '';
  bool loading = true;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    try { host = await widget.authStore.getApiBaseUrl(); final response = await ApiClient(widget.authStore).dio.get('/api/v1/system'); if (mounted) setState(() { data = Map<String,dynamic>.from(response.data); error = null; }); }
    catch (e) { if (mounted) setState(() => error = 'Server could not be reached. Pull to retry, or sign out and reconnect.'); }
    finally { if (mounted) setState(() => loading = false); }
  }
  @override
  Widget build(BuildContext context) => SafeArea(child: RefreshIndicator(onRefresh: load, child: ListView(padding: const EdgeInsets.all(AppSpacing.lg), children: [
    Text('Your system', style: AppTypography.screenTitle), const SizedBox(height: AppSpacing.lg),
    Text(host, style: AppTypography.support), const SizedBox(height: AppSpacing.lg),
    if (error != null) Text(error!, style: AppTypography.body),
    if (loading) Text('Reading server status…', style: AppTypography.support),
    if (data != null) ...[
      AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Engine health', style: AppTypography.cardHeading), const SizedBox(height: AppSpacing.md), Text('Detector: ${data!['inference']['ready'] == true ? 'ready' : 'unavailable'}\nLocal chat: ${data!['chat']['local_available'] == true ? 'connected' : 'unavailable'}\nTraining: ${data!['training']['status']}', style: AppTypography.body)])),
      const SizedBox(height: AppSpacing.lg), AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Recorded activity', style: AppTypography.cardHeading), const SizedBox(height: AppSpacing.md), for (final entry in (data!['counts'] as Map).entries) Padding(padding: const EdgeInsets.only(bottom: AppSpacing.sm), child: Text('${entry.key.toString().replaceAll('_', ' ')}: ${entry.value}', style: AppTypography.body))])),
      const SizedBox(height: AppSpacing.lg), AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Outside detection coverage', style: AppTypography.cardHeading), for (final item in (data!['inference']['unsupported'] as List? ?? [])) Padding(padding: const EdgeInsets.only(top: AppSpacing.sm), child: Text(item.toString(), style: AppTypography.support))])),
    ],
    const SizedBox(height: AppSpacing.xl), AppButton(label: 'Sign out', onPressed: () async { try { await ApiClient(widget.authStore).dio.post('/api/v1/auth/logout'); } catch (_) { /* Local credentials must still be removable offline. */ } await widget.authStore.clearSession(); if (mounted) widget.onUnpaired(); }),
    const SizedBox(height: 96),
  ])));
}
