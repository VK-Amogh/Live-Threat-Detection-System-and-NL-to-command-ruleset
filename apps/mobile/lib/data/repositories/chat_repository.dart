import 'dart:convert';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';

class CitedFootage {
  final String eventId, label;
  final String? clipUrl, posterUrl;
  final int startMs;
  const CitedFootage({
    required this.eventId,
    required this.label,
    this.clipUrl,
    this.posterUrl,
    this.startMs = 0,
  });

  factory CitedFootage.fromJson(Map<String, dynamic> json) => CitedFootage(
        eventId: json['event_id'] as String,
        label: json['label'] as String? ?? 'Incident',
        clipUrl: json['clip_url'] as String?,
        posterUrl: json['poster_url'] as String?,
        startMs: (json['start_ms'] as num?)?.toInt() ?? 0,
      );
}

class EvidenceCardItem {
  final String id;
  final String kind;
  final String title;
  final String? subtitle;
  final String snippet;
  final String? mediaUrl;

  const EvidenceCardItem({
    required this.id,
    required this.kind,
    required this.title,
    this.subtitle,
    required this.snippet,
    this.mediaUrl,
  });

  factory EvidenceCardItem.fromJson(Map<String, dynamic> json) =>
      EvidenceCardItem(
        id: (json['id'] ?? '').toString(),
        kind: (json['kind'] ?? 'evidence').toString(),
        title: (json['title'] ?? 'Evidence').toString(),
        subtitle: json['subtitle']?.toString(),
        snippet: (json['snippet'] ?? '').toString(),
        mediaUrl: json['media_url']?.toString(),
      );
}

class ChatMessage {
  String text;
  final bool isUser;
  List<String> eventIds;
  List<CitedFootage> cited;
  List<EvidenceCardItem> evidence;
  String? intent;
  List<String> sources;
  String? status;
  String? model;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.eventIds = const [],
    this.cited = const [],
    this.evidence = const [],
    this.intent,
    this.sources = const [],
    this.status,
    this.model,
  });
}

class ChatConversation {
  final String id;
  final String title;
  final int messageCount;

  const ChatConversation(
      {required this.id, required this.title, required this.messageCount});

  factory ChatConversation.fromJson(Map<String, dynamic> json) =>
      ChatConversation(
        id: '${json['id']}',
        title: '${json['title'] ?? 'Conversation'}',
        messageCount: (json['message_count'] as num?)?.toInt() ?? 0,
      );
}

class ChatRepository {
  final ApiClient apiClient;
  String? _conversationId;
  String? eventId;
  bool includeImages = true;
  ChatRepository(this.apiClient);
  void reset() => _conversationId = null;

  Future<List<ChatConversation>> listConversations() async {
    final response = await apiClient.dio.get('/api/v1/chat/conversations');
    final items = (response.data as Map)['items'] as List? ?? const [];
    return items
        .map((item) =>
            ChatConversation.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }

  Future<List<ChatMessage>> openConversation(String id) async {
    final response = await apiClient.dio
        .get('/api/v1/chat/conversations/${Uri.encodeComponent(id)}');
    final body = response.data as Map;
    _conversationId = '${body['id']}';
    final items = body['messages'] as List? ?? const [];
    return items.map((item) {
      final saved = item as Map;
      return ChatMessage(
          text: '${saved['content'] ?? ''}', isUser: saved['role'] == 'user');
    }).toList();
  }

  /// Streams the assistant message; the same [ChatMessage] instance is mutated as tokens arrive.
  Stream<ChatMessage> ask(String text) async* {
    final message = ChatMessage(
      text: '',
      isUser: false,
      status: 'Planning evidence retrieval…',
    );
    yield message;
    final response = await apiClient.dio.post<ResponseBody>(
      '/api/v1/chat/stream',
      data: {
        'conversation_id': _conversationId,
        'message': text,
        'event_ids': eventId == null ? <String>[] : [eventId],
        'include_images': includeImages,
      },
      options: Options(
        responseType: ResponseType.stream,
        receiveTimeout: const Duration(minutes: 4),
      ),
    );
    final lines = response.data!.stream
        .cast<List<int>>()
        .transform(utf8.decoder)
        .transform(const LineSplitter());
    await for (final line in lines) {
      if (line.isEmpty) continue;
      final item = jsonDecode(line) as Map<String, dynamic>;
      switch (item['type']) {
        case 'error':
          throw Exception(item['message']);
        case 'plan':
          final plan = item['plan'] as Map?;
          if (plan != null) {
            message.intent = plan['intent']?.toString();
            message.sources = ((plan['sources'] as List?) ?? const [])
                .map((e) => e.toString())
                .toList();
          }
          message.status = 'Retrieving grounded evidence…';
        case 'evidence':
          message.evidence = ((item['items'] as List?) ?? const [])
              .map((e) => EvidenceCardItem.fromJson(
                  Map<String, dynamic>.from(e as Map)))
              .toList();
        case 'context':
          _conversationId = item['conversation_id'] as String?;
          message.eventIds =
              ((item['event_ids'] as List?) ?? const []).cast<String>();
          message.model = item['model'] as String?;
          message.status = 'Reading evidence…';
        case 'status':
          message.status = item['message'] as String?;
        case 'delta':
          message.text += item['text'] as String;
          message.status = null;
        case 'done':
          message.text = (item['answer'] as String?) ?? message.text;
          message.model = item['model'] as String?;
          message.cited = ((item['cited'] as List?) ?? const [])
              .map((e) =>
                  CitedFootage.fromJson(Map<String, dynamic>.from(e as Map)))
              .toList();
          message.status = null;
      }
      yield message;
    }
  }
}
