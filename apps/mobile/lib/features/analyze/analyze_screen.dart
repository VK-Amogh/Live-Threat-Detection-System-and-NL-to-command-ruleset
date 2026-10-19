import 'dart:async';
import 'package:camera/camera.dart';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/api_client.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_icon.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/evidence_media.dart';
import '../../core/widgets/fade_scrim.dart';
import '../../core/widgets/glass_surface.dart';
import '../../core/widgets/page_header.dart';
import '../../core/widgets/press_scale.dart';
import '../../data/repositories/events_repository.dart';
import '../incidents/incident_detail_screen.dart';

class AnalyzeScreen extends StatefulWidget {
  final ApiClient apiClient;
  final EventsRepository eventsRepository;
  const AnalyzeScreen({
    super.key,
    required this.apiClient,
    required this.eventsRepository,
  });
  @override
  State<AnalyzeScreen> createState() => _AnalyzeScreenState();
}

class _AnalyzeScreenState extends State<AnalyzeScreen>
    with WidgetsBindingObserver {
  List<Map<String, dynamic>> sources = [];
  Map<String, dynamic>? selected;
  String? error;
  bool busy = false, live = false;
  String query = '';
  int _activeTab = 0; // 0: Upload media, 1: Live camera
  CameraController? camera;
  Timer? poll;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    load();
    poll = Timer.periodic(const Duration(seconds: 4), (_) => load());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    live = false;
    poll?.cancel();
    camera?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed && live) stopLive();
  }

  Future<void> load() async {
    try {
      final response = await widget.apiClient.dio.get('/api/v1/sources');
      if (!mounted) return;
      setState(() {
        sources = (response.data as List)
            .map((s) => Map<String, dynamic>.from(s))
            .toList();
        if (selected != null) {
          for (final s in sources) {
            if (s['id'] == selected!['id']) selected = s;
          }
        }
      });
    } catch (_) {
      if (mounted) {
        setState(
          () => error =
              'Source history is unavailable. Check your server connection.',
        );
      }
    }
  }

  Future<void> upload(String path, String name) async {
    if (mounted) {
      setState(() {
        busy = true;
        error = null;
      });
    }
    try {
      final data = FormData.fromMap({
        'file': await MultipartFile.fromFile(path, filename: name),
      });
      final response = await widget.apiClient.dio.post(
        '/api/v1/sources',
        data: data,
        options: Options(
          contentType: 'multipart/form-data',
          sendTimeout: const Duration(minutes: 5),
        ),
      );
      if (mounted) {
        setState(() => selected = Map<String, dynamic>.from(response.data));
      }
      await load();
      widget.eventsRepository.invalidate();
    } catch (e) {
      if (mounted) {
        setState(
          () => error =
              'Upload failed: ${e is DioException ? e.response?.data ?? e.message : e}',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> pick() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: [
        'jpg',
        'jpeg',
        'png',
        'webp',
        'mp4',
        'webm',
        'mov',
        'avi',
        'mkv',
      ],
    );
    if (result?.files.single.path != null) {
      await upload(result!.files.single.path!, result.files.single.name);
    }
  }

  Future<void> photo() async {
    final file = await ImagePicker().pickImage(
      source: ImageSource.camera,
      maxWidth: 1920,
      imageQuality: 90,
    );
    if (file != null) await upload(file.path, file.name);
  }

  Future<void> startLive() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) throw StateError('No camera is available');
      camera = CameraController(
        cameras.firstWhere(
          (c) => c.lensDirection == CameraLensDirection.back,
          orElse: () => cameras.first,
        ),
        ResolutionPreset.high,
        enableAudio: false,
      );
      await camera!.initialize();
      if (!mounted) return;
      setState(() {
        live = true;
        error = null;
      });
      while (live && mounted) {
        final c = camera!;
        await c.startVideoRecording();
        await Future<void>.delayed(const Duration(seconds: 5));
        if (!mounted || camera != c || !c.value.isInitialized) break;
        if (c.value.isRecordingVideo) {
          final file = await c.stopVideoRecording();
          await upload(
            file.path,
            'Mobile-${DateTime.now().millisecondsSinceEpoch}.mp4',
          );
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          live = false;
          error = 'Camera unavailable: $e';
        });
      }
    }
  }

  void stopLive() {
    setState(() => live = false);
  }

  void _showLibrarySheet() {
    HapticFeedback.selectionClick();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (sheet) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Analyzed library',
                            style: AppTypography.cardHeading),
                        Text(
                          '${sources.length} recordings & snapshots',
                          style: AppTypography.caption,
                        ),
                      ],
                    ),
                  ),
                  GlassCircleButton(
                    svgAsset: 'x-01',
                    compact: true,
                    onTap: () => Navigator.pop(sheet),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                style: AppTypography.body,
                decoration: const InputDecoration(
                  prefixIcon: Padding(
                    padding: EdgeInsets.all(14),
                    child: AppIcon(
                      'search-01',
                      size: 18,
                      color: AppColors.foregroundSecondary,
                    ),
                  ),
                  hintText: 'Search analyzed media…',
                ),
                onChanged: (value) => setState(() => query = value),
              ),
              const SizedBox(height: AppSpacing.md),
              SizedBox(
                height: 340,
                child: sources.isEmpty
                    ? Center(
                        child: Text(
                          'No analyzed videos or photos yet.',
                          style: AppTypography.support,
                        ),
                      )
                    : ListView.separated(
                        itemCount: sources
                            .where(
                              (s) => '${s['filename']}'
                                  .toLowerCase()
                                  .contains(query.toLowerCase()),
                            )
                            .length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(height: AppSpacing.sm),
                        itemBuilder: (_, index) {
                          final filtered = sources
                              .where(
                                (s) => '${s['filename']}'
                                    .toLowerCase()
                                    .contains(query.toLowerCase()),
                              )
                              .toList();
                          final source = filtered[index];
                          final count =
                              ((source['event_ids'] as List?) ?? const [])
                                  .length;
                          return AppCard(
                            padding: const EdgeInsets.all(AppSpacing.md),
                            onTap: () {
                              Navigator.pop(sheet);
                              setState(() {
                                selected = source;
                                _activeTab = 0;
                              });
                            },
                            child: Row(
                              children: [
                                const AppIcon(
                                  'play-03',
                                  size: 20,
                                  color: AppColors.foreground,
                                ),
                                const SizedBox(width: AppSpacing.md),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '${source['filename']}',
                                        style: AppTypography.cardTitle,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        '${source['status']} · $count incidents',
                                        style: AppTypography.caption,
                                      ),
                                    ],
                                  ),
                                ),
                                const AppIcon(
                                  'chevron-right',
                                  size: 16,
                                  color: AppColors.foregroundSecondary,
                                ),
                              ],
                            ),
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.lg,
                AppSpacing.sm,
                AppSpacing.lg,
                AppSpacing.sm,
              ),
              child: PageHeader(
                title: 'Analyze media',
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (sources.isNotEmpty) ...[
                      GlassCircleButton(
                        svgAsset: 'folder-01',
                        tooltip: 'Library',
                        compact: true,
                        onTap: _showLibrarySheet,
                      ),
                      const SizedBox(width: AppSpacing.xs),
                    ],
                    GlassCircleButton(
                      svgAsset: 'refresh-01',
                      compact: true,
                      onTap: load,
                    ),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
              child: _buildSymmetricalTabSwitcher(),
            ),
            const SizedBox(height: AppSpacing.sm),
            Expanded(
              child: _activeTab == 0 ? _uploadPane() : _liveCameraPane(),
            ),
          ],
        ),
      ),
    );
  }

  /// Symmetrical tab switcher strictly conforming to Requirement 2:
  /// Equal-width symmetrical switcher ("Upload media" / "Live camera").
  Widget _buildSymmetricalTabSwitcher() {
    return Container(
      height: 44,
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadii.pill),
        border: Border.all(color: AppColors.divider, width: 1.0),
      ),
      child: Row(
        children: [
          Expanded(
            child: PressScale(
              onTap: () {
                if (_activeTab != 0) {
                  HapticFeedback.selectionClick();
                  setState(() => _activeTab = 0);
                }
              },
              pressedScale: 0.96,
              child: AnimatedContainer(
                duration: AppMotion.shortDuration,
                curve: AppMotion.standardCurve,
                decoration: BoxDecoration(
                  color: _activeTab == 0
                      ? AppColors.selectedChip
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(AppRadii.pill),
                  border: _activeTab == 0
                      ? Border.all(color: AppColors.foreground, width: 1.0)
                      : null,
                ),
                child: Center(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      AppIcon(
                        'upload-02',
                        size: 16,
                        color: _activeTab == 0
                            ? AppColors.foreground
                            : AppColors.foregroundSecondary,
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      Text(
                        'Upload media',
                        style: AppTypography.tabLabel.copyWith(
                          color: _activeTab == 0
                              ? AppColors.foreground
                              : AppColors.foregroundSecondary,
                          fontWeight: _activeTab == 0
                              ? FontWeight.w600
                              : FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 4),
          Expanded(
            child: PressScale(
              onTap: () {
                if (_activeTab != 1) {
                  HapticFeedback.selectionClick();
                  setState(() => _activeTab = 1);
                }
              },
              pressedScale: 0.96,
              child: AnimatedContainer(
                duration: AppMotion.shortDuration,
                curve: AppMotion.standardCurve,
                decoration: BoxDecoration(
                  color: _activeTab == 1
                      ? AppColors.selectedChip
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(AppRadii.pill),
                  border: _activeTab == 1
                      ? Border.all(color: AppColors.foreground, width: 1.0)
                      : null,
                ),
                child: Center(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      AppIcon(
                        'video-on',
                        size: 16,
                        color: _activeTab == 1
                            ? AppColors.foreground
                            : AppColors.foregroundSecondary,
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      Text(
                        'Live camera',
                        style: AppTypography.tabLabel.copyWith(
                          color: _activeTab == 1
                              ? AppColors.foreground
                              : AppColors.foregroundSecondary,
                          fontWeight: _activeTab == 1
                              ? FontWeight.w600
                              : FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Clean 16:9 upload/playback stage with centered play/pause controls.
  Widget _uploadPane() {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        if (selected != null && selected!['media_url'] != null) ...[
          // Clean 16:9 Playback Stage with Centered Play/Pause Controls
          AspectRatio(
            aspectRatio: 16 / 9,
            child: EvidenceMedia(
              key: ValueKey(selected!['media_url'] ?? selected!['id']),
              url: selected!['media_url'] ?? '',
              video: selected!['kind'] == 'video',
              autoPlay: false,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${selected!['filename'] ?? 'Recording'}',
                        style: AppTypography.cardTitle,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    AppCapsule(
                      label: '${selected!['status'] ?? 'Pending'}',
                      inverted:
                          '${selected!['status']}'.toLowerCase() == 'completed',
                    ),
                  ],
                ),
                if (selected!['error'] != null) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text('${selected!['error']}', style: AppTypography.body),
                ],
                const SizedBox(height: AppSpacing.sm),
                Text(
                  ((selected!['event_ids'] as List?) ?? const []).isEmpty
                      ? 'No supported threat detected in this footage.'
                      : 'Threat detection requires operator review.',
                  style: AppTypography.body,
                ),
                for (final id
                    in (selected!['event_ids'] as List? ?? const [])) ...[
                  const SizedBox(height: AppSpacing.md),
                  AppButton.secondary(
                    label: 'Inspect incident',
                    svgAsset: 'chevron-right',
                    expand: true,
                    onPressed: () async {
                      final event =
                          await widget.eventsRepository.getEvent('$id');
                      if (mounted) {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => IncidentDetailScreen(
                              event: event,
                              eventsRepository: widget.eventsRepository,
                            ),
                          ),
                        );
                      }
                    },
                  ),
                ],
                const SizedBox(height: AppSpacing.md),
                AppButton.secondary(
                  label: 'Upload another file',
                  svgAsset: 'upload-02',
                  expand: true,
                  onPressed: () => setState(() => selected = null),
                ),
              ],
            ),
          ),
        ] else ...[
          // Clean 16:9 Upload Stage with Centered Upload Action
          AspectRatio(
            aspectRatio: 16 / 9,
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(AppRadii.lg),
                border: Border.all(color: AppColors.divider, width: 1.0),
              ),
              clipBehavior: Clip.antiAlias,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  PressScale(
                    onTap: busy ? null : pick,
                    pressedScale: 0.98,
                    child: Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 56,
                            height: 56,
                            decoration: BoxDecoration(
                              color: AppColors.background,
                              shape: BoxShape.circle,
                              border: Border.all(color: AppColors.divider),
                            ),
                            child: const Center(
                              child: AppIcon(
                                'upload-02',
                                size: 26,
                                color: AppColors.foreground,
                              ),
                            ),
                          ),
                          const SizedBox(height: AppSpacing.md),
                          Text(
                            'Upload 16:9 footage',
                            style: AppTypography.cardHeading,
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: AppSpacing.xs),
                          Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.lg,
                            ),
                            child: Text(
                              'Choose a recording or snapshot to run threat & rule detection',
                              style: AppTypography.support,
                              textAlign: TextAlign.center,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: AppButton.secondary(
                  label: 'Take photo',
                  svgAsset: 'camera-01',
                  expand: true,
                  onPressed: busy ? null : photo,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: AppButton.secondary(
                  label: 'Browse files',
                  svgAsset: 'upload-02',
                  expand: true,
                  onPressed: busy ? null : pick,
                ),
              ),
            ],
          ),
        ],
        if (busy) ...[
          const SizedBox(height: AppSpacing.md),
          AppCard(
            child: Row(
              children: [
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppColors.foreground,
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Text(
                    'Uploading and analyzing on your laptop…',
                    style: AppTypography.body,
                  ),
                ),
              ],
            ),
          ),
        ],
        if (error != null) ...[
          const SizedBox(height: AppSpacing.md),
          Text(error!, style: AppTypography.support),
        ],
        if (sources.isNotEmpty && selected == null) ...[
          const SizedBox(height: AppSpacing.xl),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Recent analyzed media', style: AppTypography.cardHeading),
              AppCapsule(
                label: '${sources.length} items',
                onTap: _showLibrarySheet,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          for (final source in sources.take(4))
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: AppCard(
                onTap: () {
                  setState(() => selected = source);
                },
                child: Row(
                  children: [
                    const AppIcon(
                      'play-03',
                      size: 20,
                      color: AppColors.foreground,
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${source['filename']}',
                            style: AppTypography.cardTitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '${source['status']} · ${((source['event_ids'] as List?) ?? const []).length} incidents',
                            style: AppTypography.caption,
                          ),
                        ],
                      ),
                    ),
                    const AppIcon(
                      'chevron-right',
                      size: 16,
                      color: AppColors.foregroundSecondary,
                    ),
                  ],
                ),
              ),
            ),
        ],
      ],
    );
  }

  /// Clean 16:9 Live Camera Stage with Centered Controls.
  Widget _liveCameraPane() {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        if (live && camera?.value.isInitialized == true) ...[
          // Active 16:9 Live Camera Stage
          AspectRatio(
            aspectRatio: 16 / 9,
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(AppRadii.lg),
                border: Border.all(color: AppColors.foreground, width: 1.5),
              ),
              clipBehavior: Clip.antiAlias,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  FittedBox(
                    fit: BoxFit.cover,
                    clipBehavior: Clip.hardEdge,
                    child: SizedBox(
                      width: camera!.value.previewSize?.height ?? 720,
                      height: camera!.value.previewSize?.width ?? 1280,
                      child: CameraPreview(camera!),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          AppButton.secondary(
            label: 'Stop live capture',
            svgAsset: 'video-off',
            expand: true,
            onPressed: stopLive,
          ),
        ] else ...[
          // Standby 16:9 Live Camera Stage
          AspectRatio(
            aspectRatio: 16 / 9,
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(AppRadii.lg),
                border: Border.all(color: AppColors.divider, width: 1.0),
              ),
              clipBehavior: Clip.antiAlias,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  PressScale(
                    onTap: busy ? null : startLive,
                    pressedScale: 0.98,
                    child: Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 56,
                            height: 56,
                            decoration: BoxDecoration(
                              color: AppColors.background,
                              shape: BoxShape.circle,
                              border: Border.all(color: AppColors.divider),
                            ),
                            child: const Center(
                              child: AppIcon(
                                'video-on',
                                size: 26,
                                color: AppColors.foreground,
                              ),
                            ),
                          ),
                          const SizedBox(height: AppSpacing.md),
                          Text(
                            'Live 16:9 camera feed',
                            style: AppTypography.cardHeading,
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: AppSpacing.xs),
                          Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.lg,
                            ),
                            child: Text(
                              'Stream 5-second 16:9 clips directly to your laptop for threat detection',
                              style: AppTypography.support,
                              textAlign: TextAlign.center,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const Positioned(
                    top: AppSpacing.sm,
                    right: AppSpacing.sm,
                    child:
                        AppCapsule(label: '16:9 Feed', svgAsset: 'camera-01'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          AppButton(
            label: 'Start live 16:9 stream',
            svgAsset: 'video-on',
            expand: true,
            onPressed: busy ? null : startLive,
          ),
        ],
        const SizedBox(height: AppSpacing.md),
        AppCard(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AppIcon(
                'shield-check',
                size: 20,
                color: AppColors.foreground,
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Edge processing and privacy',
                      style: AppTypography.cardTitle,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'All video frames are analyzed locally on your paired host laptop. No imagery leaves your private environment.',
                      style: AppTypography.support,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (error != null) ...[
          const SizedBox(height: AppSpacing.md),
          Text(error!, style: AppTypography.support),
        ],
      ],
    );
  }
}
