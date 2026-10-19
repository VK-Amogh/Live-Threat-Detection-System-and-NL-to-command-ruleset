import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/api_client.dart';
import '../../core/auth_store.dart';
import '../../core/net/route_manager.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_icon.dart';
import '../../core/widgets/glass_surface.dart';
import '../../core/widgets/page_header.dart';
import '../../core/widgets/press_scale.dart';
import '../../services/notification_service.dart';

class StatusScreen extends StatefulWidget {
  final AuthStore authStore;
  final RouteManager routes;
  final VoidCallback onUnpaired;
  final VoidCallback onSwitchMode;
  final ApiClient? apiClient;
  final NotificationService notificationService;

  const StatusScreen({
    super.key,
    required this.authStore,
    required this.routes,
    required this.onUnpaired,
    required this.onSwitchMode,
    required this.notificationService,
    this.apiClient,
  });

  @override
  State<StatusScreen> createState() => _StatusScreenState();
}

class _StatusScreenState extends State<StatusScreen> {
  static const _gb = 1024 * 1024 * 1024;
  Map<String, dynamic>? data;
  Map<String, dynamic>? storage;
  Map<String, dynamic>? network;
  List<Map<String, dynamic>> devices = [];
  String? error;
  String? notice;
  bool loading = true;
  bool probingRoute = false;
  bool sweepingStorage = false;
  String? activeCommandKey;
  bool showUnsupported = false;
  bool testingAlert = false;
  late final ApiClient _client =
      widget.apiClient ?? ApiClient(widget.authStore);

  @override
  void initState() {
    super.initState();
    widget.routes.addListener(_changed);
    load();
  }

  @override
  void dispose() {
    widget.routes.removeListener(_changed);
    super.dispose();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  Future<Map<String, dynamic>?> _map(String path) async {
    try {
      final r = await _client.dio.get(path);
      return r.data is Map ? Map<String, dynamic>.from(r.data as Map) : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> load() async {
    if (mounted) setState(() => loading = true);
    try {
      final results = await Future.wait([
        _client.dio.get('/api/v1/system'),
        _map('/api/v1/devices/fleet'),
        _map('/api/v1/storage/summary'),
        _map('/api/v1/network'),
      ]);
      if (!mounted) return;
      final systemRes = results[0] as dynamic;
      final fleet = results[1] as Map<String, dynamic>?;
      final stor = results[2] as Map<String, dynamic>?;
      final net = results[3] as Map<String, dynamic>?;
      setState(() {
        data = Map<String, dynamic>.from(systemRes.data as Map);
        devices = ((fleet?['items'] as List?) ?? const [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        storage = stor;
        network = net;
        error = null;
      });
    } catch (_) {
      if (mounted) {
        setState(
          () => error = 'Your laptop could not be reached. Pull down to retry.',
        );
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _reprobeRoutes() async {
    setState(() {
      probingRoute = true;
      notice = null;
    });
    try {
      await widget.routes.resolve();
      await load();
      if (mounted) {
        final active = widget.routes.active;
        setState(() {
          notice = active?.ok == true
              ? 'Connected via ${active!.routeLabel} (${active.rttMs} ms).'
              : 'Route probe finished — laptop is still unreachable.';
        });
      }
    } finally {
      if (mounted) setState(() => probingRoute = false);
    }
  }

  static const _commands =
      <String, ({String action, String label, String icon})>{
    'torch': (
      action: 'toggle_torch',
      label: 'Torch',
      icon: 'sun-01',
    ),
    'lens': (
      action: 'switch_lens',
      label: 'Flip lens',
      icon: 'refresh-01',
    ),
    'stealth': (
      action: 'enter_stealth',
      label: 'Stealth',
      icon: 'eye-closed',
    ),
    'snapshot': (
      action: 'take_full_snapshot',
      label: 'Snapshot',
      icon: 'camera-01',
    ),
  };

  Future<void> _sendDeviceCommand(String devId, String command) async {
    final key = '$devId:$command';
    setState(() {
      activeCommandKey = key;
      notice = null;
      error = null;
    });
    try {
      final spec = _commands[command];
      await _client.dio.post(
        '/api/v1/devices/${Uri.encodeComponent(devId)}/commands',
        data: {
          'action': spec?.action ?? command,
          'params': <String, dynamic>{},
        },
      );
      HapticFeedback.mediumImpact();
      if (mounted) {
        setState(
          () =>
              notice = 'Sent "${spec?.label ?? command}" to the camera phone.',
        );
      }
      await load();
    } catch (e) {
      if (mounted) {
        setState(() => error = 'Command failed: ${SessionErrors.text(e)}');
      }
    } finally {
      if (mounted) setState(() => activeCommandKey = null);
    }
  }

  Future<void> _runStorageSweep() async {
    setState(() {
      sweepingStorage = true;
      notice = null;
      error = null;
    });
    try {
      await _client.dio
          .post('/api/v1/storage/sweep', data: <String, dynamic>{});
      HapticFeedback.mediumImpact();
      if (mounted) setState(() => notice = 'Retention sweep completed.');
      await load();
    } catch (e) {
      if (mounted) {
        setState(() => error = 'Sweep failed: ${SessionErrors.text(e)}');
      }
    } finally {
      if (mounted) setState(() => sweepingStorage = false);
    }
  }

  Future<void> _sendTestAlert() async {
    setState(() {
      testingAlert = true;
      error = null;
      notice = null;
    });
    try {
      await widget.notificationService.showTestAlert();
      if (mounted) {
        setState(() => notice =
            'Test alert sent. Check Android notification settings if it does not appear.');
      }
    } catch (e) {
      if (mounted) setState(() => error = 'Test alert failed: $e');
    } finally {
      if (mounted) setState(() => testingAlert = false);
    }
  }

  Future<void> _confirmSignOut() async {
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => GlassSurface(
        borderRadius: const BorderRadius.vertical(
          top: Radius.circular(AppRadii.dialog),
        ),
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.md,
          AppSpacing.lg,
          AppSpacing.xl,
        ),
        child: SafeArea(
          top: false,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.foregroundDisabled,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              Text('Sign out of this laptop?',
                  style: AppTypography.sectionHeading),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'You will need to pair or sign in again to receive live alerts and view camera streams.',
                style: AppTypography.support,
              ),
              const SizedBox(height: AppSpacing.xl),
              Row(
                children: [
                  Expanded(
                    child: AppButton.secondary(
                      label: 'Cancel',
                      onPressed: () => Navigator.of(ctx).pop(false),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: AppButton(
                      label: 'Sign out',
                      onPressed: () => Navigator.of(ctx).pop(true),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
    if (confirmed != true) return;
    try {
      await _client.dio.post('/api/v1/auth/logout');
    } catch (_) {}
    await widget.authStore.clearSession();
    if (mounted) widget.onUnpaired();
  }

  String _gbText(num? bytes) =>
      bytes == null ? '—' : (bytes / _gb).toStringAsFixed(1);

  Widget _buildCommandPill({
    required String devId,
    required String commandKey,
    required String label,
    required String icon,
  }) {
    final isActive = activeCommandKey == '$devId:$commandKey';
    final isBusy = activeCommandKey != null;
    return PressScale(
      onTap: isBusy ? null : () => _sendDeviceCommand(devId, commandKey),
      pressedScale: 0.96,
      child: Container(
        height: 38,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        decoration: BoxDecoration(
          color: isActive ? AppColors.selectedChip : AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadii.pill),
          border: Border.all(
            color: isActive ? AppColors.foreground : AppColors.divider,
            width: 1.0,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AppIcon(
              icon,
              size: 14,
              color: isActive
                  ? AppColors.foreground
                  : AppColors.foregroundSecondary,
            ),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                isActive ? '$label…' : label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.tabLabel.copyWith(
                  color: isActive
                      ? AppColors.foreground
                      : AppColors.foregroundSecondary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDeviceCard(Map<String, dynamic> d) {
    final devId =
        d['device_id']?.toString() ?? d['id']?.toString() ?? 'unknown';
    final devName =
        d['device_name']?.toString() ?? d['name']?.toString() ?? devId;
    return AppCard(
      padding: EdgeInsets.zero,
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
        title: Text(devName,
            style: AppTypography.cardHeading,
            maxLines: 1,
            overflow: TextOverflow.ellipsis),
        childrenPadding: const EdgeInsets.fromLTRB(
            AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
        children: [
          Row(
            children: [
              Expanded(
                  child: _buildCommandPill(
                      devId: devId,
                      commandKey: 'torch',
                      label: 'Torch',
                      icon: 'sun-01')),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                  child: _buildCommandPill(
                      devId: devId,
                      commandKey: 'lens',
                      label: 'Flip',
                      icon: 'refresh-01')),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                  child: _buildCommandPill(
                      devId: devId,
                      commandKey: 'stealth',
                      label: 'Stealth',
                      icon: 'eye-closed')),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                  child: _buildCommandPill(
                      devId: devId,
                      commandKey: 'snapshot',
                      label: 'Snapshot',
                      icon: 'camera-01')),
            ],
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final counts = data?['counts'] is Map
        ? Map<String, dynamic>.from(data!['counts'] as Map)
        : <String, dynamic>{};
    final active = widget.routes.active;
    final usedBytes = ((storage?['recordings_bytes'] as num?) ?? 0) +
        ((storage?['snapshots_bytes'] as num?) ?? 0) +
        ((storage?['exports_bytes'] as num?) ?? 0);
    final freeBytes = (storage?['free_bytes'] as num?) ?? 0;

    return RefreshIndicator(
      color: AppColors.foreground,
      backgroundColor: AppColors.surface,
      onRefresh: _reprobeRoutes,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.xl),
        children: [
          Row(
            children: [
              Expanded(child: Text('System', style: AppTypography.screenTitle)),
              GlassCircleButton(
                svgAsset: 'refresh-01',
                tooltip: 'Refresh system',
                onTap: loading || probingRoute ? null : _reprobeRoutes,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          AppCard(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Connection', style: AppTypography.cardHeading),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  active?.routeLabel ?? 'No laptop connected',
                  style: AppTypography.body,
                ),
                if (active?.ok == true) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text('${active!.rttMs} ms', style: AppTypography.support),
                ],
                const SizedBox(height: AppSpacing.lg),
                AppButton.secondary(
                  label: probingRoute ? 'Checking…' : 'Check connection',
                  expand: true,
                  onPressed: probingRoute ? null : _reprobeRoutes,
                ),
              ],
            ),
          ),
          if (error != null || notice != null) ...[
            const SizedBox(height: AppSpacing.md),
            Text(error ?? notice!, style: AppTypography.support),
          ],
          const SizedBox(height: AppSpacing.md),
          AppButton.secondary(
            label: testingAlert ? 'Sending…' : 'Send test notification',
            expand: true,
            onPressed: testingAlert ? null : _sendTestAlert,
          ),
          const SizedBox(height: AppSpacing.xl),
          Text('Activity', style: AppTypography.sectionHeading),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                  child: _metricCard(
                      'Events', (counts['incidents'] ?? '—').toString())),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                  child: _metricCard(
                      'Review', (counts['needs_review'] ?? '—').toString())),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                  child: _metricCard(
                      'Confirmed', (counts['confirmed'] ?? '—').toString())),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                  child: _metricCard(
                      'Cameras',
                      (counts['cameras_online'] ?? counts['sources'] ?? '—')
                          .toString())),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          Text('Phones', style: AppTypography.sectionHeading),
          const SizedBox(height: AppSpacing.md),
          if (devices.isEmpty)
            AppCard(
                child: Text('No phones connected', style: AppTypography.body))
          else
            for (final device in devices) ...[
              _buildDeviceCard(device),
              const SizedBox(height: AppSpacing.md),
            ],
          if (storage != null) ...[
            const SizedBox(height: AppSpacing.lg),
            Text('Storage', style: AppTypography.sectionHeading),
            const SizedBox(height: AppSpacing.md),
            AppCard(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                          child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${_gbText(usedBytes)} GB',
                              style: AppTypography.cardHeading),
                          Text('Used', style: AppTypography.support),
                        ],
                      )),
                      Expanded(
                          child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${_gbText(freeBytes)} GB',
                              style: AppTypography.cardHeading),
                          Text('Free', style: AppTypography.support),
                        ],
                      )),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  AppButton.secondary(
                    label: sweepingStorage
                        ? 'Applying…'
                        : 'Apply retention limits',
                    expand: true,
                    onPressed: sweepingStorage ? null : _runStorageSweep,
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.xl),
          AppButton.secondary(
            label: 'Use this phone as a camera',
            svgAsset: 'video-on',
            expand: true,
            onPressed: widget.onSwitchMode,
          ),
          const SizedBox(height: AppSpacing.md),
          AppButton.secondary(
            label: 'Sign out',
            expand: true,
            onPressed: _confirmSignOut,
          ),
        ],
      ),
    );
  }

  Widget _metricCard(String label, String value) => AppCard(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(value, style: AppTypography.sectionHeading),
            const SizedBox(height: AppSpacing.sm),
            Text(label, style: AppTypography.support),
          ],
        ),
      );
}

/// Short, readable text for an exception raised by a request.
class SessionErrors {
  static String text(Object e) => e.toString().split('\n').first;
}
