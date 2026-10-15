import 'package:flutter/material.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/glass_surface.dart';
import '../../core/widgets/press_scale.dart';
import '../../data/repositories/chat_repository.dart';

class ChatScreen extends StatefulWidget {
  final ChatRepository chatRepository;

  const ChatScreen({super.key, required this.chatRepository});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final List<ChatMessage> _messages = [];
  final _controller = TextEditingController();
  bool _isSending = false;

  Future<void> _sendMessage([String? presetText]) async {
    final text = presetText ?? _controller.text.trim();
    if (text.isEmpty || _isSending) return;

    if (presetText == null) {
      _controller.clear();
    }

    setState(() {
      _messages.add(ChatMessage(text: text, isUser: true));
      _isSending = true;
    });

    try {
      final reply = await widget.chatRepository.sendMessage(text);
      setState(() {
        _messages.add(reply);
        _isSending = false;
      });
    } catch (e) {
      setState(() {
        _messages.add(ChatMessage(
          text: 'Assistant error: $e',
          isUser: false,
        ));
        _isSending = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.lg,
                AppSpacing.md,
                AppSpacing.lg,
                AppSpacing.sm,
              ),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Threat Intelligence', style: AppTypography.screenTitle),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      'Natural Language Incident Queries & Summaries',
                      style: AppTypography.support,
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: _messages.isEmpty
                  ? EmptyState(
                      icon: Icons.chat_bubble_outline_rounded,
                      title: 'Query Threat Logs',
                      message: 'Ask questions about incidents detected across your cameras.',
                      action: Wrap(
                        spacing: AppSpacing.sm,
                        runSpacing: AppSpacing.sm,
                        alignment: WrapAlignment.center,
                        children: [
                          _suggestionChip('Show weapon detections today'),
                          _suggestionChip('List high-severity alerts'),
                          _suggestionChip('Summarize camera activity'),
                        ],
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.lg,
                        AppSpacing.sm,
                        AppSpacing.lg,
                        88, // Clear input bar
                      ),
                      itemCount: _messages.length,
                      itemBuilder: (context, index) {
                        final msg = _messages[index];
                        return Align(
                          alignment: msg.isUser
                              ? Alignment.centerRight
                              : Alignment.centerLeft,
                          child: Container(
                            margin: const EdgeInsets.only(bottom: AppSpacing.md),
                            padding: const EdgeInsets.all(AppSpacing.md),
                            constraints: BoxConstraints(
                              maxWidth: MediaQuery.of(context).size.width * 0.78,
                            ),
                            decoration: BoxDecoration(
                              color: msg.isUser
                                  ? AppColors.foreground
                                  : AppColors.surface,
                              borderRadius: BorderRadius.circular(AppRadii.lg),
                              border: msg.isUser
                                  ? null
                                  : Border.all(color: AppColors.divider, width: 1.0),
                            ),
                            child: Text(
                              msg.text,
                              style: AppTypography.body.copyWith(
                                color: msg.isUser
                                    ? AppColors.background
                                    : AppColors.foreground,
                                height: 1.4,
                              ),
                            ),
                          ),
                        );
                      },
                    ),
            ),
            if (_isSending)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: AppSpacing.xs),
                child: SizedBox(
                  height: 16,
                  width: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppColors.foreground,
                  ),
                ),
              ),

            // Floating Input Bar
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.lg,
                AppSpacing.xs,
                AppSpacing.lg,
                80, // Clearance for floating nav pill
              ),
              child: GlassSurface(
                height: AppSpacing.floatingBarHeight,
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        style: AppTypography.body,
                        decoration: InputDecoration(
                          hintText: 'Search alerts with natural language...',
                          hintStyle: AppTypography.body.copyWith(
                            color: AppColors.foregroundSecondary,
                          ),
                          border: InputBorder.none,
                        ),
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                    PressScale(
                      onTap: () => _sendMessage(),
                      pressedScale: 0.90,
                      child: Container(
                        width: AppSpacing.smallCircle,
                        height: AppSpacing.smallCircle,
                        decoration: const BoxDecoration(
                          color: AppColors.foreground,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.arrow_upward_rounded,
                          size: 20,
                          color: AppColors.background,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _suggestionChip(String label) {
    return PressScale(
      onTap: () => _sendMessage(label),
      pressedScale: 0.96,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadii.pill),
          border: Border.all(color: AppColors.divider, width: 1.0),
        ),
        child: Text(
          label,
          style: AppTypography.caption.copyWith(color: AppColors.foreground),
        ),
      ),
    );
  }
}
