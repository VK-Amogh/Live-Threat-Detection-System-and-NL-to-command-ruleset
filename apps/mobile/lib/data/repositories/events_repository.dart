import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import '../../core/api_client.dart';
import '../generated/models.dart';

class EventsRepository {
  final ApiClient apiClient;
  final revision = ValueNotifier<int>(0);
  EventsRepository(this.apiClient);
  void invalidate() => revision.value++;
  Future<List<EventOut>> getEvents({int limit = 100}) async {
    final response = await apiClient.dio.get('/api/v1/events', queryParameters: {'limit': limit});
    return (response.data as List).map((e) => EventOut.fromJson(Map<String, dynamic>.from(e))).toList();
  }
  Future<EventOut> getEvent(String id) async => EventOut.fromJson(Map<String, dynamic>.from((await apiClient.dio.get('/api/v1/events/$id')).data));
  Future<ChangesResponse> getChanges({required int after, int limit = 50}) async => ChangesResponse.fromJson(Map<String, dynamic>.from((await apiClient.dio.get('/api/v1/changes', queryParameters: {'after': after, 'limit': limit})).data));
  Future<EventOut> _review(String id, HumanAction action, String? note) async {
    final response = await apiClient.dio.post('/api/v1/events/$id/verification', data: HumanVerificationRequest(clientActionId: const Uuid().v4(), action: action, note: note).toJson());
    invalidate();
    return EventOut.fromJson(Map<String, dynamic>.from(response.data));
  }
  Future<EventOut> confirmEvent(String eventId, {String? note}) => _review(eventId, HumanAction.CONFIRM, note);
  Future<EventOut> markFalsePositive(String eventId, {String? note}) => _review(eventId, HumanAction.MARK_FALSE_POSITIVE, note);
}
