import 'package:flutter/material.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_icon.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/evidence_media.dart';
import '../../core/widgets/page_header.dart';
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
  String _selectedStatus = 'ALL';
  bool _criticalOnly = false;
  bool _showSearch = false;
  final TextEditingController _searchCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    widget.eventsRepository.revision.addListener(_loadEvents);
    _loadEvents();
  }

  @override
  void dispose() {
    widget.eventsRepository.revision.removeListener(_loadEvents);
    _searchCtrl.dispose();
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
    final query = _searchCtrl.text.trim().toLowerCase();
    return _events.where((e) {
      if (_criticalOnly && e.severity != Severity.CRITICAL) {
        return false;
      }
      if (_selectedFilter != 'ALL') {
        if (_selectedFilter == 'RULE') {
          if (e.category.key != 'RULE_ALERT') return false;
        } else {
          final cat = e.category.label.toUpperCase();
          if (!cat.contains(_selectedFilter)) return false;
        }
      }
      if (_selectedStatus != 'ALL') {
        if (_selectedStatus == 'UNREVIEWED') {
          if (e.status != EventStatus.NEEDS_REVIEW &&
              e.status != EventStatus.DETECTED &&
              e.status != EventStatus.VERIFYING) {
            return false;
          }
        } else if (e.status.name != _selectedStatus) {
          return false;
        }
      }
      if (query.isNotEmpty) {
        final hay =
            '${e.category.label} ${e.camera.name} ${e.summary ?? ''} ${e.severity.name}'
                .toLowerCase();
        if (!hay.contains(query)) return false;
      }
      return true;
    }).toList();
  }

  EventOut? get _recentVideo {
    for (final event in _filteredEvents) {
      if (event.media.any((item) => item.kind == MediaKind.CLIP)) return event;
    }
    return null;
  }

  String _formatStatus(String raw) {
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

  Widget _buildFilterRow(List<Widget> chips) {
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
                for (int i = 0; i < chips.length; i++) ...[
                  chips[i],
                  if (i < chips.length - 1)
                    const SizedBox(width: AppSpacing.sm),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final awaitingCount = _events
        .where((e) =>
            e.status == EventStatus.NEEDS_REVIEW ||
            e.status == EventStatus.DETECTED ||
            e.status == EventStatus.VERIFYING)
        .length;
    final recent = _recentVideo;
    final recentClip =
        recent?.media.where((item) => item.kind == MediaKind.CLIP).firstOrNull;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: RefreshIndicator(
        color: AppColors.foreground,
        backgroundColor: AppColors.surface,
        onRefresh: _loadEvents,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.xl),
          children: [
            Row(
              children: [
                Expanded(
                    child: Text('History', style: AppTypography.screenTitle)),
                GlassCircleButton(
                  svgAsset: 'search-01',
                  active: _showSearch,
                  tooltip: 'Search history',
                  onTap: () => setState(() {
                    _showSearch = !_showSearch;
                    if (!_showSearch) _searchCtrl.clear();
                  }),
                ),
              ],
            ),
            if (_showSearch) ...[
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _searchCtrl,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(hintText: 'Search history'),
              ),
            ],
            const SizedBox(height: AppSpacing.lg),
            Row(
              children: [
                Expanded(
                  child: _statBox('Events', _events.length.toString(),
                      selected: _selectedStatus == 'ALL',
                      onTap: () => setState(() {
                            _selectedStatus = 'ALL';
                            _criticalOnly = false;
                          })),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: _statBox('Needs review', awaitingCount.toString(),
                      selected: _selectedStatus == 'UNREVIEWED',
                      onTap: () => setState(() {
                            _selectedStatus = _selectedStatus == 'UNREVIEWED'
                                ? 'ALL'
                                : 'UNREVIEWED';
                            _criticalOnly = false;
                          })),
                ),
              ],
            ),
            if (recent != null && recentClip != null) ...[
              const SizedBox(height: AppSpacing.xl),
              Text('Latest video', style: AppTypography.sectionHeading),
              const SizedBox(height: AppSpacing.md),
              AppCard(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    EvidenceMedia(
                      url: recentClip.url,
                      video: true,
                      offsetMs: recentClip.offsetMs ?? 0,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text(recent.category.label,
                        style: AppTypography.cardHeading),
                    const SizedBox(height: AppSpacing.xs),
                    Text(recent.camera.name, style: AppTypography.support),
                    const SizedBox(height: AppSpacing.md),
                    AppButton.secondary(
                      label: 'View event',
                      expand: true,
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => IncidentDetailScreen(
                            event: recent,
                            eventsRepository: widget.eventsRepository,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.xl),
            Text('Events', style: AppTypography.sectionHeading),
            const SizedBox(height: AppSpacing.md),
            _buildFilterRow([
              AppChip(
                label: 'All',
                selected: _selectedFilter == 'ALL',
                onTap: () => setState(() => _selectedFilter = 'ALL'),
              ),
              AppChip(
                label: 'Weapons',
                selected: _selectedFilter == 'WEAPON',
                onTap: () => setState(() => _selectedFilter = 'WEAPON'),
              ),
              AppChip(
                label: 'Violence',
                selected: _selectedFilter == 'VIOLENCE',
                onTap: () => setState(() => _selectedFilter = 'VIOLENCE'),
              ),
              AppChip(
                label: 'Intrusion',
                selected: _selectedFilter == 'INTRUSION',
                onTap: () => setState(() => _selectedFilter = 'INTRUSION'),
              ),
              AppChip(
                label: 'Rules',
                selected: _selectedFilter == 'RULE',
                onTap: () => setState(() => _selectedFilter = 'RULE'),
              ),
            ]),
            const SizedBox(height: AppSpacing.md),
            if (_isLoading)
              const Center(
                  child: Padding(
                padding: EdgeInsets.all(AppSpacing.xl),
                child: CircularProgressIndicator(color: AppColors.foreground),
              ))
            else if (_error != null)
              EmptyState(
                svgAsset: 'alert-circle',
                title: 'Could not load history',
                subtitle: _error!,
                action: AppButton.secondary(
                  label: 'Retry',
                  onPressed: _loadEvents,
                ),
              )
            else if (_filteredEvents.isEmpty)
              const EmptyState(
                svgAsset: 'shield-check',
                title: 'No events',
                subtitle: 'New events will appear here.',
              )
            else
              for (final event in _filteredEvents)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.md),
                  child: _buildEventCard(event),
                ),
          ],
        ),
      ),
    );
  }

  Widget _statBox(
    String label,
    String value, {
    required bool selected,
    required VoidCallback onTap,
  }) {
    return AppCard(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.md,
      ),
      border: Border.all(
        color: selected ? AppColors.foreground : AppColors.divider,
        width: selected ? 1.5 : 1.0,
      ),
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            value,
            style: AppTypography.sectionHeading.copyWith(
              fontFeatures: const [FontFeature.tabularFigures()],
              height: 1.1,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            label,
            style: AppTypography.caption.copyWith(
              color: selected
                  ? AppColors.foreground
                  : AppColors.foregroundSecondary,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildEventCard(EventOut event) {
    final frame = event.media
        .where((item) => item.kind == MediaKind.KEYFRAME)
        .firstOrNull;
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => IncidentDetailScreen(
            event: event,
            eventsRepository: widget.eventsRepository,
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (frame != null) ...[
            EvidenceMedia(url: frame.url),
            const SizedBox(height: AppSpacing.md),
          ],
          Text(event.category.label, style: AppTypography.cardHeading),
          const SizedBox(height: AppSpacing.xs),
          Text(
            event.summary ?? event.camera.name,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: AppTypography.body,
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: Text(
                  '${event.camera.name} · ${_formatTime(event.firstSeenAt)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.support,
                ),
              ),
              Text(_formatStatus(event.status.name),
                  style: AppTypography.caption),
              const SizedBox(width: AppSpacing.xs),
              const AppIcon('chevron-right', size: 16),
            ],
          ),
        ],
      ),
    );
  }
}
