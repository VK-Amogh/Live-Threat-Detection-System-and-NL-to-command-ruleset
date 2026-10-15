import 'package:flutter/material.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_dialog.dart';
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

  @override
  void initState() {
    super.initState();
    _currentEvent = widget.event;
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
    final isCritical = _currentEvent.severity == Severity.CRITICAL;

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
                    // Keyframe Media Container
                    Container(
                      height: 240,
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: BorderRadius.circular(AppRadii.card),
                        border: Border.all(color: AppColors.divider, width: 1.0),
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(AppRadii.card),
                        child: Stack(
                          fit: StackFit.expand,
                          children: [
                            if (media.isNotEmpty)
                              Image.network(
                                media.first.url,
                                fit: BoxFit.cover,
                                errorBuilder: (ctx, err, stack) => _placeholderKeyframe(),
                              )
                            else
                              _placeholderKeyframe(),
                            Positioned(
                              top: AppSpacing.md,
                              left: AppSpacing.md,
                              child: isCritical
                                  ? const AppCapsule(
                                      label: 'CRITICAL THREAT',
                                      icon: Icons.warning_amber_rounded,
                                      inverted: true,
                                    )
                                  : AppCapsule(label: _currentEvent.severity.name),
                            ),
                            Positioned(
                              bottom: AppSpacing.md,
                              left: AppSpacing.md,
                              child: AppCapsule(
                                label: _currentEvent.camera.name,
                                icon: Icons.videocam_outlined,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
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
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // VLM Reasoning Card
                    if (_currentEvent.summary != null) ...[
                      Text('VLM Intelligence Analysis', style: AppTypography.cardHeading),
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

  Widget _placeholderKeyframe() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.camera_alt_outlined,
            size: 40,
            color: AppColors.foregroundSecondary,
          ),
          const SizedBox(height: AppSpacing.sm),
          Text('Keyframe Processing', style: AppTypography.caption),
        ],
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: AppTypography.support),
        Text(value, style: AppTypography.cardTitle),
      ],
    );
  }
}
