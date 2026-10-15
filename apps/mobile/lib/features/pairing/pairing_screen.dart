import 'package:flutter/material.dart';
import '../../core/api_client.dart';
import '../../core/auth_store.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';

class PairingScreen extends StatefulWidget {
  final AuthStore authStore;
  final ApiClient apiClient;
  final VoidCallback onPaired;

  const PairingScreen({
    super.key,
    required this.authStore,
    required this.apiClient,
    required this.onPaired,
  });

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final _urlController = TextEditingController();
  final _codeController = TextEditingController();
  final _deviceNameController = TextEditingController(text: 'Android Security Terminal');
  bool _isLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadCurrentUrl();
  }

  Future<void> _loadCurrentUrl() async {
    final url = await widget.authStore.getApiBaseUrl();
    _urlController.text = url;
  }

  Future<void> _submitPairing() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    final hostUrl = _urlController.text.trim();
    final code = _codeController.text.trim().toUpperCase();
    final deviceName = _deviceNameController.text.trim();

    if (hostUrl.isEmpty || code.isEmpty) {
      setState(() {
        _error = 'Host URL and 10-minute Pairing Code are required.';
        _isLoading = false;
      });
      return;
    }

    try {
      await widget.authStore.setApiBaseUrl(hostUrl);

      final response = await widget.apiClient.dio.post(
        '/api/v1/auth/pair',
        data: {
          'code': code,
          'device_name': deviceName,
        },
      );

      final data = response.data as Map<String, dynamic>;
      final deviceId = data['device_id'] as String;
      final deviceToken = data['device_token'] as String;

      await widget.authStore.savePairingSession(
        deviceId: deviceId,
        deviceName: deviceName,
        deviceToken: deviceToken,
      );

      widget.onPaired();
    } catch (e) {
      setState(() {
        _error = 'Pairing failed: $e';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: AppSpacing.lg),
              Text('Device Pairing', style: AppTypography.screenTitle),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Connect to your local SafeSpace Threat Detection Server.',
                style: AppTypography.support,
              ),
              const SizedBox(height: AppSpacing.xxl),

              // Inputs
              _inputField(
                label: 'Server LAN Base URL',
                controller: _urlController,
                hint: 'http://192.168.1.100:8000',
              ),
              const SizedBox(height: AppSpacing.lg),

              _inputField(
                label: '10-Minute Pairing Code',
                controller: _codeController,
                hint: 'SAFE-9821',
                textCapitalization: TextCapitalization.characters,
              ),
              const SizedBox(height: AppSpacing.lg),

              _inputField(
                label: 'Device Identifier Name',
                controller: _deviceNameController,
                hint: 'Security Terminal 1',
              ),

              if (_error != null) ...[
                const SizedBox(height: AppSpacing.lg),
                Row(
                  children: [
                    const Icon(Icons.info_outline_rounded, size: 16, color: AppColors.foreground),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(
                      child: Text(
                        _error!,
                        style: AppTypography.caption.copyWith(color: AppColors.foreground),
                      ),
                    ),
                  ],
                ),
              ],

              const SizedBox(height: AppSpacing.xxl),

              AppButton(
                label: 'Pair Device Now',
                expand: true,
                isLoading: _isLoading,
                onPressed: _submitPairing,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _inputField({
    required String label,
    required TextEditingController controller,
    required String hint,
    TextCapitalization textCapitalization = TextCapitalization.none,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppTypography.caption),
        const SizedBox(height: AppSpacing.xs),
        Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(AppRadii.lg),
            border: Border.all(color: AppColors.divider, width: 1.0),
          ),
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
          child: TextField(
            controller: controller,
            textCapitalization: textCapitalization,
            style: AppTypography.body,
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: AppTypography.body.copyWith(
                color: AppColors.foregroundSecondary,
              ),
              border: InputBorder.none,
            ),
          ),
        ),
      ],
    );
  }
}
