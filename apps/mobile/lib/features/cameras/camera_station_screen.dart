import 'dart:async';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/api_client.dart';
import '../../core/auth_store.dart';
import '../../core/config.dart';
import '../../core/net/route_manager.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_icon.dart';
import '../../core/widgets/page_header.dart';
import '../../services/camera_publisher.dart';
import '../../services/session_service.dart';
import 'live_cameras_screen.dart';

/// This phone as a 16:9 CCTV camera: live widescreen video to the laptop, recorded and analysed there, visible on every other device.
class CameraStationScreen extends StatefulWidget {
  final ApiClient apiClient;
  final AuthStore authStore;
  final RouteManager routes;
  final SessionService session;
  final VoidCallback onSwitchMode;
  final void Function(String cameraId) onCreateRules;

  const CameraStationScreen({
    super.key,
    required this.apiClient,
    required this.authStore,
    required this.routes,
    required this.session,
    required this.onSwitchMode,
    required this.onCreateRules,
  });

  @override
  State<CameraStationScreen> createState() => _CameraStationScreenState();
}

class _CameraStationScreenState extends State<CameraStationScreen>
    with WidgetsBindingObserver {
  static const _screen = MethodChannel('safespace/screen');
  late final CameraPublisher _pub;
  CameraLensDirection _lens = CameraLensDirection.back;
  bool _stealth = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _pub = CameraPublisher(
      store: widget.authStore,
      routes: widget.routes,
      onCommand: _onCommand,
    )..addListener(_changed);
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  /// Commands from the laptop or another phone.
  void _onCommand(String action, Map<String, dynamic> params) {
    switch (action) {
      case 'switch_lens':
        unawaited(_flipLens());
      case 'enter_stealth':
        _setStealth(true);
      case 'exit_stealth':
        _setStealth(false);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if ((state == AppLifecycleState.paused ||
            state == AppLifecycleState.hidden ||
            state == AppLifecycleState.detached) &&
        _pub.state != PublisherState.idle) {
      unawaited(_pub.stop());
    }
  }

  Future<void> _start() async {
    HapticFeedback.selectionClick();
    final cameras = await availableCameras();
    if (cameras.isEmpty) {
      setState(() {});
      return;
    }
    final camera = cameras.firstWhere(
      (c) => c.lensDirection == _lens,
      orElse: () => cameras.first,
    );
    await _pub.start(camera);
  }

  Future<void> _flipLens() async {
    HapticFeedback.selectionClick();
    final was = _pub.live;
    if (was) await _pub.stop();
    _lens = _lens == CameraLensDirection.back
        ? CameraLensDirection.front
        : CameraLensDirection.back;
    if (was) await _start();
    if (mounted) setState(() {});
  }

  void _setStealth(bool on) {
    HapticFeedback.selectionClick();
    _pub.stealth = on;
    unawaited(
      _screen.invokeMethod('setBrightness', {'level': on ? 0.01 : null}),
    );
    if (mounted) setState(() => _stealth = on);
  }

  Future<void> _switchToControlCenter() async {
    if ((await widget.authStore.getScope()) == 'admin') {
      await _pub.stop();
      widget.onSwitchMode();
      return;
    }
    if (!mounted) return;
    final password = TextEditingController();
    String? problem;
    String email = AppConfig.accountTiles.first.key;
    bool busy = false;
    await showDialog<void>(
      context: context,
      barrierColor: AppColors.scrim,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialog) => Dialog(
          backgroundColor: Colors.transparent,
          insetPadding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 380),
            child: Container(
              padding: const EdgeInsets.all(AppSpacing.xl),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(AppRadii.dialog),
                border: Border.all(color: AppColors.divider, width: 1.0),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Operator sign-in required',
                    style: AppTypography.cardHeading,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Enter your operator password to leave Camera Station and open the control center.',
                    style: AppTypography.support,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Wrap(
                    spacing: AppSpacing.sm,
                    runSpacing: AppSpacing.sm,
                    children: [
                      for (final a in AppConfig.accountTiles)
                        AppChip(
                          label: a.value,
                          selected: email == a.key,
                          onTap: () => setDialog(() => email = a.key),
                        ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    controller: password,
                    obscureText: true,
                    autocorrect: false,
                    enableSuggestions: false,
                    style: AppTypography.body,
                    decoration: const InputDecoration(
                      hintText: 'Operator password',
                    ),
                  ),
                  if (problem != null) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      problem!,
                      style: AppTypography.caption.copyWith(
                        color: AppColors.foreground,
                      ),
                    ),
                  ],
                  const SizedBox(height: AppSpacing.xl),
                  Row(
                    children: [
                      Expanded(
                        child: AppButton.secondary(
                          label: 'Cancel',
                          expand: true,
                          onPressed: busy ? null : () => Navigator.pop(ctx),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: AppButton(
                          label: 'Unlock',
                          expand: true,
                          isLoading: busy,
                          onPressed: busy
                              ? null
                              : () async {
                                  setDialog(() {
                                    busy = true;
                                    problem = null;
                                  });
                                  try {
                                    await widget.session.signIn(
                                      email,
                                      password.text,
                                    );
                                    if (ctx.mounted) Navigator.pop(ctx);
                                    await _pub.stop();
                                    widget.onSwitchMode();
                                  } catch (e) {
                                    setDialog(() {
                                      busy = false;
                                      problem = SessionService.describe(e);
                                    });
                                  }
                                },
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pub.removeListener(_changed);
    unawaited(_screen.invokeMethod('setBrightness', {'level': null}));
    _pub.dispose();
    super.dispose();
  }

  Widget _build16By9Preview(CameraController? c) {
    if (c == null || !c.value.isInitialized) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(AppRadii.pill),
                border: Border.all(color: AppColors.divider),
              ),
              child: const Center(
                child: AppIcon(
                  'video-on',
                  size: 28,
                  color: AppColors.foregroundSecondary,
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              '16:9 Widescreen Camera Ready',
              style: AppTypography.cardTitle,
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Tap Start live camera below to stream 16:9 video',
              style: AppTypography.caption,
            ),
          ],
        ),
      );
    }

    final previewSize = c.value.previewSize;
    final rawW = previewSize?.height ?? 720.0;
    final rawH = previewSize?.width ?? 1280.0;

    return FittedBox(
      fit: BoxFit.cover,
      clipBehavior: Clip.hardEdge,
      child: SizedBox(
        width: rawW,
        height: rawH,
        child: CameraPreview(c),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_stealth) {
      return GestureDetector(
        behavior: HitTestBehavior.opaque,
        onDoubleTap: () => _setStealth(false),
        child: Scaffold(
          backgroundColor: AppColors.background,
          body: SafeArea(
            child: Align(
              alignment: Alignment.bottomLeft,
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.xl),
                child: Text(
                  'SafeSpace · ${_pub.live ? 'Live 16:9 · ${_pub.sent} frames · ${_pub.viewers} watching' : 'Standby'} · Double-tap to wake',
                  style: AppTypography.caption.copyWith(
                    color: AppColors.foregroundDisabled,
                  ),
                ),
              ),
            ),
          ),
        ),
      );
    }

    final c = _pub.controller;
    final live = _pub.live;
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.lg,
            AppSpacing.md,
            AppSpacing.lg,
            AppSpacing.xxl,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Camera station',
                      style: AppTypography.screenTitle,
                    ),
                  ),
                  GlassCircleButton(
                    svgAsset: 'grid-01',
                    tooltip: 'Switch to control center',
                    onTap: _switchToControlCenter,
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              AnimatedBuilder(
                animation: widget.routes,
                builder: (_, __) => Row(
                  children: [
                    Icon(
                      Icons.circle,
                      size: 12,
                      color: widget.routes.active?.ok == true
                          ? const Color(0xFF38C878)
                          : const Color(0xFFE65757),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Text(
                        _lens == CameraLensDirection.front
                            ? 'Front camera'
                            : 'Rear camera',
                        style: AppTypography.support),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.lg),

              Text(_pub.cameraId ?? 'This phone',
                  style: AppTypography.cardHeading),
              const SizedBox(height: AppSpacing.md),
              ClipRRect(
                borderRadius: BorderRadius.circular(AppRadii.card),
                child: AspectRatio(
                  aspectRatio: 16 / 9,
                  child: _build16By9Preview(c),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              if (live)
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.sm,
                  children: [
                    AppChip(
                      label: 'Torch',
                      leadingSvg: 'flash',
                      selected: _pub.torchOn,
                      onTap: () => _pub.setTorch(!_pub.torchOn),
                    ),
                    AppChip(
                      label: 'Flip',
                      leadingSvg: 'refresh-01',
                      selected: false,
                      onTap: _flipLens,
                    ),
                    AppChip(
                      label: 'Snapshot',
                      leadingSvg: 'camera-01',
                      selected: false,
                      onTap: _pub.requestSnapshot,
                    ),
                    AppChip(
                      label: 'Stealth',
                      leadingSvg: 'eye-closed',
                      selected: false,
                      onTap: () => _setStealth(true),
                    ),
                  ],
                ),
              const SizedBox(height: AppSpacing.lg),
              // Live Stream Telemetry Card
              AppCard(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Stream', style: AppTypography.cardHeading),
                    const SizedBox(height: AppSpacing.md),
                    Row(
                      children: [
                        Expanded(
                          child: _metricTile(
                            'Frames sent',
                            '${_pub.sent}',
                            '${_pub.dropped} skipped',
                          ),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: _metricTile(
                            'Stream rate',
                            '${_pub.fpsOut.toStringAsFixed(1)} fps',
                            'Target ${_pub.targetFps} fps',
                          ),
                        ),
                      ],
                    ),
                    if (_pub.lastSnapshotNote != null) ...[
                      const SizedBox(height: AppSpacing.md),
                      Text(_pub.lastSnapshotNote!,
                          style: AppTypography.caption),
                    ],
                    if (_pub.error != null) ...[
                      const SizedBox(height: AppSpacing.md),
                      Text(_pub.error!, style: AppTypography.body),
                    ],
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.lg),

              AppButton(
                label: _pub.state == PublisherState.starting
                    ? 'Starting camera…'
                    : (_pub.state == PublisherState.idle
                        ? 'Start 16:9 live camera'
                        : 'Stop camera stream'),
                svgAsset: _pub.state == PublisherState.idle
                    ? 'video-on'
                    : 'video-off',
                expand: true,
                isLoading: _pub.state == PublisherState.starting,
                onPressed: _pub.state == PublisherState.starting
                    ? null
                    : (_pub.state == PublisherState.idle ? _start : _pub.stop),
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  Expanded(
                    child: AppButton.secondary(
                      label: 'Save snapshot',
                      svgAsset: 'camera-01',
                      expand: true,
                      onPressed: live ? _pub.requestSnapshot : null,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: AppButton.secondary(
                      label: 'Stealth screen',
                      svgAsset: 'eye-closed',
                      expand: true,
                      onPressed: () => _setStealth(true),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  Expanded(
                    child: AppButton.secondary(
                      label: 'Flip lens',
                      svgAsset: 'refresh-01',
                      expand: true,
                      onPressed: _flipLens,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: AppButton.secondary(
                      label: 'All cameras',
                      svgAsset: 'grid-01',
                      expand: true,
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => Scaffold(
                            backgroundColor: AppColors.background,
                            body: SafeArea(
                              child: Column(
                                children: [
                                  const Padding(
                                    padding: EdgeInsets.fromLTRB(
                                      AppSpacing.lg,
                                      AppSpacing.sm,
                                      AppSpacing.lg,
                                      0,
                                    ),
                                    child: PageHeader(
                                      title: 'All connected cameras',
                                    ),
                                  ),
                                  Expanded(
                                    child: LiveCamerasScreen(
                                      apiClient: widget.apiClient,
                                      onCreateRules: (id) {
                                        Navigator.pop(context);
                                        widget.onCreateRules(id);
                                      },
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _metricTile(String label, String value, String sub) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(AppRadii.md),
        border: Border.all(color: AppColors.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: AppTypography.caption),
          const SizedBox(height: 4),
          Text(
            value,
            style: AppTypography.cardTitle.copyWith(
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 2),
          Text(sub, style: AppTypography.caption),
        ],
      ),
    );
  }
}
