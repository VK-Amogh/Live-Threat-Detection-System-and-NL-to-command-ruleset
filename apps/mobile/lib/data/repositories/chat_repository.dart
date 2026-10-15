import '../../core/api_client.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final List<String> eventIds;

  ChatMessage({required this.text, required this.isUser, this.eventIds = const []});
}

class ChatRepository {
  final ApiClient _apiClient;
  String? _conversationId;

  ChatRepository(this._apiClient);

  Future<ChatMessage> sendMessage(String text) async {
    final response = await _apiClient.dio.post(
      '/api/v1/chat',
      data: {
        'conversation_id': _conversationId,
        'message': text,
      },
    );

    final data = response.data as Map<String, dynamic>;
    _conversationId = data['conversation_id'] as String?;
    final answer = data['answer'] as String;
    final eventIds = (data['event_ids'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [];

    return ChatMessage(text: answer, isUser: false, eventIds: eventIds);
  }
}
