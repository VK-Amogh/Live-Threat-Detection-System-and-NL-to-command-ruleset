import 'package:dio/dio.dart';
import '../../core/api_client.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final List<String> eventIds;
  ChatMessage({required this.text, required this.isUser, this.eventIds = const []});
}
class ChatRepository {
  final ApiClient apiClient;
  String? _conversationId;
  String provider = 'ollama';
  String? eventId;
  bool includeImages = false;
  ChatRepository(this.apiClient);
  void reset() => _conversationId = null;
  Future<ChatMessage> sendMessage(String text) async {
    final response = await apiClient.dio.post('/api/v1/chat', data: {
      'conversation_id': _conversationId, 'message': text, 'provider': provider,
      'event_ids': eventId == null ? <String>[] : [eventId], 'include_images': includeImages && provider == 'ollama',
    }, options: Options(receiveTimeout: const Duration(minutes: 4)));
    final data = Map<String, dynamic>.from(response.data);
    _conversationId = data['conversation_id'];
    return ChatMessage(text: data['answer'], isUser: false, eventIds: (data['event_ids'] as List).cast<String>());
  }
}
