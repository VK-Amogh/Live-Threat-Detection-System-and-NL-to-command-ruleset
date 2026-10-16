import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/evidence_media.dart';
import '../../data/repositories/chat_repository.dart';
import '../../data/repositories/events_repository.dart';
import '../incidents/incident_detail_screen.dart';

const _prompts = [
  'Summarize the most recent incident and what the footage shows.',
  'Which incidents still need review?',
  'Show me the footage of the highest-severity incident.',
];

final _bullet = RegExp(r'^\s*[-*•]\s+');
final _heading = RegExp(r'^#{1,4}\s+');

/// Renders **bold** without injecting any markup.
List<InlineSpan> _inline(String text, TextStyle base) {
  final spans = <InlineSpan>[];
  for (final part in text.split(RegExp(r'(\*\*[^*]+\*\*)'))) {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      spans.add(TextSpan(text: part.substring(2, part.length - 2), style: base.copyWith(fontWeight: FontWeight.w600)));
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
  StreamSubscription<ChatMessage>? sub;
  bool busy = false;
  String? error;

  @override
  void dispose() {
    sub?.cancel();
    controller.dispose();
    scroll.dispose();
    super.dispose();
  }

  void toBottom() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (scroll.hasClients) scroll.jumpTo(scroll.position.maxScrollExtent);
      });

  Future<void> send([String? preset]) async {
    final text = (preset ?? controller.text).trim();
    if (text.isEmpty || busy) return;
    controller.clear();
    setState(() {
      busy = true;
      error = null;
      messages.add(ChatMessage(text: text, isUser: true));
    });
    final done = Completer<void>();
    sub = widget.chatRepository.ask(text).listen((message) {
      if (!mounted) return;
      setState(() {
        if (!messages.contains(message)) messages.add(message);
      });
      toBottom();
    }, onError: (Object e) {
      if (mounted) setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      if (!done.isCompleted) done.complete();
    }, onDone: () {
      if (!done.isCompleted) done.complete();
    });
    await done.future;
    if (mounted) setState(() => busy = false);
  }

  Future<void> evidence(String id) async {
    try {
      final repo = EventsRepository(widget.chatRepository.apiClient);
      final event = await repo.getEvent(id);
      if (mounted) Navigator.push(context, MaterialPageRoute(builder: (_) => IncidentDetailScreen(event: event, eventsRepository: repo)));
    } catch (_) {
      if (mounted) setState(() => error = 'Could not load this incident.');
    }
  }

  Widget bubble(ChatMessage m) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(m.isUser ? 'YOU' : 'SAFESPACE${m.model == null ? '' : ' · ${m.model}'}', style: AppTypography.caption),
          const SizedBox(height: AppSpacing.sm),
          if (m.isUser)
            SelectableText(m.text, style: AppTypography.body)
          else ...[
            if (m.text.isEmpty) Text(m.status ?? 'Waiting for the model…', style: AppTypography.support),
            for (final line in m.text.split('\n'))
              if (line.trim().isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                  child: SelectableText.rich(TextSpan(children: [
                    if (_bullet.hasMatch(line)) TextSpan(text: '•  ', style: AppTypography.body),
                    ..._inline(line.replaceFirst(_bullet, '').replaceFirst(_heading, ''), AppTypography.body),
                  ])),
                ),
            for (final c in m.cited) ...[
              const SizedBox(height: AppSpacing.md),
              Text('${c.label} · footage', style: AppTypography.support),
              const SizedBox(height: AppSpacing.sm),
              ClipRRect(
                borderRadius: BorderRadius.circular(AppRadii.card),
                child: EvidenceMedia(url: c.clipUrl ?? c.posterUrl ?? '', video: c.clipUrl != null, offsetMs: c.startMs),
              ),
              TextButton(onPressed: () => evidence(c.eventId), child: Text('Open incident', style: AppTypography.caption)),
            ],
          ],
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, 88),
          child: Column(children: [
            Align(alignment: Alignment.centerLeft, child: Text('Ask the evidence.', style: AppTypography.screenTitle)),
            const SizedBox(height: AppSpacing.md),
            DropdownButtonFormField<String>(
              initialValue: widget.chatRepository.provider,
              decoration: const InputDecoration(labelText: 'Assistant provider'),
              items: const [DropdownMenuItem(value: 'ollama', child: Text('Local Gemma')), DropdownMenuItem(value: 'groq', child: Text('Groq · Qwen'))],
              onChanged: busy
                  ? null
                  : (value) => setState(() {
                        widget.chatRepository.provider = value!;
                        widget.chatRepository.reset();
                        messages.clear();
                      }),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
                widget.chatRepository.provider == 'groq'
                    ? 'Your question, incident metadata and selected evidence frames are sent to Groq. Full recordings stay on your PC.'
                    : 'Questions and incident evidence stay on your PC.',
                style: AppTypography.caption),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: widget.chatRepository.includeImages,
              onChanged: (value) => setState(() => widget.chatRepository.includeImages = value!),
              title: Text('Let the assistant look at footage frames', style: AppTypography.support),
              activeColor: AppColors.foreground,
              checkColor: AppColors.background,
            ),
            Expanded(
              child: messages.isEmpty
                  ? ListView(children: [
                      Padding(
                          padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg),
                          child: Text('Ask what happened, which incidents need review, or to see the recording of an incident.', textAlign: TextAlign.center, style: AppTypography.support)),
                      for (final p in _prompts)
                        Padding(padding: const EdgeInsets.only(bottom: AppSpacing.sm), child: OutlinedButton(onPressed: busy ? null : () => send(p), child: Text(p, style: AppTypography.caption))),
                    ])
                  : ListView.builder(controller: scroll, itemCount: messages.length, itemBuilder: (_, i) => bubble(messages[i])),
            ),
            if (error != null) Text(error!, style: AppTypography.body),
            const SizedBox(height: AppSpacing.sm),
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Expanded(child: TextField(controller: controller, minLines: 1, maxLines: 4, decoration: const InputDecoration(hintText: 'What happened?', border: OutlineInputBorder()), onSubmitted: (_) => send())),
              const SizedBox(width: AppSpacing.sm),
              TextButton(
                onPressed: busy
                    ? () {
                        sub?.cancel();
                        setState(() => busy = false);
                      }
                    : send,
                child: Text(busy ? 'Stop' : 'Ask', style: AppTypography.button),
              ),
            ]),
          ]),
        ),
      );
}
