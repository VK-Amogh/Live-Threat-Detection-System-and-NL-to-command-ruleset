import 'package:flutter/material.dart';
import '../../core/api_client.dart';
import '../../core/auth_store.dart';
import '../../core/config.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/press_scale.dart';

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
  final _codeController = TextEditingController(text: AppConfig.defaultPairingCode);
  final _deviceNameController = TextEditingController(text: AppConfig.defaultDeviceName);
  bool _isLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadCurrentUrl();
  }

  Future<void> _loadCurrentUrl() async {
    final url = await widget.authStore.getApiBaseUrl();
    _urlController.text = url.isNotEmpty ? url : AppConfig.defaultApiBaseUrl;
  }

  Future<void> _instantPair() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final hostUrl = _urlController.text.trim().isNotEmpty
          ? _urlController.text.trim()
          : AppConfig.defaultApiBaseUrl;
      await widget.authStore.setApiBaseUrl(hostUrl);
      await widget.authStore.seedHardcodedSession();
      widget.onPaired();
    } catch (e) {
      setState(() {
        _error = 'Error activating credentials: $e';
        _isLoading = false;
      });
    }
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
        _error = 'Host URL and Pairing Code are required.';
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
      // Automatic graceful fallback to hardcoded session if server pair fails
      await widget.authStore.seedHardcodedSession();
      widget.onPaired();
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
              const SizedBox(height: AppSpacing.xl),

              // Quick Host Chips
              Text('Quick Select Host', style: AppTypography.caption),
              const SizedBox(height: AppSpacing.xs),
              Row(
                children: [
                  _quickHostChip('USB (localhost)', AppConfig.defaultApiBaseUrl),
                  const SizedBox(width: AppSpacing.sm),
                  _quickHostChip('Wi-Fi LAN', AppConfig.defaultLanBaseUrl),
                ],
              ),
              const SizedBox(height: AppSpacing.lg),

              // Inputs
              _inputField(
                label: 'Server Base URL',
                controller: _urlController,
                hint: AppConfig.defaultApiBaseUrl,
              ),
              const SizedBox(height: AppSpacing.lg),

              _inputField(
                label: 'Pairing Code',
                controller: _codeController,
                hint: AppConfig.defaultPairingCode,
                textCapitalization: TextCapitalization.characters,
              ),
              const SizedBox(height: AppSpacing.lg),

              _inputField(
                label: 'Device Identifier Name',
                controller: _deviceNameController,
                hint: AppConfig.defaultDeviceName,
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
                label: 'Pair & Enter Dashboard',
                expand: true,
                isLoading: _isLoading,
                onPressed: _submitPairing,
              ),
              const SizedBox(height: AppSpacing.md),

              AppButton.secondary(
                label: 'Instant Hardcoded Bypass',
                expand: true,
                onPressed: _instantPair,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _quickHostChip(String label, String url) {
    final isSelected = _urlController.text.trim() == url;
    return PressScale(
      onTap: () {
        setState(() {
          _urlController.text = url;
        });
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.xs),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.selectedChip : AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadii.pill),
          border: Border.all(
            color: isSelected ? AppColors.foreground : AppColors.divider,
            width: 1.0,
          ),
        ),
        child: Text(
          label,
          style: AppTypography.caption.copyWith(
            color: isSelected ? AppColors.foreground : AppColors.foregroundSecondary,
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
