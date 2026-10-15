import 'package:flutter/material.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/press_scale.dart';
import '../../data/generated/models.dart';
import '../../data/repositories/events_repository.dart';
import 'incident_detail_screen.dart';

class IncidentsScreen extends StatefulWidget {
  final EventsRepository eventsRepository;

  const IncidentsScreen({super.key, required this.eventsRepository});

  @override
  State<IncidentsScreen> createState() => _IncidentsScreenState();
}

class _IncidentsScreenState extends State<IncidentsScreen> {
  List<EventOut> _events = [];
  bool _isLoading = true;
  String? _error;
  String _selectedFilter = 'ALL';

  @override
  void initState() {
    super.initState();
    widget.eventsRepository.revision.addListener(_loadEvents);
    _loadEvents();
  }

  @override
  void dispose() {
    widget.eventsRepository.revision.removeListener(_loadEvents);
    super.dispose();
  }

  Future<void> _loadEvents() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final events = await widget.eventsRepository.getEvents();
      if (!mounted) return;
      setState(() {
        _events = events;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  List<EventOut> get _filteredEvents {
    if (_selectedFilter == 'ALL') return _events;
    return _events.where((e) {
      final cat = e.category.label.toUpperCase();
      return cat.contains(_selectedFilter);
    }).toList();
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
          onRefresh: _loadEvents,
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // Editorial Section Header
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.lg,
                    AppSpacing.md,
                    AppSpacing.lg,
                    AppSpacing.sm,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('Threat Alerts', style: AppTypography.screenTitle),
                          PressScale(
                            onTap: _loadEvents,
                            pressedScale: 0.94,
                            child: Container(
                              width: AppSpacing.smallCircle,
                              height: AppSpacing.smallCircle,
                              decoration: BoxDecoration(
                                color: AppColors.surface,
                                shape: BoxShape.circle,
                                border: Border.all(color: AppColors.divider, width: 1.0),
                              ),
                              child: const Icon(
                                Icons.refresh_rounded,
                                size: 20,
                                color: AppColors.foreground,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'On-premises CCTV Threat Intelligence & Verification',
                        style: AppTypography.support,
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      // Filter Chips Row
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            _filterChip('ALL', 'All Threats'),
                            const SizedBox(width: AppSpacing.sm),
                            _filterChip('WEAPON', 'Weapons'),
                            const SizedBox(width: AppSpacing.sm),
                            _filterChip('VIOLENCE', 'Violence'),
                            const SizedBox(width: AppSpacing.sm),
                            _filterChip('INTRUSION', 'Intrusion'),
                          ],
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                    ],
                  ),
                ),
              ),

              // Content Body
              if (_isLoading)
                const SliverFillRemaining(
                  child: Center(
                    child: CircularProgressIndicator(
                      color: AppColors.foreground,
                      strokeWidth: 2,
                    ),
                  ),
                )
              else if (_error != null)
                SliverFillRemaining(
                  child: EmptyState(
                    icon: Icons.error_outline_rounded,
                    title: 'Sync Error',
                    message: _error!,
                    action: PressScale(
                      onTap: _loadEvents,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.xl,
                          vertical: AppSpacing.md,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.surface,
                          borderRadius: BorderRadius.circular(AppRadii.pill),
                          border: Border.all(color: AppColors.divider, width: 1.0),
                        ),
                        child: Text('Retry Connection', style: AppTypography.button),
                      ),
                    ),
                  ),
                )
              else if (_filteredEvents.isEmpty)
                const SliverFillRemaining(
                  child: EmptyState(
                    icon: Icons.shield_outlined,
                    title: 'No Threat Incidents',
                    message: 'Active camera feeds are normal and undisturbed.',
                  ),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.lg,
                    0,
                    AppSpacing.lg,
                    96, // Bottom padding to clear floating nav bar
                  ),
                  sliver: SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, index) {
                        final event = _filteredEvents[index];
                        return Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.md),
                          child: _buildEventCard(event),
                        );
                      },
                      childCount: _filteredEvents.length,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _filterChip(String key, String label) {
    final isSelected = _selectedFilter == key;

    return PressScale(
      onTap: () => setState(() => _selectedFilter = key),
      pressedScale: 0.96,
      child: AnimatedContainer(
        duration: AppMotion.shortDuration,
        height: 36,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.selectedChip : AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadii.pill),
          border: Border.all(
            color: isSelected ? AppColors.foreground : AppColors.divider,
            width: 1.0,
          ),
        ),
        child: Center(
          child: Text(
            label,
            style: AppTypography.tabLabel.copyWith(
              color: isSelected ? AppColors.foreground : AppColors.foregroundSecondary,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildEventCard(EventOut event) {
    final isCritical = event.severity == Severity.CRITICAL;

    return AppCard(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (ctx) => IncidentDetailScreen(
              event: event,
              eventsRepository: widget.eventsRepository,
            ),
          ),
        );
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (isCritical)
                const AppCapsule(
                  label: 'CRITICAL',
                  icon: Icons.warning_amber_rounded,
                  inverted: true,
                )
              else
                AppCapsule(label: event.severity.name),
              const Spacer(),
              Text(
                '${(event.peakConfidence * 100).toStringAsFixed(0)}% Conf',
                style: AppTypography.support.copyWith(
                  fontFeatures: const [FontFeature.tabularFigures()],
                  color: AppColors.foreground,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            event.category.label,
            style: AppTypography.cardHeading,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            event.summary ?? 'Detection on ${event.camera.name}',
            style: AppTypography.body.copyWith(
              color: AppColors.foregroundSecondary,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              const Icon(
                Icons.videocam_outlined,
                size: 16,
                color: AppColors.foregroundSecondary,
              ),
              const SizedBox(width: AppSpacing.xs),
              Text(event.camera.name, style: AppTypography.caption),
              const Spacer(),
              Text(
                event.status.name,
                style: AppTypography.caption.copyWith(
                  color: AppColors.foreground,
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              const Icon(
                Icons.chevron_right_rounded,
                size: 18,
                color: AppColors.foregroundSecondary,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
