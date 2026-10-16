import 'dart:convert';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';

class CitedFootage {
  final String eventId, label;
  final String? clipUrl, posterUrl;
  final int startMs;
  const CitedFootage({required this.eventId, required this.label, this.clipUrl, this.posterUrl, this.startMs = 0});
  factory CitedFootage.fromJson(Map<String, dynamic> json) => CitedFootage(
        eventId: json['event_id'] as String,
        label: json['label'] as String? ?? 'Incident',
        clipUrl: json['clip_url'] as String?,
        posterUrl: json['poster_url'] as String?,
        startMs: (json['start_ms'] as num?)?.toInt() ?? 0,
      );
}

class ChatMessage {
  String text;
  final bool isUser;
  List<String> eventIds;
  List<CitedFootage> cited;
  String? status;
  String? model;
  ChatMessage({required this.text, required this.isUser, this.eventIds = const [], this.cited = const [], this.status, this.model});
}

class ChatRepository {
  final ApiClient apiClient;
  String? _conversationId;
  String provider = 'ollama';
  String? eventId;
  bool includeImages = true;
  ChatRepository(this.apiClient);
  void reset() => _conversationId = null;

  /// Streams the assistant message; the same [ChatMessage] instance is mutated as tokens arrive.
  Stream<ChatMessage> ask(String text) async* {
    final message = ChatMessage(text: '', isUser: false, status: 'Searching incident records…');
    yield message;
    final response = await apiClient.dio.post<ResponseBody>('/api/v1/chat/stream',
        data: {
          'conversation_id': _conversationId,
          'message': text,
          'provider': provider,
          'event_ids': eventId == null ? <String>[] : [eventId],
          'include_images': includeImages,
        },
        options: Options(responseType: ResponseType.stream, receiveTimeout: const Duration(minutes: 4)));
    final lines = response.data!.stream.cast<List<int>>().transform(utf8.decoder).transform(const LineSplitter());
    await for (final line in lines) {
      if (line.isEmpty) continue;
      final item = jsonDecode(line) as Map<String, dynamic>;
      switch (item['type']) {
        case 'error':
          throw Exception(item['message']);
        case 'context':
          _conversationId = item['conversation_id'] as String?;
          message.eventIds = (item['event_ids'] as List).cast<String>();
          message.model = item['model'] as String?;
          message.status = 'Reading evidence…';
        case 'status':
          message.status = item['message'] as String?;
        case 'delta':
          message.text += item['text'] as String;
          message.status = null;
        case 'done':
          message.cited = ((item['cited'] as List?) ?? const []).map((e) => CitedFootage.fromJson(Map<String, dynamic>.from(e as Map))).toList();
          message.status = null;
      }
      yield message;
    }
  }
}
