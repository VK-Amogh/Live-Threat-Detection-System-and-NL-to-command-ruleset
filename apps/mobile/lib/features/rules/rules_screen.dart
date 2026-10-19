import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/auth_store.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_icon.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/page_header.dart';
import '../../data/repositories/rules_repository.dart';

class _ZonePainter extends CustomPainter {
  final Map<String, List<List<int>>> zones;
  final Map<String, List<List<int>>> lines;
  final List<Offset> draftPoints;
  final double snapshotW;
  final double snapshotH;

  _ZonePainter({
    required this.zones,
    required this.lines,
    required this.draftPoints,
    required this.snapshotW,
    required this.snapshotH,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final sx = size.width / snapshotW;
    final sy = size.height / snapshotH;

    final fillPaint = Paint()
      ..color = AppColors.highlight
      ..style = PaintingStyle.fill;
    final strokePaint = Paint()
      ..color = AppColors.foreground
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;
    final labelBgPaint = Paint()
      ..color = AppColors.glassFill
      ..style = PaintingStyle.fill;

    for (final entry in zones.entries) {
      final pts = entry.value;
      if (pts.length < 3) continue;
      final path = Path();
      path.moveTo(pts.first[0] * sx, pts.first[1] * sy);
      for (var i = 1; i < pts.length; i++) {
        path.lineTo(pts[i][0] * sx, pts[i][1] * sy);
      }
      path.close();
      canvas.drawPath(path, fillPaint);
      canvas.drawPath(path, strokePaint);
      _drawLabel(
        canvas,
        entry.key,
        Offset(pts.first[0] * sx, pts.first[1] * sy),
        labelBgPaint,
      );
    }

    for (final entry in lines.entries) {
      final pts = entry.value;
      if (pts.length < 2) continue;
      final p1 = Offset(pts[0][0] * sx, pts[0][1] * sy);
      final p2 = Offset(pts[1][0] * sx, pts[1][1] * sy);
      canvas.drawLine(p1, p2, strokePaint);
      _drawLabel(canvas, entry.key, p1, labelBgPaint);
    }

    if (draftPoints.isNotEmpty) {
      final dotPaint = Paint()..color = AppColors.foreground;
      for (var i = 0; i < draftPoints.length; i++) {
        final pt = Offset(draftPoints[i].dx * sx, draftPoints[i].dy * sy);
        canvas.drawCircle(pt, 5, dotPaint);
        if (i > 0) {
          final prev = Offset(
            draftPoints[i - 1].dx * sx,
            draftPoints[i - 1].dy * sy,
          );
          canvas.drawLine(prev, pt, strokePaint);
        }
      }
    }
  }

  void _drawLabel(Canvas canvas, String text, Offset anchor, Paint bgPaint) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: AppTypography.caption.copyWith(
          color: AppColors.foreground,
          fontSize: 11,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final rect =
        Rect.fromLTWH(anchor.dx, anchor.dy, tp.width + 10, tp.height + 4);
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(999)),
      bgPaint,
    );
    tp.paint(canvas, Offset(rect.left + 5, rect.top + 2));
  }

  @override
  bool shouldRepaint(covariant _ZonePainter oldDelegate) => true;
}

class RulesScreen extends StatefulWidget {
  final RulesRepository repository;
  final String? initialCameraId;
  const RulesScreen({
    super.key,
    required this.repository,
    this.initialCameraId,
  });

  @override
  State<RulesScreen> createState() => _RulesScreenState();
}

class _RulesScreenState extends State<RulesScreen> {
  final _text = TextEditingController();
  final _rulesetName = TextEditingController();
  List<Map<String, dynamic>> _cameras = [];
  List<Map<String, dynamic>> _rules = [];
  List<Map<String, dynamic>> _templates = [];
  List<Map<String, dynamic>> _rulesets = [];
  Set<String> _selectedCameras = {};
  String _systemMode = 'HOME';
  String? _cameraId;
  String? _selectedTemplateId;
  Map<String, dynamic>? _draft;
  Map<String, dynamic>? _dryRunResult;
  String? _error;
  String? _notice;
  bool _visual = false;
  bool _scheduleEnabled = false;
  bool _multiCameraMode = false;
  final Set<String> _scheduleDays = {
    'mon',
    'tue',
    'wed',
    'thu',
    'fri',
    'sat',
    'sun',
  };
  String _startTime = '22:00';
  String _endTime = '06:00';
  bool _ack = false;
  bool _busy = false;
  bool _creating = false;

  void _showMonitoringModes() {
    HapticFeedback.selectionClick();
    const modes = [
      ('HOME', 'Home', 'Standard perimeter and weapon alerts active.'),
      ('AWAY', 'Away', 'Full intrusion, loitering, and motion rules active.'),
      ('NIGHT', 'Night', 'Elevated night-watch sensitivity across all zones.'),
      (
        'DISARMED',
        'Disarmed',
        'Pauses rule alerts while cameras keep recording.'
      ),
    ];
    showModalBottomSheet<void>(
      context: context,
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
                    child: Text(
                      'Monitoring mode',
                      style: AppTypography.cardHeading,
                    ),
                  ),
                  GlassCircleButton(
                    svgAsset: 'x-01',
                    compact: true,
                    onTap: () => Navigator.pop(sheet),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Disarmed pauses rule alerts while cameras continue recording.',
                style: AppTypography.support,
              ),
              const SizedBox(height: AppSpacing.lg),
              for (final (key, title, desc) in modes)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: AppCard(
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    border: Border.all(
                      color: _systemMode == key
                          ? AppColors.foreground
                          : AppColors.divider,
                      width: _systemMode == key ? 1.5 : 1.0,
                    ),
                    onTap: () async {
                      Navigator.pop(sheet);
                      try {
                        final updated =
                            await widget.repository.setSystemMode(key);
                        if (mounted) setState(() => _systemMode = updated);
                      } catch (error) {
                        if (mounted) setState(() => _error = '$error');
                      }
                    },
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(title, style: AppTypography.cardTitle),
                              const SizedBox(height: 2),
                              Text(desc, style: AppTypography.caption),
                            ],
                          ),
                        ),
                        if (_systemMode == key)
                          const AppIcon(
                            'check-01',
                            size: 18,
                            color: AppColors.foreground,
                          ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _cameraId = widget.initialCameraId;
    _load();
  }

  @override
  void didUpdateWidget(covariant RulesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialCameraId != oldWidget.initialCameraId &&
        widget.initialCameraId != null) {
      _cameraId = widget.initialCameraId;
      _selectedCameras = {widget.initialCameraId!};
      _draft = null;
      _load();
    }
  }

  @override
  void dispose() {
    _text.dispose();
    _rulesetName.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final cameras = await widget.repository.cameras();
      final tmpls = await widget.repository
          .templates()
          .catchError((_) => <Map<String, dynamic>>[]);
      final rsets = await widget.repository
          .rulesets()
          .catchError((_) => <Map<String, dynamic>>[]);
      final mode =
          await widget.repository.getSystemMode().catchError((_) => 'HOME');
      final selected = cameras.any((camera) => camera['id'] == _cameraId)
          ? _cameraId
          : (cameras.isEmpty ? null : cameras.first['id'] as String);
      final rules = selected == null
          ? <Map<String, dynamic>>[]
          : await widget.repository.rules(selected);
      if (mounted) {
        setState(() {
          _cameras = cameras;
          _cameraId = selected;
          if (_selectedCameras.isEmpty && selected != null) {
            _selectedCameras = {selected};
          }
          _rules = rules;
          _templates = tmpls;
          _rulesets = rsets;
          _systemMode = mode;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    }
  }

  void _applyTemplate(Map<String, dynamic> t) {
    HapticFeedback.selectionClick();
    setState(() {
      _selectedTemplateId = t['id'] as String?;
      _rulesetName.text = (t['name'] ?? '').toString();
      _text.text = (t['default_text'] ?? '').toString();
      final sched = t['default_schedule'] as Map?;
      if (sched != null) {
        _scheduleEnabled = true;
        _startTime = (sched['start_time'] ?? '22:00').toString();
        _endTime = (sched['end_time'] ?? '06:00').toString();
        _scheduleDays
          ..clear()
          ..addAll(
            ((sched['days'] as List?) ??
                    const ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'])
                .map((day) => day.toString()),
          );
      } else {
        _scheduleEnabled = false;
      }
      _notice =
          'Template "${t['name']}" selected. Compile it, then activate the ruleset below to start alerts.';
    });
  }

  Future<void> _compile() async {
    if (_cameraId == null || _text.text.trim().isEmpty) return;
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
      _draft = null;
      _dryRunResult = null;
    });
    try {
      final draft = await widget.repository.compile(
        _cameraId!,
        _text.text.trim(),
        _visual,
      );
      if (mounted) {
        setState(() {
          _draft = draft;
          _ack = false;
        });
      }
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _deployRuleset() async {
    if (_scheduleEnabled && _scheduleDays.isEmpty) {
      setState(() => _error = 'Choose at least one day for the schedule.');
      return;
    }
    final targets = _multiCameraMode && _selectedCameras.isNotEmpty
        ? _selectedCameras.toList()
        : (_cameraId != null ? [_cameraId!] : <String>[]);
    if (targets.isEmpty || _text.text.trim().isEmpty) return;
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      final created = await widget.repository.createRuleset(
        name: _rulesetName.text.trim().isNotEmpty
            ? _rulesetName.text.trim()
            : _text.text
                .trim()
                .substring(0, _text.text.trim().length.clamp(0, 40)),
        cameraIds: targets,
        text: _text.text.trim(),
        templateId: _selectedTemplateId,
        schedule: _scheduleEnabled
            ? {
                'days': _scheduleDays.toList(),
                'start_time': _startTime,
                'end_time': _endTime,
                'timezone': 'local',
              }
            : null,
        visual: _visual,
      );
      if (mounted) {
        setState(
          () => _notice =
              'Compiled ruleset "${created['name']}". Confirm readback below to activate.',
        );
      }
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _activateRuleset(Map<String, dynamic> rs) async {
    final hash = rs['readback_hash'] as String?;
    if (hash == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.activateRuleset(rs['id'] as String, hash);
      if (mounted) {
        setState(() => _notice = 'Ruleset "${rs['name']}" activated.');
      }
      await _load();
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _activate(Map<String, dynamic> record) async {
    final spec = Map<String, dynamic>.from(record['spec'] as Map);
    if (spec['support_level'] == 'EXPERIMENTAL' && !_ack) {
      setState(() => _error = 'Acknowledge the experimental limitation first.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.activate(
        spec['rule_id'] as String,
        spec['version'] as int,
        record['readback_hash'] as String,
        _ack,
      );
      if (mounted) {
        setState(() {
          _draft = null;
          _notice = 'Rule "${spec['name']}" is now active.';
        });
      }
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _disable(Map<String, dynamic> record) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.disable(
        record['id'] as String,
        record['version'] as int,
      );
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _dryRun(String ruleId) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final res = await widget.repository.dryRun(ruleId);
      if (mounted) setState(() => _dryRunResult = res);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickScheduleTime(bool start) async {
    final current = start ? _startTime : _endTime;
    final parts = current.split(':');
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(
        hour: int.parse(parts[0]),
        minute: int.parse(parts[1]),
      ),
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
        child: child!,
      ),
    );
    if (picked == null || !mounted) return;
    final value =
        '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}';
    setState(() {
      if (start) {
        _startTime = value;
      } else {
        _endTime = value;
      }
    });
  }

  Future<void> _openZoneEditor() async {
    final camId = _cameraId;
    if (camId == null) return;
    HapticFeedback.selectionClick();
    final existing =
        await widget.repository.getGeometry(camId).catchError((_) => null);
    final store = AuthStore();
    final baseUrl = await store.getApiBaseUrl();
    final token = await store.getDeviceToken();
    if (!mounted) return;

    const double snapW = 1280;
    const double snapH = 720;
    final prevW = (existing?['snapshot_width'] as num?)?.toDouble() ?? snapW;
    final prevH = (existing?['snapshot_height'] as num?)?.toDouble() ?? snapH;
    final scaleX = snapW / prevW;
    final scaleY = snapH / prevH;

    final zones = <String, List<List<int>>>{};
    final lines = <String, List<List<int>>>{};
    if (existing != null) {
      final zMap = (existing['zones'] as Map?) ?? {};
      for (final e in zMap.entries) {
        zones[e.key.toString()] = ((e.value as List?) ?? []).map((pt) {
          final list = (pt as List).map((n) => (n as num).toDouble()).toList();
          return [(list[0] * scaleX).round(), (list[1] * scaleY).round()];
        }).toList();
      }
      final lMap = (existing['lines'] as Map?) ?? {};
      for (final e in lMap.entries) {
        lines[e.key.toString()] = ((e.value as List?) ?? []).map((pt) {
          final list = (pt as List).map((n) => (n as num).toDouble()).toList();
          return [(list[0] * scaleX).round(), (list[1] * scaleY).round()];
        }).toList();
      }
    }

    final draftPts = <Offset>[];
    final nameCtrl = TextEditingController(text: 'driveway');
    var mode = 'zone';

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) => SafeArea(
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
                            '16:9 Zones & crossing lines',
                            style: AppTypography.cardHeading,
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Tap points on the 16:9 camera frame to define named regions.',
                            style: AppTypography.support,
                          ),
                        ],
                      ),
                    ),
                    GlassCircleButton(
                      svgAsset: 'x-01',
                      compact: true,
                      onTap: () => Navigator.pop(ctx),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.md),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: nameCtrl,
                        style: AppTypography.body,
                        decoration: const InputDecoration(
                          hintText: 'Region name (e.g. driveway, gate)',
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    AppChip(
                      label: 'Zone',
                      selected: mode == 'zone',
                      onTap: () => setSheetState(() {
                        mode = 'zone';
                        draftPts.clear();
                      }),
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    AppChip(
                      label: 'Line',
                      selected: mode == 'line',
                      onTap: () => setSheetState(() {
                        mode = 'line';
                        draftPts.clear();
                      }),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.md),
                LayoutBuilder(
                  builder: (ctx, constraints) {
                    final w = constraints.maxWidth;
                    final h = w * 9 / 16; // Strict 16:9 canvas
                    return GestureDetector(
                      onTapDown: (details) {
                        HapticFeedback.selectionClick();
                        final x =
                            (details.localPosition.dx / w * snapW).round();
                        final y =
                            (details.localPosition.dy / h * snapH).round();
                        setSheetState(() {
                          draftPts.add(Offset(x.toDouble(), y.toDouble()));
                          if (mode == 'line' &&
                              draftPts.length == 2 &&
                              nameCtrl.text.trim().isNotEmpty) {
                            lines[nameCtrl.text.trim()] = draftPts
                                .map((p) => [p.dx.round(), p.dy.round()])
                                .toList();
                            draftPts.clear();
                          }
                        });
                      },
                      child: Container(
                        width: w,
                        height: h,
                        decoration: BoxDecoration(
                          color: AppColors.background,
                          borderRadius: BorderRadius.circular(AppRadii.lg),
                          border: Border.all(
                            color: AppColors.divider,
                            width: 1.0,
                          ),
                        ),
                        clipBehavior: Clip.antiAlias,
                        child: Stack(
                          fit: StackFit.expand,
                          children: [
                            if (token != null)
                              Image.network(
                                '$baseUrl/api/v1/cameras/$camId/frame',
                                headers: {'Authorization': 'Bearer $token'},
                                fit: BoxFit.contain,
                                errorBuilder: (_, __, ___) => Center(
                                  child: Text(
                                    'Tap to place 16:9 geometry points (1280×720)',
                                    style: AppTypography.caption,
                                  ),
                                ),
                              ),
                            CustomPaint(
                              painter: _ZonePainter(
                                zones: zones,
                                lines: lines,
                                draftPoints: draftPts,
                                snapshotW: snapW,
                                snapshotH: snapH,
                              ),
                            ),
                            const Positioned(
                              top: AppSpacing.sm,
                              right: AppSpacing.sm,
                              child: AppCapsule(label: '16:9 · 1280×720'),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
                if (zones.isNotEmpty || lines.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Wrap(
                    spacing: AppSpacing.xs,
                    runSpacing: AppSpacing.xs,
                    children: [
                      for (final z in zones.keys)
                        AppCapsule(
                          label: 'Zone: $z',
                          svgAsset: 'x-01',
                          onTap: () => setSheetState(() => zones.remove(z)),
                        ),
                      for (final l in lines.keys)
                        AppCapsule(
                          label: 'Line: $l',
                          svgAsset: 'x-01',
                          onTap: () => setSheetState(() => lines.remove(l)),
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: AppSpacing.md),
                Row(
                  children: [
                    if (draftPts.isNotEmpty) ...[
                      AppButton.secondary(
                        label: 'Clear',
                        onPressed: () => setSheetState(() => draftPts.clear()),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                    ],
                    if (mode == 'zone') ...[
                      Expanded(
                        child: AppButton.secondary(
                          label: 'Add zone (${draftPts.length} pts)',
                          expand: true,
                          onPressed: draftPts.length >= 3 &&
                                  nameCtrl.text.trim().isNotEmpty
                              ? () {
                                  setSheetState(() {
                                    zones[nameCtrl.text.trim()] = draftPts
                                        .map(
                                          (p) => [p.dx.round(), p.dy.round()],
                                        )
                                        .toList();
                                    draftPts.clear();
                                  });
                                }
                              : null,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                    ],
                    Expanded(
                      child: AppButton(
                        label: 'Save geometry',
                        svgAsset: 'check-01',
                        expand: true,
                        onPressed: () async {
                          await widget.repository.saveGeometry(camId, {
                            'snapshot_width': snapW.toInt(),
                            'snapshot_height': snapH.toInt(),
                            'zones': zones,
                            'lines': lines,
                            'homography': null,
                          });
                          if (ctx.mounted) Navigator.pop(ctx);
                          await _load();
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
    );
  }

  Widget _ruleCard(Map<String, dynamic> record, {bool isDraft = false}) {
    final spec = Map<String, dynamic>.from(record['spec'] as Map);
    final active = record['status'] == 'active';
    final canActivate =
        record['can_activate'] == true && record['readback_hash'] != null;
    final ruleId = (record['id'] ?? spec['rule_id']).toString();
    final supportLevel = '${spec['support_level'] ?? 'SUPPORTED'}';

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: AppCard(
        border: Border.all(
          color: (isDraft || active) ? AppColors.foreground : AppColors.divider,
          width: isDraft ? 1.5 : 1.0,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${spec['name']}',
                    style: AppTypography.cardHeading,
                  ),
                ),
                AppCapsule(
                  label: isDraft
                      ? 'Preview'
                      : (active ? 'Active' : '${record['status']}'),
                  inverted: active || isDraft,
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              '$supportLevel · v${record['version']}',
              style: AppTypography.caption,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              '${record['readback'] ?? record['text']}',
              style: AppTypography.body,
            ),
            if (spec['unsupported_reason'] != null) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                '${spec['unsupported_reason']}',
                style: AppTypography.support,
              ),
            ],
            if (!active && supportLevel == 'EXPERIMENTAL') ...[
              const SizedBox(height: AppSpacing.md),
              AppChip(
                label: 'I understand this rule is experimental',
                selected: _ack,
                onTap: () => setState(() => _ack = !_ack),
              ),
            ],
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                if (active)
                  Expanded(
                    child: AppButton.secondary(
                      label: 'Turn off rule',
                      svgAsset: 'x-01',
                      expand: true,
                      onPressed: _busy ? null : () => _disable(record),
                    ),
                  )
                else if (canActivate)
                  Expanded(
                    child: AppButton(
                      label: 'Activate rule',
                      svgAsset: 'check-01',
                      expand: true,
                      onPressed: _busy ? null : () => _activate(record),
                    ),
                  ),
                if (active || canActivate) const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: AppButton.secondary(
                    label: 'Dry-run test',
                    svgAsset: 'play-03',
                    expand: true,
                    onPressed: _busy ? null : () => _dryRun(ruleId),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          color: AppColors.foreground,
          backgroundColor: AppColors.surface,
          onRefresh: _load,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg,
              AppSpacing.md,
              AppSpacing.lg,
              AppSpacing.xl,
            ),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text('Rules', style: AppTypography.screenTitle),
                  ),
                  GlassCircleButton(
                    svgAsset: _creating ? 'x-01' : 'plus-01',
                    tooltip: _creating ? 'Close creator' : 'Create ruleset',
                    onTap: () => setState(() => _creating = !_creating),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.lg),

              // Quick Status & Utility Row
              Row(
                children: [
                  Expanded(
                    child: AppCard(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      onTap: _cameraId == null ? null : _openZoneEditor,
                      child: SizedBox(
                        height: 84,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const AppIcon(
                              'target-01',
                              size: 24,
                              color: AppColors.foreground,
                            ),
                            Text('Draw area', style: AppTypography.cardTitle),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: AppCard(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      onTap: _showMonitoringModes,
                      child: SizedBox(
                        height: 84,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const AppIcon(
                              'shield-01',
                              size: 24,
                              color: AppColors.foreground,
                            ),
                            Text('Mode', style: AppTypography.cardTitle),
                          ],
                        ),
                      ),
                    ),
                  ),
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
                      Expanded(
                        child: Text(_error!, style: AppTypography.support),
                      ),
                    ],
                  ),
                ),
              ],
              if (_notice != null) ...[
                const SizedBox(height: AppSpacing.md),
                AppCard(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Row(
                    children: [
                      const AppIcon('check-01', size: 18),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: Text(_notice!, style: AppTypography.body),
                      ),
                    ],
                  ),
                ),
              ],

              if (_creating) ...[
                // Ready-to-use Rule Templates Carousel
                if (_templates.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.xl),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Quick templates', style: AppTypography.cardHeading),
                      Text(
                        'Tap to pre-fill',
                        style: AppTypography.caption,
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  SizedBox(
                    height: 118,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: _templates.length,
                      separatorBuilder: (_, __) =>
                          const SizedBox(width: AppSpacing.sm),
                      itemBuilder: (_, idx) {
                        final t = _templates[idx];
                        final selected = _selectedTemplateId == t['id'];
                        return SizedBox(
                          width: 236,
                          child: AppCard(
                            padding: const EdgeInsets.all(AppSpacing.md),
                            border: Border.all(
                              color: selected
                                  ? AppColors.foreground
                                  : AppColors.divider,
                              width: selected ? 1.5 : 1.0,
                            ),
                            onTap: () => _applyTemplate(t),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        '${t['name']}',
                                        style: AppTypography.cardTitle,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                    if (selected)
                                      const AppCapsule(
                                        label: 'Loaded',
                                        inverted: true,
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                Expanded(
                                  child: Text(
                                    '${t['description']}',
                                    style: AppTypography.caption,
                                    maxLines: 3,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],

                const SizedBox(height: AppSpacing.xl),
                Text('Build a camera rule', style: AppTypography.cardHeading),
                const SizedBox(height: AppSpacing.sm),

                if (_cameras.isEmpty)
                  const EmptyState(
                    svgAsset: 'video-on',
                    title: 'No cameras connected',
                    subtitle:
                        'Connect a camera station to create your first rule.',
                  )
                else
                  AppCard(
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text('1. Target camera', style: AppTypography.caption),
                        const SizedBox(height: AppSpacing.xs),
                        SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: Row(
                            children: [
                              for (final camera in _cameras) ...[
                                AppChip(
                                  label: '${camera['name']}',
                                  leadingSvg: 'video-on',
                                  selected: _cameraId == camera['id'],
                                  onTap: () {
                                    setState(() {
                                      _cameraId = camera['id'] as String;
                                      if (!_multiCameraMode) {
                                        _selectedCameras = {_cameraId!};
                                      }
                                      _draft = null;
                                    });
                                    _load();
                                  },
                                ),
                                const SizedBox(width: AppSpacing.sm),
                              ],
                            ],
                          ),
                        ),
                        const SizedBox(height: AppSpacing.lg),
                        Text(
                          '2. What should trigger an alert?',
                          style: AppTypography.caption,
                        ),
                        const SizedBox(height: AppSpacing.xs),
                        TextField(
                          controller: _text,
                          maxLines: 3,
                          style: AppTypography.body,
                          decoration: const InputDecoration(
                            hintText:
                                'e.g. Alert when a person stays in the driveway zone for 5 seconds',
                          ),
                        ),
                        const SizedBox(height: AppSpacing.md),

                        // Option Chips Row
                        SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: Row(
                            children: [
                              AppChip(
                                label: _scheduleEnabled
                                    ? 'Schedule: $_startTime–$_endTime'
                                    : 'Schedule',
                                leadingSvg: 'clock-backward',
                                selected: _scheduleEnabled,
                                onTap: () => setState(
                                  () => _scheduleEnabled = !_scheduleEnabled,
                                ),
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              AppChip(
                                label: 'Visual AI summary',
                                leadingSvg: 'eye-open',
                                selected: _visual,
                                onTap: () => setState(() => _visual = !_visual),
                              ),
                              if (_cameras.length > 1) ...[
                                const SizedBox(width: AppSpacing.sm),
                                AppChip(
                                  label: 'Multi-camera group',
                                  leadingSvg: 'grid-01',
                                  selected: _multiCameraMode,
                                  onTap: () => setState(
                                    () => _multiCameraMode = !_multiCameraMode,
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),

                        if (_scheduleEnabled) ...[
                          const SizedBox(height: AppSpacing.md),
                          Row(
                            children: [
                              Expanded(
                                child: AppButton.secondary(
                                  label: 'From $_startTime',
                                  svgAsset: 'clock-backward',
                                  expand: true,
                                  onPressed: () => _pickScheduleTime(true),
                                ),
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              Expanded(
                                child: AppButton.secondary(
                                  label: 'Until $_endTime',
                                  svgAsset: 'clock-backward',
                                  expand: true,
                                  onPressed: () => _pickScheduleTime(false),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: AppSpacing.sm),
                          Wrap(
                            spacing: AppSpacing.xs,
                            runSpacing: AppSpacing.xs,
                            children: [
                              for (final day in const [
                                'mon',
                                'tue',
                                'wed',
                                'thu',
                                'fri',
                                'sat',
                                'sun',
                              ])
                                AppChip(
                                  label:
                                      day[0].toUpperCase() + day.substring(1),
                                  selected: _scheduleDays.contains(day),
                                  onTap: () => setState(() {
                                    _scheduleDays.contains(day)
                                        ? _scheduleDays.remove(day)
                                        : _scheduleDays.add(day);
                                  }),
                                ),
                            ],
                          ),
                        ],

                        if (_multiCameraMode) ...[
                          const SizedBox(height: AppSpacing.md),
                          Text(
                            'Cameras included in this group rule',
                            style: AppTypography.caption,
                          ),
                          const SizedBox(height: AppSpacing.xs),
                          Wrap(
                            spacing: AppSpacing.sm,
                            runSpacing: AppSpacing.xs,
                            children: [
                              for (final camera in _cameras)
                                AppChip(
                                  label: '${camera['name']}',
                                  selected: _selectedCameras.contains(
                                    camera['id'],
                                  ),
                                  onTap: () => setState(() {
                                    final id = camera['id'].toString();
                                    _selectedCameras.contains(id)
                                        ? _selectedCameras.remove(id)
                                        : _selectedCameras.add(id);
                                  }),
                                ),
                            ],
                          ),
                        ],

                        const SizedBox(height: AppSpacing.lg),
                        AppButton(
                          label: _busy
                              ? 'Compiling rule…'
                              : (_multiCameraMode
                                  ? 'Compile for ${_selectedCameras.length} cameras'
                                  : _selectedTemplateId != null
                                      ? 'Compile template'
                                      : 'Preview & compile rule'),
                          svgAsset: 'shield-check',
                          expand: true,
                          isLoading: _busy,
                          onPressed: _busy
                              ? null
                              : (_multiCameraMode || _selectedTemplateId != null
                                  ? _deployRuleset
                                  : _compile),
                        ),
                      ],
                    ),
                  ),

                // Compiled Draft Readback Card
                if (_draft != null) ...[
                  const SizedBox(height: AppSpacing.xl),
                  Text(
                    'Confirm compiled readback',
                    style: AppTypography.cardHeading,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  _ruleCard(
                    {
                      ..._draft!,
                      'status': 'draft',
                      'text': _text.text,
                      'version': (_draft!['spec'] as Map)['version'],
                    },
                    isDraft: true,
                  ),
                  for (final problem in (_draft!['problems'] as List? ?? []))
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                      child: Text('$problem', style: AppTypography.support),
                    ),
                  if (_draft!['can_activate'] == false)
                    AppButton.secondary(
                      label: 'Draw required 16:9 zone or crossing line',
                      svgAsset: 'target-01',
                      expand: true,
                      onPressed: _openZoneEditor,
                    ),
                ],

                // Dry-Run Result Card
                if (_dryRunResult != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  AppCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Dry-run verification',
                              style: AppTypography.cardTitle,
                            ),
                            AppCapsule(
                              label: _dryRunResult!['matched'] == true
                                  ? 'Matched'
                                  : 'No match',
                              inverted: _dryRunResult!['matched'] == true,
                            ),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.xs),
                        for (final r
                            in (_dryRunResult!['reasons'] as List? ?? []))
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text('$r', style: AppTypography.caption),
                          ),
                      ],
                    ),
                  ),
                ],
              ],

              // Multi-Camera Rulesets
              if (_rulesets.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.xl),
                Text(
                  'Multi-camera rulesets',
                  style: AppTypography.cardHeading,
                ),
                const SizedBox(height: AppSpacing.sm),
                for (final rs in _rulesets)
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.md),
                    child: AppCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Expanded(
                                child: Text(
                                  '${rs['name']}',
                                  style: AppTypography.cardTitle,
                                ),
                              ),
                              AppCapsule(
                                label: '${rs['status']}',
                                inverted: rs['status'] == 'active',
                              ),
                            ],
                          ),
                          const SizedBox(height: AppSpacing.xs),
                          Text(
                            '${rs['readback_text'] ?? rs['description'] ?? ''}',
                            style: AppTypography.body,
                          ),
                          if (rs['status'] != 'active' &&
                              rs['readback_hash'] != null) ...[
                            const SizedBox(height: AppSpacing.md),
                            AppButton(
                              label: 'Activate ruleset',
                              svgAsset: 'check-01',
                              expand: true,
                              onPressed:
                                  _busy ? null : () => _activateRuleset(rs),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
              ],

              // Active & Saved Rules for Selected Camera
              const SizedBox(height: AppSpacing.xl),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Existing rules',
                    style: AppTypography.cardHeading,
                  ),
                  AppCapsule(label: '${_rules.length} total'),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              if (_rules.isEmpty)
                AppCard(
                  child: Text(
                    'No rules yet. Tap + to create a ruleset.',
                    style: AppTypography.support,
                  ),
                )
              else
                for (final rule in _rules) _ruleCard(rule),
            ],
          ),
        ),
      ),
    );
  }
}
