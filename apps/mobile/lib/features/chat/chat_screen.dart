import 'package:flutter/material.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_card.dart';
import '../../data/repositories/chat_repository.dart';
import '../../data/repositories/events_repository.dart';
import '../incidents/incident_detail_screen.dart';

class ChatScreen extends StatefulWidget {
  final ChatRepository chatRepository;
  const ChatScreen({super.key, required this.chatRepository});
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}
class _ChatScreenState extends State<ChatScreen> {
  final controller = TextEditingController();
  final messages = <ChatMessage>[];
  bool busy = false;
  String? error;
  @override
  void dispose() { controller.dispose(); super.dispose(); }
  Future<void> send() async {
    final text = controller.text.trim(); if (text.isEmpty || busy) return;
    controller.clear(); setState(() { busy = true; error = null; messages.add(ChatMessage(text: text, isUser: true)); });
    try { final answer = await widget.chatRepository.sendMessage(text); if (mounted) setState(() => messages.add(answer)); }
    catch (_) { if (mounted) setState(() => error = 'The model is unavailable. Check System or choose another provider.'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> evidence(String id) async {
    try {
      final repo = EventsRepository(widget.chatRepository.apiClient);
      final event = await repo.getEvent(id);
      if (mounted) Navigator.push(context, MaterialPageRoute(builder: (_) => IncidentDetailScreen(event: event, eventsRepository: repo)));
    } catch (_) { if (mounted) setState(() => error = 'Could not load this incident.'); }
  }
  @override
  Widget build(BuildContext context) => SafeArea(child: Padding(padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, 88), child: Column(children: [
    Align(alignment: Alignment.centerLeft, child: Text('Ask the evidence.', style: AppTypography.screenTitle)), const SizedBox(height: AppSpacing.md),
    DropdownButtonFormField<String>(initialValue: widget.chatRepository.provider, decoration: const InputDecoration(labelText: 'Assistant provider'), items: const [DropdownMenuItem(value: 'ollama', child: Text('Local Gemma')), DropdownMenuItem(value: 'groq', child: Text('Groq cloud'))], onChanged: busy ? null : (value) { setState(() { widget.chatRepository.provider = value!; widget.chatRepository.reset(); messages.clear(); }); }),
    const SizedBox(height: AppSpacing.sm), Text(widget.chatRepository.provider == 'groq' ? 'Your question and selected incident metadata are sent to Groq. Video stays on your PC.' : 'Questions and incident evidence stay on your PC.', style: AppTypography.caption),
    if (widget.chatRepository.provider == 'ollama') CheckboxListTile(contentPadding: EdgeInsets.zero, value: widget.chatRepository.includeImages, onChanged: (value) => setState(() => widget.chatRepository.includeImages = value!), title: Text('Include evidence frames', style: AppTypography.support), activeColor: AppColors.foreground, checkColor: AppColors.background),
    Expanded(child: messages.isEmpty ? Center(child: Text('Ask what happened, which incidents need review, or where to find a recording.', textAlign: TextAlign.center, style: AppTypography.support)) : ListView.builder(itemCount: messages.length, itemBuilder: (context, index) { final m = messages[index]; return Padding(padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm), child: AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(m.isUser ? 'YOU' : 'SAFESPACE', style: AppTypography.caption), const SizedBox(height: AppSpacing.sm), SelectableText(m.text, style: AppTypography.body), if (m.eventIds.isNotEmpty) ...[const SizedBox(height: AppSpacing.md), Text('Evidence & recordings', style: AppTypography.support), for (final id in m.eventIds.take(5)) TextButton(onPressed: () => evidence(id), child: Text('Open ${id.substring(0, id.length.clamp(0, 12))}…', style: AppTypography.caption))]]))); })),
    if (busy) Text('Waiting for the model…', style: AppTypography.caption), if (error != null) Text(error!, style: AppTypography.body),
    const SizedBox(height: AppSpacing.sm), Row(crossAxisAlignment: CrossAxisAlignment.end, children: [Expanded(child: TextField(controller: controller, minLines: 1, maxLines: 4, decoration: const InputDecoration(hintText: 'What happened?', border: OutlineInputBorder()), onSubmitted: (_) => send())), const SizedBox(width: AppSpacing.sm), TextButton(onPressed: busy ? null : send, child: Text('Ask', style: AppTypography.button))]),
  ])));
}
