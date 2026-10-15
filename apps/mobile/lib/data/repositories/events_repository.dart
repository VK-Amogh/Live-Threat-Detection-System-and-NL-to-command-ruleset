import 'package:uuid/uuid.dart';
import '../../core/api_client.dart';
import '../generated/models.dart';

class EventsRepository {
  final ApiClient _apiClient;

  EventsRepository(this._apiClient);

  Future<List<EventOut>> getEvents({int limit = 50}) async {
    final response = await _apiClient.dio.get(
      '/api/v1/events',
      queryParameters: {'limit': limit},
    );
    final data = response.data as List<dynamic>;
    return data.map((json) => EventOut.fromJson(json as Map<String, dynamic>)).toList();
  }

  Future<ChangesResponse> getChanges({required int after, int limit = 50}) async {
    final response = await _apiClient.dio.get(
      '/api/v1/changes',
      queryParameters: {'after': after, 'limit': limit},
    );
    return ChangesResponse.fromJson(response.data as Map<String, dynamic>);
  }

  Future<EventOut> confirmEvent(String eventId, {String? note}) async {
    final req = HumanVerificationRequest(
      clientActionId: const Uuid().v4(),
      action: HumanAction.CONFIRM,
      note: note,
    );
    final response = await _apiClient.dio.post(
      '/api/v1/events/$eventId/verification',
      data: req.toJson(),
    );
    return EventOut.fromJson(response.data as Map<String, dynamic>);
  }

  Future<EventOut> markFalsePositive(String eventId, {String? note}) async {
    final req = HumanVerificationRequest(
      clientActionId: const Uuid().v4(),
      action: HumanAction.MARK_FALSE_POSITIVE,
      note: note,
    );
    final response = await _apiClient.dio.post(
      '/api/v1/events/$eventId/verification',
      data: req.toJson(),
    );
    return EventOut.fromJson(response.data as Map<String, dynamic>);
  }
}
