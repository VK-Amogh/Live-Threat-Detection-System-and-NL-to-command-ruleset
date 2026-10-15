import 'package:flutter/material.dart';
import '../../core/auth_store.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_dialog.dart';

class StatusScreen extends StatefulWidget {
  final AuthStore authStore;
  final VoidCallback onUnpaired;

  const StatusScreen({super.key, required this.authStore, required this.onUnpaired});

  @override
  State<StatusScreen> createState() => _StatusScreenState();
}

class _StatusScreenState extends State<StatusScreen> {
  String _hostUrl = '';
  bool _isPaired = false;

  @override
  void initState() {
    super.initState();
    _loadStatus();
  }

  Future<void> _loadStatus() async {
    final url = await widget.authStore.getApiBaseUrl();
    final paired = await widget.authStore.isPaired();
    setState(() {
      _hostUrl = url;
      _isPaired = paired;
    });
  }

  Future<void> _unpair() async {
    final confirmed = await showAppConfirmDialog(
      context,
      title: 'Unpair Device?',
      body: 'You will stop receiving local threat notifications on this device until re-paired.',
      confirmLabel: 'Unpair',
    );

    if (confirmed) {
      await widget.authStore.clearSession();
      widget.onUnpaired();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: AppSpacing.sm),
              Text('System Telemetry', style: AppTypography.screenTitle),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'On-premises Server & Real-time Stream Diagnostics',
                style: AppTypography.support,
              ),
              const SizedBox(height: AppSpacing.xxl),

              AppCard(
                child: Column(
                  children: [
                    _statusRow('LAN Host API', _hostUrl),
                    const Divider(color: AppColors.divider, height: AppSpacing.lg),
                    _statusRow('Device Status', _isPaired ? 'AUTHENTICATED' : 'UNPAIRED'),
                    const Divider(color: AppColors.divider, height: AppSpacing.lg),
                    _statusRow('WebSocket Stream', 'ACTIVE (PORT 8000)'),
                    const Divider(color: AppColors.divider, height: AppSpacing.lg),
                    _statusRow('Detection Model', 'YOLOv8 (5 FPS, FP16)'),
                    const Divider(color: AppColors.divider, height: AppSpacing.lg),
                    _statusRow('Verification Engine', 'Local VLM (Ollama)'),
                    const Divider(color: AppColors.divider, height: AppSpacing.lg),
                    _statusRow('Supabase Backup', 'SYNCHRONIZED'),
                  ],
                ),
              ),

              const Spacer(),

              if (_isPaired)
                AppButton.secondary(
                  label: 'Unpair Device',
                  expand: true,
                  onPressed: _unpair,
                ),
              const SizedBox(height: 72), // Clearance for floating nav pill
            ],
          ),
        ),
      ),
    );
  }

  Widget _statusRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: AppTypography.support),
        Text(value, style: AppTypography.cardTitle),
      ],
    );
  }
}
