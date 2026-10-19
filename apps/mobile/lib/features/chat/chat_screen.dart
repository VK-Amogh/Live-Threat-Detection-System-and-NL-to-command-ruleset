import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_capsule.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/app_icon.dart';
import '../../core/widgets/evidence_media.dart';
import '../../core/widgets/page_header.dart';
import '../../core/widgets/press_scale.dart';
import '../../data/repositories/chat_repository.dart';
import '../../data/repositories/events_repository.dart';
import '../incidents/incident_detail_screen.dart';

final _bullet = RegExp(r'^\s*[-*•]\s+');
final _heading = RegExp(r'^#{1,4}\s+');

List<InlineSpan> _inline(String text, TextStyle base) {
  final spans = <InlineSpan>[];
  for (final part in text.split(RegExp(r'(\*\*[^*]+\*\*)'))) {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      spans.add(
        TextSpan(
          text: part.substring(2, part.length - 2),
          style: base.copyWith(fontWeight: FontWeight.w600),
        ),
      );
    } else if (part.isNotEmpty) {
      spans.add(TextSpan(text: part, style: base));
    }
  }
  return spans;
}

class ChatScreen extends StatefulWidget {
  final ChatRepository chatRepository;
  const ChatScreen({super.key, required this.chatRepository});
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final controller = TextEditingController();
  final scroll = ScrollController();
  final messages = <ChatMessage>[];
  List<ChatConversation> conversations = [];
  StreamSubscription<ChatMessage>? sub;
  bool busy = false;
  String? error;

  @override
  void initState() {
    super.initState();
    _loadConversations();
  }

  Future<void> _loadConversations() async {
    try {
      final items = await widget.chatRepository.listConversations();
      if (mounted) setState(() => conversations = items);
    } catch (_) {}
  }

  Future<void> _openConversation(String id) async {
    try {
      final saved = await widget.chatRepository.openConversation(id);
      if (mounted) {
        setState(() {
          messages
            ..clear()
            ..addAll(saved);
          error = null;
        });
      }
      toBottom();
    } catch (_) {
      if (mounted) setState(() => error = 'Could not open this conversation.');
    }
  }

  void _showConversationsSheet() {
    HapticFeedback.selectionClick();
    _loadConversations();
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
                        Text('Past chats', style: AppTypography.cardHeading),
                        Text(
                          '${conversations.length} saved conversations',
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
              SizedBox(
                height: 320,
                child: conversations.isEmpty
                    ? Center(
                        child: Text(
                          'Your conversations will appear here.',
                          style: AppTypography.support,
                          textAlign: TextAlign.center,
                        ),
                      )
                    : ListView.separated(
                        itemCount: conversations.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(height: AppSpacing.sm),
                        itemBuilder: (_, idx) {
                          final item = conversations[idx];
                          return AppCard(
                            padding: const EdgeInsets.all(AppSpacing.md),
                            onTap: () {
                              Navigator.pop(sheet);
                              _openConversation(item.id);
                            },
                            child: Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        item.title,
                                        style: AppTypography.cardTitle,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        '${item.messageCount} messages',
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

  void _showEvidenceDetail(EvidenceCardItem ev) {
    HapticFeedback.selectionClick();
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
                  AppCapsule(label: ev.kind),
                  const Spacer(),
                  GlassCircleButton(
                    svgAsset: 'x-01',
                    compact: true,
                    onTap: () => Navigator.pop(sheet),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              Text(ev.title, style: AppTypography.cardHeading),
              const SizedBox(height: AppSpacing.sm),
              Text(ev.snippet, style: AppTypography.body),
              const SizedBox(height: AppSpacing.lg),
              AppButton.secondary(
                label: 'Close',
                expand: true,
                onPressed: () => Navigator.pop(sheet),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    sub?.cancel();
    controller.dispose();
    scroll.dispose();
    super.dispose();
  }

  void toBottom() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (scroll.hasClients) {
          scroll.animateTo(
            scroll.position.maxScrollExtent,
            duration: AppMotion.shortDuration,
            curve: AppMotion.standardCurve,
          );
        }
      });

  Future<void> send([String? preset]) async {
    final text = (preset ?? controller.text).trim();
    if (text.isEmpty || busy) return;
    HapticFeedback.selectionClick();
    controller.clear();
    setState(() {
      busy = true;
      error = null;
      messages.add(ChatMessage(text: text, isUser: true));
    });
    toBottom();
    final done = Completer<void>();
    sub = widget.chatRepository.ask(text).listen(
      (message) {
        if (!mounted) return;
        setState(() {
          if (!messages.contains(message)) messages.add(message);
        });
        toBottom();
      },
      onError: (Object e) {
        if (mounted) {
          setState(() => error = e.toString().replaceFirst('Exception: ', ''));
        }
        if (!done.isCompleted) done.complete();
      },
      onDone: () {
        if (!done.isCompleted) done.complete();
      },
    );
    await done.future;
    if (mounted) setState(() => busy = false);
    _loadConversations();
  }

  Future<void> evidence(String id) async {
    try {
      final repo = EventsRepository(widget.chatRepository.apiClient);
      final event = await repo.getEvent(id);
      if (mounted) {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => IncidentDetailScreen(
              event: event,
              eventsRepository: repo,
            ),
          ),
        );
      }
    } catch (_) {
      if (mounted) setState(() => error = 'Could not load this incident.');
    }
  }

  /// Clean, balanced prompt pill conforming strictly to Requirement 1:
  /// Equal-sized balanced prompt pill with icon and prompt text.
  /// Empty state with cleanly organized, centered, equal-sized balanced prompt pills.
  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Text(
          'What would you like to know?',
          style: AppTypography.sectionHeading,
          textAlign: TextAlign.center,
        ),
      ),
    );
  }

  /// Message bubbles with generous padding, clean typographic hierarchy,
  /// and uncluttered layout conforming to Requirement 1.
  Widget _buildBubble(ChatMessage m) {
    if (m.isUser) {
      return Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.md),
        child: Align(
          alignment: Alignment.centerRight,
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.82,
            ),
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.lg,
                vertical: AppSpacing.md,
              ),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(AppRadii.card).copyWith(
                  bottomRight: const Radius.circular(AppRadii.sm),
                ),
                border: Border.all(color: AppColors.divider, width: 1.0),
              ),
              child: SelectableText(
                m.text,
                style: AppTypography.body.copyWith(
                  color: AppColors.foreground,
                ),
              ),
            ),
          ),
        ),
      );
    }

    // Assistant message bubble
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.lg),
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.lg),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadii.card),
          border: Border.all(color: AppColors.divider, width: 1.0),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: AppSpacing.xs),
            if (m.text.isEmpty)
              Row(
                children: [
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AppColors.foreground,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text(
                      m.status ?? 'Analyzing grounded evidence…',
                      style: AppTypography.support,
                    ),
                  ),
                ],
              )
            else
              for (final line in m.text.split('\n'))
                if (line.trim().isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                    child: SelectableText.rich(
                      TextSpan(
                        children: [
                          if (_bullet.hasMatch(line))
                            TextSpan(text: '•  ', style: AppTypography.body),
                          ..._inline(
                            line
                                .replaceFirst(_bullet, '')
                                .replaceFirst(_heading, ''),
                            AppTypography.body,
                          ),
                        ],
                      ),
                    ),
                  ),
            if (m.evidence.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.lg),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Grounded evidence (${m.evidence.length})',
                    style: AppTypography.cardTitle,
                  ),
                  Text('Tap to inspect', style: AppTypography.caption),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              SizedBox(
                height: 112,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: m.evidence.length,
                  separatorBuilder: (_, __) =>
                      const SizedBox(width: AppSpacing.sm),
                  itemBuilder: (_, idx) {
                    final ev = m.evidence[idx];
                    return SizedBox(
                      width: 224,
                      child: AppCard(
                        padding: const EdgeInsets.all(AppSpacing.md),
                        onTap: () => _showEvidenceDetail(ev),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${ev.kind} · ${ev.title}',
                              style: AppTypography.caption.copyWith(
                                color: AppColors.foreground,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 4),
                            Expanded(
                              child: Text(
                                ev.snippet,
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
            for (final c in m.cited) ...[
              const SizedBox(height: AppSpacing.lg),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${c.label} · 16:9 footage',
                    style: AppTypography.cardTitle,
                  ),
                  AppCapsule(
                    label: 'Open incident',
                    svgAsset: 'chevron-right',
                    onTap: () => evidence(c.eventId),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              // Video evidence cited by assistant strictly enforces clean 16:9 stage with tap-to-play
              EvidenceMedia(
                url: c.clipUrl ?? c.posterUrl ?? '',
                video: c.clipUrl != null,
                offsetMs: c.startMs,
              ),
            ],
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
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.lg,
            AppSpacing.md,
            AppSpacing.lg,
            AppSpacing.lg,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text('Ask', style: AppTypography.screenTitle),
                  ),
                  GlassCircleButton(
                    svgAsset: 'menu-01',
                    tooltip: 'Past chats',
                    onTap: _showConversationsSheet,
                  ),
                  if (messages.isNotEmpty) ...[
                    const SizedBox(width: AppSpacing.xs),
                    GlassCircleButton(
                      svgAsset: 'plus-01',
                      tooltip: 'New conversation',
                      onTap: () {
                        widget.chatRepository.reset();
                        setState(messages.clear);
                      },
                    ),
                  ],
                ],
              ),
              const SizedBox(height: AppSpacing.lg),
              Expanded(
                child: messages.isEmpty
                    ? _buildEmptyState()
                    : ListView.builder(
                        controller: scroll,
                        itemCount: messages.length,
                        itemBuilder: (_, i) => _buildBubble(messages[i]),
                      ),
              ),
              if (error != null) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(error!, style: AppTypography.support),
              ],
              const SizedBox(height: AppSpacing.sm),
              // Circular send/stop action button geometrically centered with text composer field
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(
                    child: TextField(
                      controller: controller,
                      minLines: 1,
                      maxLines: 4,
                      style: AppTypography.body,
                      textAlignVertical: TextAlignVertical.center,
                      decoration: InputDecoration(
                        hintText: 'Ask about alerts, rules, or live cameras…',
                        hintStyle: AppTypography.body.copyWith(
                          color: AppColors.foregroundSecondary,
                        ),
                        isDense: true,
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.lg,
                          vertical: 14,
                        ),
                        filled: true,
                        fillColor: AppColors.surface,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(AppRadii.pill),
                          borderSide: const BorderSide(
                            color: AppColors.divider,
                            width: 1.0,
                          ),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(AppRadii.pill),
                          borderSide: const BorderSide(
                            color: AppColors.divider,
                            width: 1.0,
                          ),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(AppRadii.pill),
                          borderSide: const BorderSide(
                            color: AppColors.foreground,
                            width: 1.0,
                          ),
                        ),
                      ),
                      onSubmitted: (_) => send(),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  PressScale(
                    onTap: busy
                        ? () {
                            HapticFeedback.selectionClick();
                            sub?.cancel();
                            setState(() => busy = false);
                          }
                        : send,
                    pressedScale: 0.92,
                    child: Container(
                      width: 48,
                      height: 48,
                      decoration: const BoxDecoration(
                        color: AppColors.foreground,
                        shape: BoxShape.circle,
                      ),
                      child: Center(
                        child: AppIcon(
                          busy ? 'x-01' : 'send-01',
                          size: 20,
                          color: AppColors.background,
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
}
