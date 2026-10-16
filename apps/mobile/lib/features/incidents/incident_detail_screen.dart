import 'package:flutter/material.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';

import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_dialog.dart';
import '../../core/widgets/page_header.dart';
import '../../core/widgets/evidence_media.dart';
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
  Map<String, dynamic>? _ai; // reasoning + disagreement flag from the server's AI second opinion
  String? _ruleId;
  int? _ruleVersion;
  String? _uncertainty;

  @override
  void initState() {
    super.initState();
    _currentEvent = widget.event;
    widget.eventsRepository.revision.addListener(_loadAi);
    _loadAi();
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
        _ai = raw['reasoning'] == null ? null : {'reasoning': raw['reasoning'], 'disagrees': raw['ai_disagrees'] == true, 'model': (raw['models']?['vlm']?['name'])};
      });
    }
  }

  Future<void> _loadAi() async {
    try {
      final response = await widget.eventsRepository.apiClient.dio.get('/api/v1/events/${widget.event.id}');
      _setAi(Map<String, dynamic>.from(response.data));
    } catch (_) {}
  }

  Future<void> _askAi() async {
    setState(() => _aiBusy = true);
    try {
      final response = await widget.eventsRepository.apiClient.dio.post('/api/v1/events/${_currentEvent.id}/ai-review');
      _setAi(Map<String, dynamic>.from(response.data));
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(backgroundColor: AppColors.surface, content: Text('The assistant could not review this incident. Check the server.', style: AppTypography.body)));
    } finally {
      if (mounted) setState(() => _aiBusy = false);
    }
  }

  Future<void> _handleDecision(HumanAction action) async {
    final isConfirm = action == HumanAction.CONFIRM;
    final confirmed = await showAppConfirmDialog(
      context,
      title: isConfirm ? 'Confirm Threat?' : 'Mark False Positive?',
      body: isConfirm
          ? 'This incident will be verified as an active security threat and escalated across the on-premises security log.'
          : 'This incident will be marked as a false alarm and suppressed from critical alert notifications.',
      confirmLabel: isConfirm ? 'Confirm' : 'Mark False',
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
              isConfirm ? 'Incident Confirmed' : 'Marked as False Positive',
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

  @override
  Widget build(BuildContext context) {
    final media = _currentEvent.media;


    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.lg,
                vertical: AppSpacing.sm,
              ),
              child: PageHeader(title: _currentEvent.category.label),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (media.isNotEmpty)
                      EvidenceMedia(
                        url: (media.where((m) => m.kind == MediaKind.CLIP).isNotEmpty ? media.firstWhere((m) => m.kind == MediaKind.CLIP) : media.first).url,
                        video: media.any((m) => m.kind == MediaKind.CLIP),
                        offsetMs: (media.where((m) => m.kind == MediaKind.CLIP).isNotEmpty ? media.firstWhere((m) => m.kind == MediaKind.CLIP) : media.first).offsetMs ?? 0,
                      )
                    else
                      Text('No evidence attached to this incident.', style: AppTypography.support),
                    const SizedBox(height: AppSpacing.lg),
                    // Event Details Card
                    AppCard(
                      child: Column(
                        children: [
                          _infoRow('Status', _currentEvent.status.name),
                          const Divider(color: AppColors.divider, height: AppSpacing.md),
                          _infoRow('Severity', _currentEvent.severity.name),
                          const Divider(color: AppColors.divider, height: AppSpacing.md),
                          _infoRow('Camera', _currentEvent.camera.name),
                          const Divider(color: AppColors.divider, height: AppSpacing.md),
                          _infoRow(
                            'Confidence',
                            '${(_currentEvent.peakConfidence * 100).toStringAsFixed(1)}%',
                          ),
                          const Divider(color: AppColors.divider, height: AppSpacing.md),
                          _infoRow('Detected At', _currentEvent.firstSeenAt),
                          if (_ruleId != null) ...[
                            const Divider(color: AppColors.divider, height: AppSpacing.md),
                            _infoRow('Rule', '$_ruleId · version ${_ruleVersion ?? '?'}'),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // VLM Reasoning Card
                    if (_currentEvent.summary != null) ...[
                      Text('Detection summary', style: AppTypography.cardHeading),
                      const SizedBox(height: AppSpacing.sm),
                      AppCard(
                        child: Text(
                          _currentEvent.summary!,
                          style: AppTypography.body.copyWith(
                            color: AppColors.foregroundSecondary,
                            height: 1.5,
                          ),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xl),
                    ],
                    if (_ruleId != null && _uncertainty != null) ...[
                      Text('What remains uncertain', style: AppTypography.cardHeading),
                      const SizedBox(height: AppSpacing.sm),
                      AppCard(child: Text(_uncertainty!, style: AppTypography.support)),
                      const SizedBox(height: AppSpacing.xl),
                    ],

                    Text('AI second opinion', style: AppTypography.cardHeading),
                    const SizedBox(height: AppSpacing.sm),
                    AppCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (_ai != null) ...[
                            Text(_ai!['disagrees'] == true ? 'Disagrees with the detector' : (_ai!['reasoning']['evidence_insufficient'] == true ? 'Inconclusive' : 'Consistent with the detector'), style: AppTypography.cardTitle),
                            const SizedBox(height: AppSpacing.sm),
                            Text('${_ai!['reasoning']['uncertainty']}', style: AppTypography.body),
                            for (final fact in (_ai!['reasoning']['visible_facts'] as List? ?? const [])) Text('•  $fact', style: AppTypography.support),
                            const SizedBox(height: AppSpacing.sm),
                            Text('${_ai!['model'] ?? 'Vision model'} · advisory only, you decide.', style: AppTypography.caption),
                          ] else
                            Text('An open-weights vision model can double-check the evidence frames. It never confirms or dismisses an incident for you.', style: AppTypography.support),
                          const SizedBox(height: AppSpacing.md),
                          AppButton.secondary(label: _ai == null ? 'Ask the AI to double-check' : 'Ask again', expand: true, isLoading: _aiBusy, onPressed: _aiBusy ? null : _askAi),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xl),

                    // Action Buttons Row
                    Row(
                      children: [
                        Expanded(
                          child: AppButton.secondary(
                            label: 'False Positive',
                            expand: true,
                            isLoading: _isSubmitting,
                            onPressed: () => _handleDecision(HumanAction.MARK_FALSE_POSITIVE),
                          ),
                        ),
                        const SizedBox(width: AppSpacing.md),
                        Expanded(
                          child: AppButton(
                            label: 'Confirm Threat',
                            expand: true,
                            isLoading: _isSubmitting,
                            onPressed: () => _handleDecision(HumanAction.CONFIRM),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xl),
                  ],
                ),
              ),
            ),
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
        Expanded(child: Text(value, style: AppTypography.cardTitle, textAlign: TextAlign.right)),
      ],
    );
  }
}

