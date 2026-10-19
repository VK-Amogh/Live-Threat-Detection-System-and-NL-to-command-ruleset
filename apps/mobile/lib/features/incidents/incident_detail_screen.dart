import 'package:flutter/material.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_dialog.dart';
import '../../core/widgets/app_icon.dart';
import '../../core/widgets/evidence_media.dart';
import '../../core/widgets/page_header.dart';
import '../../data/generated/models.dart';
import '../../data/repositories/events_repository.dart';

class IncidentDetailScreen extends StatefulWidget {
  final EventOut event;
  final EventsRepository eventsRepository;

  const IncidentDetailScreen({
    super.key,
    required this.event,
    required this.eventsRepository,
  });

  @override
  State<IncidentDetailScreen> createState() => _IncidentDetailScreenState();
}

class _IncidentDetailScreenState extends State<IncidentDetailScreen> {
  late EventOut _currentEvent;
  bool _isSubmitting = false;
  bool _aiBusy = false;
  Map<String, dynamic>? _ai;
  String? _ruleId;
  int? _ruleVersion;
  String? _uncertainty;
  int _selectedMediaIndex = 0;

  @override
  void initState() {
    super.initState();
    _currentEvent = widget.event;
    _selectDefaultMedia();
    widget.eventsRepository.revision.addListener(_loadAi);
    _loadAi();
  }

  void _selectDefaultMedia() {
    final idx =
        _currentEvent.media.indexWhere((m) => m.kind == MediaKind.CLIP);
    _selectedMediaIndex = idx >= 0 ? idx : 0;
  }

  @override
  void dispose() {
    widget.eventsRepository.revision.removeListener(_loadAi);
    super.dispose();
  }

  void _setAi(Map<String, dynamic> raw) {
    if (mounted) {
      setState(() {
        _currentEvent = EventOut.fromJson(raw);
        _ruleId = raw['rule_id'] as String?;
        _ruleVersion = raw['rule_version'] as int?;
        _uncertainty = raw['uncertainty'] as String?;
        _ai = raw['reasoning'] == null
            ? null
            : {
                'reasoning': raw['reasoning'],
                'disagrees': raw['ai_disagrees'] == true,
                'model': (raw['models']?['vlm']?['name']),
              };
      });
    }
  }

  Future<void> _loadAi() async {
    try {
      final response = await widget.eventsRepository.apiClient.dio
          .get('/api/v1/events/${widget.event.id}');
      _setAi(Map<String, dynamic>.from(response.data));
    } catch (_) {}
  }

  Future<void> _askAi() async {
    setState(() => _aiBusy = true);
    try {
      final response = await widget.eventsRepository.apiClient.dio
          .post('/api/v1/events/${_currentEvent.id}/ai-review');
      _setAi(Map<String, dynamic>.from(response.data));
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.surface,
            content: Text(
              'The assistant could not review this incident. Check the server.',
              style: AppTypography.body,
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _aiBusy = false);
    }
  }

  Future<void> _handleDecision(HumanAction action) async {
    final isConfirm = action == HumanAction.CONFIRM;
    final confirmed = await showAppConfirmDialog(
      context,
      title: isConfirm ? 'Confirm threat?' : 'Mark false positive?',
      body: isConfirm
          ? 'This incident will be verified as an active security threat and logged in your on-premises audit trail.'
          : 'This incident will be marked as a false alarm and suppressed from critical alert notifications.',
      confirmLabel: isConfirm ? 'Confirm' : 'Mark false',
    );

    if (!confirmed || !mounted) return;

    setState(() => _isSubmitting = true);
    try {
      final updated = isConfirm
          ? await widget.eventsRepository.confirmEvent(_currentEvent.id)
          : await widget.eventsRepository.markFalsePositive(_currentEvent.id);

      setState(() {
        _currentEvent = updated;
        _isSubmitting = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.surface,
            content: Text(
              isConfirm ? 'Incident confirmed' : 'Marked as false positive',
              style: AppTypography.body,
            ),
          ),
        );
      }
    } catch (e) {
      setState(() => _isSubmitting = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.surface,
            content: Text('Action failed: $e', style: AppTypography.body),
          ),
        );
      }
    }
  }

  String _formatLabel(String raw) {
    final s = raw.replaceAll('_', ' ').toLowerCase();
    if (s.isEmpty) return s;
    return s[0].toUpperCase() + s.substring(1);
  }

  String _formatTime(String iso) {
    final dt = DateTime.tryParse(iso)?.toLocal();
    if (dt == null) return iso;
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '${dt.month}/${dt.day} · $h:$m';
  }

  Widget _buildMediaChipsRow(List<MediaItemOut> media) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          physics: const BouncingScrollPhysics(),
          child: ConstrainedBox(
            constraints: BoxConstraints(minWidth: constraints.maxWidth),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              mainAxisSize: MainAxisSize.min,
              children: [
                for (var i = 0; i < media.length; i++) ...[
                  AppChip(
                    label: media[i].kind == MediaKind.CLIP
                        ? '16:9 Clip ${i + 1}'
                        : '16:9 Frame ${i + 1}',
                    leadingSvg: media[i].kind == MediaKind.CLIP
                        ? 'play-03'
                        : 'camera-01',
                    selected: _selectedMediaIndex == i,
                    onTap: () => setState(() => _selectedMediaIndex = i),
                  ),
                  if (i < media.length - 1)
                    const SizedBox(width: AppSpacing.sm),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildBottomActionBar() {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.background,
        border: Border(
          top: BorderSide(color: AppColors.divider, width: 1.0),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.md,
        AppSpacing.lg,
        AppSpacing.md,
      ),
      child: SafeArea(
        top: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Row(
              children: [
                Expanded(
                  child: AppButton.secondary(
                    label: 'False positive',
                    svgAsset: 'x-01',
                    expand: true,
                    isLoading: _isSubmitting,
                    onPressed: _isSubmitting
                        ? null
                        : () => _handleDecision(HumanAction.MARK_FALSE_POSITIVE),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: AppButton(
                    label: 'Confirm threat',
                    svgAsset: 'check-01',
                    expand: true,
                    isLoading: _isSubmitting,
                    onPressed: _isSubmitting
                        ? null
                        : () => _handleDecision(HumanAction.CONFIRM),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final media = _currentEvent.media;
    final activeMedia = media.isNotEmpty
        ? media[_selectedMediaIndex.clamp(0, media.length - 1)]
        : null;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.lg,
                vertical: AppSpacing.sm,
              ),
              child: PageHeader(
                title: _currentEvent.category.label,
                trailing: AppCapsule(
                  label: _formatLabel(_currentEvent.status.name),
                  inverted: _currentEvent.status == EventStatus.CONFIRMED,
                ),
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.lg,
                  AppSpacing.sm,
                  AppSpacing.lg,
                  AppSpacing.xl,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Strict 16:9 Media Stage
                    if (activeMedia != null) ...[
                      AspectRatio(
                        aspectRatio: 16 / 9,
                        child: EvidenceMedia(
                          key: ValueKey(activeMedia.url),
                          url: activeMedia.url,
                          video: activeMedia.kind == MediaKind.CLIP,
                          offsetMs: activeMedia.offsetMs ?? 0,
                        ),
                      ),
                      if (media.length > 1) ...[
                        const SizedBox(height: AppSpacing.sm),
                        _buildMediaChipsRow(media),
                      ],
                    ] else ...[
                      AspectRatio(
                        aspectRatio: 16 / 9,
                        child: Container(
                          decoration: BoxDecoration(
                            color: AppColors.surface,
                            borderRadius: BorderRadius.circular(AppRadii.lg),
                            border: Border.all(
                              color: AppColors.divider,
                              width: 1.0,
                            ),
                          ),
                          child: Center(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const AppIcon(
                                  'video-off',
                                  size: 32,
                                  color: AppColors.foregroundSecondary,
                                ),
                                const SizedBox(height: AppSpacing.sm),
                                Text(
                                  'No recording attached to this incident.',
                                  style: AppTypography.support,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: AppSpacing.lg),

                    // Event Details Card
                    AppCard(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      child: Column(
                        children: [
                          _infoRow(
                            'Status',
                            _formatLabel(_currentEvent.status.name),
                          ),
                          const Divider(
                            color: AppColors.divider,
                            height: AppSpacing.lg,
                          ),
                          _infoRow(
                            'Severity',
                            _formatLabel(_currentEvent.severity.name),
                          ),
                          const Divider(
                            color: AppColors.divider,
                            height: AppSpacing.lg,
                          ),
                          _infoRow('Camera', _currentEvent.camera.name),
                          const Divider(
                            color: AppColors.divider,
                            height: AppSpacing.lg,
                          ),
                          _infoRow(
                            'Confidence',
                            '${(_currentEvent.peakConfidence * 100).toStringAsFixed(1)}%',
                          ),
                          const Divider(
                            color: AppColors.divider,
                            height: AppSpacing.lg,
                          ),
                          _infoRow(
                            'Detected at',
                            _formatTime(_currentEvent.firstSeenAt),
                          ),
                          if (_ruleId != null) ...[
                            const Divider(
                              color: AppColors.divider,
                              height: AppSpacing.lg,
                            ),
                            _infoRow(
                              'Rule',
                              '$_ruleId · v${_ruleVersion ?? '?'}',
                            ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    if (_currentEvent.summary != null) ...[
                      Text(
                        'Detection summary',
                        style: AppTypography.cardHeading,
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      AppCard(
                        padding: const EdgeInsets.all(AppSpacing.lg),
                        child: Text(
                          _currentEvent.summary!,
                          style: AppTypography.body.copyWith(
                            color: AppColors.foregroundSecondary,
                            height: 1.5,
                          ),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.lg),
                    ],

                    if (_ruleId != null && _uncertainty != null) ...[
                      Text(
                        'What remains uncertain',
                        style: AppTypography.cardHeading,
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      AppCard(
                        padding: const EdgeInsets.all(AppSpacing.lg),
                        child: Text(
                          _uncertainty!,
                          style: AppTypography.support,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.lg),
                    ],

                    Text(
                      'AI second opinion',
                      style: AppTypography.cardHeading,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    AppCard(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (_ai != null) ...[
                            Row(
                              children: [
                                AppCapsule(
                                  label: _ai!['disagrees'] == true
                                      ? 'Disagrees with detector'
                                      : (_ai!['reasoning']
                                                  ?['evidence_insufficient'] ==
                                              true
                                          ? 'Inconclusive'
                                          : 'Consistent with detector'),
                                  inverted: _ai!['disagrees'] != true,
                                ),
                              ],
                            ),
                            const SizedBox(height: AppSpacing.md),
                            if (_ai!['reasoning']?['uncertainty'] != null)
                              Text(
                                '${_ai!['reasoning']['uncertainty']}',
                                style: AppTypography.body,
                              ),
                            const SizedBox(height: AppSpacing.sm),
                            for (final fact in (_ai!['reasoning']
                                    ?['visible_facts'] as List? ??
                                const []))
                              Padding(
                                padding: const EdgeInsets.only(
                                  bottom: AppSpacing.xs,
                                ),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Padding(
                                      padding: EdgeInsets.only(top: 3),
                                      child: AppIcon(
                                        'check-01',
                                        size: 14,
                                        color: AppColors.foregroundSecondary,
                                      ),
                                    ),
                                    const SizedBox(width: AppSpacing.sm),
                                    Expanded(
                                      child: Text(
                                        '$fact',
                                        style: AppTypography.support,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              '${_ai!['model'] ?? 'Vision model'} · advisory only, you decide.',
                              style: AppTypography.caption,
                            ),
                          ] else
                            Text(
                              'An open-weights vision model can double-check the 16:9 evidence frames. It never confirms or dismisses an incident for you.',
                              style: AppTypography.support,
                            ),
                          const SizedBox(height: AppSpacing.md),
                          AppButton.secondary(
                            label: _ai == null
                                ? 'Ask AI to double-check'
                                : 'Re-run AI review',
                            svgAsset: 'shield-check',
                            expand: true,
                            isLoading: _aiBusy,
                            onPressed: _aiBusy ? null : _askAi,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            // Centered & Balanced Action Bar Pinned at Bottom
            _buildBottomActionBar(),
          ],
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: AppTypography.support),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Text(
            value,
            style: AppTypography.cardTitle.copyWith(
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
            textAlign: TextAlign.right,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}
