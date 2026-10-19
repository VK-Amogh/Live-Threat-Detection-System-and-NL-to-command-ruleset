import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/api_client.dart';
import '../../core/auth_store.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_icon.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/evidence_media.dart';
import '../../core/widgets/page_header.dart';
import '../../data/repositories/events_repository.dart';
import '../analyze/analyze_screen.dart';

class _DetectionBoxPainter extends CustomPainter {
  final List<Map<String, dynamic>> boxes;
  final double frameWidth;
  final double frameHeight;

  _DetectionBoxPainter({
    required this.boxes,
    required this.frameWidth,
    required this.frameHeight,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (boxes.isEmpty || frameWidth <= 0 || frameHeight <= 0) return;

    // Strictly project frameWidth x frameHeight inside the 16:9 viewport
    final fitted = applyBoxFit(
      BoxFit.contain,
      Size(frameWidth, frameHeight),
      size,
    );
    final destRect = Alignment.center.inscribe(
      fitted.destination,
      Offset.zero & size,
    );
    final scaleX = destRect.width / frameWidth;
    final scaleY = destRect.height / frameHeight;

    final boxPaint = Paint()
      ..color = AppColors.foreground
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    final threatPaint = Paint()
      ..color = AppColors.foreground
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.0;

    final pillPaint = Paint()
      ..color = AppColors.glassFill
      ..style = PaintingStyle.fill;
    final pillBorderPaint = Paint()
      ..color = AppColors.divider
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    for (final b in boxes) {
      final rawBbox =
          (b['bbox'] as List?) ?? (b['box'] as List?) ?? const [0, 0, 0, 0];
      if (rawBbox.length < 4) continue;
      final x1 = destRect.left + (rawBbox[0] as num).toDouble() * scaleX;
      final y1 = destRect.top + (rawBbox[1] as num).toDouble() * scaleY;
      final x2 = destRect.left + (rawBbox[2] as num).toDouble() * scaleX;
      final y2 = destRect.top + (rawBbox[3] as num).toDouble() * scaleY;
      final rect = Rect.fromLTRB(x1, y1, x2, y2);
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(6)),
        b['kind'] == 'threat' ? threatPaint : boxPaint,
      );

      final cls = (b['class_name'] ?? 'object').toString();
      final conf =
          (((b['confidence'] as num?)?.toDouble() ?? 0.0) * 100).round();
      final textSpan = TextSpan(
        text: '$cls $conf%',
        style: AppTypography.caption.copyWith(
          color: AppColors.foreground,
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
      );
      final tp = TextPainter(text: textSpan, textDirection: TextDirection.ltr)
        ..layout();

      final pillHeight = tp.height + 4;
      final pillWidth = tp.width + 10;
      final pillY = (y1 - pillHeight - 4) < 4
          ? (y1 + 4).clamp(0.0, size.height - pillHeight)
          : (y1 - pillHeight - 4);
      final pillX =
          x1.clamp(0.0, (size.width - pillWidth).clamp(0.0, size.width));

      final pillRect = Rect.fromLTWH(pillX, pillY, pillWidth, pillHeight);
      final pillRRect = RRect.fromRectAndRadius(
          pillRect, const Radius.circular(AppRadii.pill));
      canvas.drawRRect(pillRRect, pillPaint);
      canvas.drawRRect(pillRRect, pillBorderPaint);
      tp.paint(canvas, Offset(pillRect.left + 5, pillRect.top + 2));
    }
  }

  @override
  bool shouldRepaint(covariant _DetectionBoxPainter oldDelegate) =>
      oldDelegate.boxes != boxes ||
      oldDelegate.frameWidth != frameWidth ||
      oldDelegate.frameHeight != frameHeight;
}

class LiveCameraFeedWidget extends StatefulWidget {
  final String cameraId;
  final bool isOnline;
  final String? baseUrl;
  final String? token;
  final int fallbackTick;
  final bool showBoxes;

  const LiveCameraFeedWidget({
    super.key,
    required this.cameraId,
    required this.isOnline,
    required this.baseUrl,
    required this.token,
    required this.fallbackTick,
    this.showBoxes = true,
  });

  @override
  State<LiveCameraFeedWidget> createState() => _LiveCameraFeedWidgetState();
}

class _LiveCameraFeedWidgetState extends State<LiveCameraFeedWidget> {
  WebSocket? _ws;
  Uint8List? _latestJpeg;
  double _frameW = 1280;
  double _frameH = 720;
  double _fps = 0.0;
  int _latencyMs = 0;
  String _profile = 'normal';
  List<Map<String, dynamic>> _boxes = [];

  @override
  void initState() {
    super.initState();
    if (widget.isOnline) _connectWs();
  }

  @override
  void didUpdateWidget(covariant LiveCameraFeedWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.cameraId != oldWidget.cameraId ||
        widget.isOnline != oldWidget.isOnline) {
      _disconnectWs();
      if (widget.isOnline) _connectWs();
    }
  }

  Future<void> _connectWs() async {
    final base = widget.baseUrl;
    final token = widget.token;
    if (base == null || token == null) return;
    try {
      final wsBase = base
          .replaceFirst('https://', 'wss://')
          .replaceFirst('http://', 'ws://');
      final ws = await WebSocket.connect(
        '$wsBase/api/v1/cameras/${Uri.encodeComponent(widget.cameraId)}/view',
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 4));
      if (!mounted) {
        await ws.close();
        return;
      }
      _ws = ws;
      ws.listen(
        (data) {
          if (!mounted) return;
          if (data is String) {
            _onText(data);
          } else if (data is List<int>) {
            _onFrame(data is Uint8List ? data : Uint8List.fromList(data));
          }
        },
        onDone: () => _ws = null,
        onError: (_) => _ws = null,
      );
    } catch (_) {
      _ws = null;
    }
  }

  void _onText(String data) {
    try {
      final msg = jsonDecode(data) as Map<String, dynamic>;
      if (msg['type'] != 'overlay') return;
      setState(() {
        _fps = (msg['fps_in'] as num?)?.toDouble() ?? _fps;
        _latencyMs = (msg['latency_ms'] as num?)?.toInt() ?? _latencyMs;
        _profile = (msg['profile'] as String?) ?? _profile;
        _boxes = ((msg['boxes'] as List?) ?? const [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      });
    } catch (_) {}
  }

  void _onFrame(Uint8List bytes) {
    if (bytes.length <= 22 ||
        bytes[0] != 0x53 ||
        bytes[1] != 0x53 ||
        bytes[2] != 0x46 ||
        bytes[3] != 0x31) {
      return;
    }
    final header = ByteData.sublistView(bytes, 0, 22);
    setState(() {
      _frameW = header.getUint16(6).toDouble();
      _frameH = header.getUint16(8).toDouble();
      _latestJpeg = Uint8List.sublistView(bytes, 22);
    });
  }

  void _disconnectWs() {
    try {
      _ws?.close();
    } catch (_) {}
    _ws = null;
  }

  @override
  void dispose() {
    _disconnectWs();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.isOnline) {
      return const ColoredBox(
        color: AppColors.background,
        child: Center(
          child: AppIcon(
            'video-off',
            size: 28,
            color: AppColors.foregroundSecondary,
          ),
        ),
      );
    }

    return Container(
      color: AppColors.background,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (_latestJpeg != null)
            Image.memory(
              _latestJpeg!,
              fit: BoxFit.contain,
              gaplessPlayback: true,
            )
          else if (widget.baseUrl != null && widget.token != null)
            Image.network(
              '${widget.baseUrl}/api/v1/cameras/${widget.cameraId}/frame?t=${widget.fallbackTick}',
              headers: {'Authorization': 'Bearer ${widget.token}'},
              fit: BoxFit.contain,
              gaplessPlayback: true,
              errorBuilder: (_, __, ___) => Center(
                child: Text(
                  'Waiting for 16:9 frame…',
                  style: AppTypography.caption.copyWith(
                    color: AppColors.foregroundSecondary,
                  ),
                ),
              ),
            ),
          if (widget.showBoxes && _boxes.isNotEmpty)
            CustomPaint(
              painter: _DetectionBoxPainter(
                boxes: _boxes,
                frameWidth: _frameW,
                frameHeight: _frameH,
              ),
            ),
        ],
      ),
    );
  }
}

class LiveCamerasScreen extends StatefulWidget {
  final ApiClient apiClient;
  final void Function(String cameraId)? onCreateRules;
  final VoidCallback? onClose;

  const LiveCamerasScreen({
    super.key,
    required this.apiClient,
    this.onCreateRules,
    this.onClose,
  });

  @override
  State<LiveCamerasScreen> createState() => _LiveCamerasScreenState();
}

class _LiveCamerasScreenState extends State<LiveCamerasScreen> {
  List<Map<String, dynamic>> _cameras = [];
  bool _showBoxes = true;
  bool _showAllWall = false;
  Timer? _timer;
  String? _error;
  String? _base;
  String? _token;
  int _tick = 0;
  String? _selectedCameraId;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(milliseconds: 650), (_) {
      if (mounted) setState(() => _tick++);
      if (_tick % 8 == 0) _load();
    });
  }

  Future<void> _load() async {
    try {
      final store = AuthStore();
      final response = await widget.apiClient.dio.get('/api/v1/cameras');
      final base = await store.getApiBaseUrl();
      final token = await store.getDeviceToken();
      if (mounted) {
        setState(() {
          _cameras = (response.data as List)
              .map((c) => Map<String, dynamic>.from(c as Map))
              .toList();
          if (_cameras.isNotEmpty &&
              !_cameras.any((c) => c['id'] == _selectedCameraId)) {
            _selectedCameraId = _cameras.first['id'] as String;
          }
          _base = base;
          _token = token;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Cannot reach your laptop from this network.');
      }
    }
  }

  Future<void> _snapshot(String id) async {
    HapticFeedback.selectionClick();
    try {
      final response =
          await widget.apiClient.dio.post('/api/v1/cameras/$id/snapshots');
      if (!mounted) return;
      _showMedia(
        '16:9 Snapshot saved on laptop',
        response.data['url'] as String,
      );
    } catch (e) {
      if (mounted) setState(() => _error = 'Snapshot failed: $e');
    }
  }

  void _showMedia(String title, String url, {bool video = false}) {
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
                    child: Text(title, style: AppTypography.cardHeading),
                  ),
                  GlassCircleButton(
                    svgAsset: 'x-01',
                    compact: true,
                    tooltip: 'Close',
                    onTap: () => Navigator.pop(sheet),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              EvidenceMedia(url: url, video: video, autoPlay: video),
              const SizedBox(height: AppSpacing.md),
              AppButton.secondary(
                label: 'Done',
                expand: true,
                onPressed: () => Navigator.pop(sheet),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _showTimelineAndRecordings(Map<String, dynamic> camera) async {
    HapticFeedback.selectionClick();
    final id = camera['id'] as String;
    final name = camera['name'] as String;
    try {
      final timelineRes =
          await widget.apiClient.dio.get('/api/v1/cameras/$id/timeline');
      final data = Map<String, dynamic>.from(timelineRes.data as Map);
      final segments = ((data['segments'] as List?) ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final snapshots = ((data['snapshots'] as List?) ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      if (!mounted) return;

      String? selectedUrl;
      bool selectedIsVideo = true;
      if (segments.isNotEmpty) {
        selectedUrl =
            (segments.last['stream_url'] ?? segments.last['url'] ?? '')
                .toString();
        selectedIsVideo = true;
      } else if (snapshots.isNotEmpty) {
        selectedUrl = (snapshots.first['url'] ?? '').toString();
        selectedIsVideo = false;
      }

      String? exportNote;

      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: AppColors.surface,
        builder: (sheet) => StatefulBuilder(
          builder: (sheetCtx, setSheet) => SafeArea(
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
                            Text(
                              '$name · 24h Timeline',
                              style: AppTypography.cardHeading,
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${segments.length} MP4 segments · ${snapshots.length} snapshots',
                              style: AppTypography.support,
                            ),
                          ],
                        ),
                      ),
                      GlassCircleButton(
                        svgAsset: 'x-01',
                        compact: true,
                        tooltip: 'Close',
                        onTap: () => Navigator.pop(sheet),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.md),
                  if (selectedUrl != null && selectedUrl!.isNotEmpty) ...[
                    EvidenceMedia(
                      url: selectedUrl!,
                      video: selectedIsVideo,
                      autoPlay: selectedIsVideo,
                    ),
                    const SizedBox(height: AppSpacing.md),
                  ] else
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        vertical: AppSpacing.lg,
                      ),
                      child: Text(
                        'No 10-second segments recorded yet. Keep streaming to record automatically.',
                        style: AppTypography.support,
                        textAlign: TextAlign.center,
                      ),
                    ),
                  if (segments.isNotEmpty) ...[
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Recorded segments',
                            style: AppTypography.cardTitle),
                        AppCapsule(
                          label: 'Export clip range',
                          svgAsset: 'upload-02',
                          onTap: () async {
                            try {
                              final first = (segments.first['started_at'] ??
                                      segments.first['start_ts'])
                                  .toString();
                              final last = (segments.last['ended_at'] ??
                                      segments.last['end_ts'] ??
                                      DateTime.now().toIso8601String())
                                  .toString();
                              await widget.apiClient.dio.post(
                                '/api/v1/cameras/$id/exports',
                                data: {'from_ts': first, 'to_ts': last},
                              );
                              setSheet(
                                () => exportNote =
                                    'Clip range exported on your laptop.',
                              );
                            } catch (e) {
                              setSheet(
                                () => exportNote = 'Export failed: $e',
                              );
                            }
                          },
                        ),
                      ],
                    ),
                    if (exportNote != null) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(exportNote!, style: AppTypography.caption),
                    ],
                    const SizedBox(height: AppSpacing.sm),
                    SizedBox(
                      height: 44,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: segments.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(width: AppSpacing.sm),
                        itemBuilder: (_, idx) {
                          final item = segments[segments.length - 1 - idx];
                          final streamUrl =
                              (item['stream_url'] ?? item['url'] ?? '')
                                  .toString();
                          final rawStart =
                              (item['started_at'] ?? '').toString();
                          final label = rawStart.length >= 19
                              ? rawStart.substring(11, 19)
                              : 'Seg ${segments.length - idx}';
                          return AppChip(
                            label: label,
                            leadingSvg: 'play-03',
                            selected:
                                selectedIsVideo && selectedUrl == streamUrl,
                            onTap: () => setSheet(() {
                              selectedUrl = streamUrl;
                              selectedIsVideo = true;
                            }),
                          );
                        },
                      ),
                    ),
                  ],
                  if (snapshots.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.md),
                    Text('Saved snapshots', style: AppTypography.cardTitle),
                    const SizedBox(height: AppSpacing.sm),
                    SizedBox(
                      height: 44,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: snapshots.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(width: AppSpacing.sm),
                        itemBuilder: (_, idx) {
                          final snap = snapshots[idx];
                          final url = (snap['url'] ?? '').toString();
                          return AppChip(
                            label: 'Snapshot ${idx + 1}',
                            leadingSvg: 'camera-01',
                            selected: !selectedIsVideo && selectedUrl == url,
                            onTap: () => setSheet(() {
                              selectedUrl = url;
                              selectedIsVideo = false;
                            }),
                          );
                        },
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      );
    } catch (e) {
      if (mounted) setState(() => _error = 'Timeline unavailable: $e');
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Widget _buildCameraTile(
    Map<String, dynamic> camera, {
    required bool isWall,
    required bool isFocused,
    bool compact = false,
  }) {
    final id = camera['id'] as String;
    final name = (camera['name'] ?? id).toString();
    final isOnline = camera['is_online'] == true;

    return AppCard(
      padding: EdgeInsets.zero,
      border: Border.all(
        color: isFocused ? AppColors.foreground : AppColors.divider,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    name,
                    style: AppTypography.cardHeading,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (isWall)
                  GlassCircleButton(
                    svgAsset: 'expand-01',
                    compact: true,
                    tooltip: 'Focus camera',
                    onTap: () => setState(() {
                      _selectedCameraId = id;
                      _showAllWall = false;
                    }),
                  ),
              ],
            ),
          ),
          ClipRRect(
            borderRadius: BorderRadius.circular(AppRadii.lg),
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: LiveCameraFeedWidget(
                cameraId: id,
                isOnline: isOnline,
                baseUrl: _base,
                token: _token,
                fallbackTick: _tick,
                showBoxes: _showBoxes,
              ),
            ),
          ),
          if (!compact)
            Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: [
                  if (isOnline)
                    AppChip(
                      label: 'Snapshot',
                      leadingSvg: 'camera-01',
                      selected: false,
                      onTap: () => _snapshot(id),
                    ),
                  AppChip(
                    label: 'Timeline',
                    leadingSvg: 'clock-backward',
                    selected: false,
                    onTap: () => _showTimelineAndRecordings(camera),
                  ),
                  AppChip(
                    label: _showBoxes ? 'Hide boxes' : 'Show boxes',
                    leadingSvg: 'eye-open',
                    selected: _showBoxes,
                    onTap: () => setState(() => _showBoxes = !_showBoxes),
                  ),
                  if (widget.onCreateRules != null)
                    AppChip(
                      label: 'Rules',
                      leadingSvg: 'shield-check',
                      selected: false,
                      onTap: () => widget.onCreateRules!(id),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final onlineCount = _cameras.where((c) => c['is_online'] == true).length;
    final selectedCamera =
        _cameras.where((c) => c['id'] == _selectedCameraId).firstOrNull ??
            (_cameras.isNotEmpty ? _cameras.first : null);

    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.md,
          AppSpacing.lg,
          AppSpacing.xl,
        ),
        children: [
          // Top Header Row
          Row(
            children: [
              if (widget.onClose != null) ...[
                GlassCircleButton(
                  svgAsset: 'arrow-left',
                  compact: true,
                  tooltip: 'Back',
                  onTap: widget.onClose,
                ),
                const SizedBox(width: AppSpacing.sm),
              ],
              Expanded(
                child: Text(
                  _showAllWall ? 'Live wall' : 'Cameras',
                  style: AppTypography.screenTitle,
                ),
              ),
              if (_cameras.length > 1)
                GlassCircleButton(
                  svgAsset: 'grid-01',
                  active: _showAllWall,
                  tooltip:
                      _showAllWall ? 'Single camera view' : 'All cameras wall',
                  onTap: () => setState(() => _showAllWall = !_showAllWall),
                ),
              const SizedBox(width: AppSpacing.xs),
              GlassCircleButton(
                svgAsset: 'refresh-01',
                tooltip: 'Refresh cameras',
                onTap: _load,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),

          const SizedBox(height: AppSpacing.lg),
          Row(
            children: [
              Expanded(child: _cameraMetric('Cameras', '${_cameras.length}')),
              const SizedBox(width: AppSpacing.md),
              Expanded(child: _cameraMetric('Live', '$onlineCount')),
            ],
          ),

          if (_error != null) ...[
            const SizedBox(height: AppSpacing.md),
            AppCard(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Row(
                children: [
                  const AppIcon('alert-circle', size: 18),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(child: Text(_error!, style: AppTypography.support)),
                ],
              ),
            ),
          ],

          // Camera Selector Chips (Single View when >1 camera)
          if (_cameras.length > 1 && !_showAllWall) ...[
            const SizedBox(height: AppSpacing.md),
            SizedBox(
              height: 40,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: _cameras.length,
                separatorBuilder: (_, __) =>
                    const SizedBox(width: AppSpacing.sm),
                itemBuilder: (_, idx) {
                  final c = _cameras[idx];
                  final id = c['id'] as String;
                  final isSel = id == _selectedCameraId;
                  return AppChip(
                    label: '${c['name'] ?? id}',
                    leadingSvg:
                        c['is_online'] == true ? 'video-on' : 'video-off',
                    selected: isSel,
                    onTap: () => setState(() => _selectedCameraId = id),
                  );
                },
              ),
            ),
          ],

          const SizedBox(height: AppSpacing.lg),

          if (_cameras.isEmpty)
            const EmptyState(
              svgAsset: 'video-on',
              title: 'No cameras connected yet',
              subtitle:
                  'Open SafeSpace on a paired phone and start Camera Station to stream in 16:9.',
            )
          else if (_showAllWall) ...[
            for (final cam in _cameras) ...[
              _buildCameraTile(
                cam,
                isWall: true,
                isFocused: cam['id'] == _selectedCameraId,
              ),
              const SizedBox(height: AppSpacing.md),
            ],
            const SizedBox(height: AppSpacing.md),
          ] else if (selectedCamera != null) ...[
            // Single Focused Camera View: Strict 16:9
            _buildCameraTile(
              selectedCamera,
              isWall: false,
              isFocused: true,
            ),
            const SizedBox(height: AppSpacing.lg),
          ],

          const SizedBox(height: AppSpacing.xs),
          AppButton.secondary(
            label: 'Analyze a recorded video or photo',
            svgAsset: 'upload-02',
            expand: true,
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => AnalyzeScreen(
                  apiClient: widget.apiClient,
                  eventsRepository: EventsRepository(widget.apiClient),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _cameraMetric(String label, String value) => AppCard(
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
