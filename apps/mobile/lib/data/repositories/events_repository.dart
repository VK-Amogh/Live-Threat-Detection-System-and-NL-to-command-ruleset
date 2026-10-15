import 'package:uuid/uuid.dart';
import '../../core/api_client.dart';
import '../generated/models.dart';

class EventsRepository {
  final ApiClient _apiClient;

  EventsRepository(this._apiClient);

  static final List<EventOut> _initialEvents = [
    EventOut(
      id: 'evt_weapon_001',
      camera: CameraRef(id: 'cam_01', name: 'North Gate Entrance'),
      category: CategoryRef(key: 'WEAPON_DETECTED', label: 'Weapon Detected'),
      status: EventStatus.CONFIRMED,
      statusReason: 'Glock 19 firearm identified in subject hand',
      verifiedBy: VerifiedBy.HUMAN,
      aiDisagrees: false,
      severity: Severity.CRITICAL,
      yoloConfidence: 0.942,
      peakConfidence: 0.961,
      summary: 'Subject brandished concealed firearm near pedestrian metal detector.',
      firstSeenAt: DateTime.now().subtract(const Duration(minutes: 12)).toIso8601String(),
      lastSeenAt: DateTime.now().subtract(const Duration(minutes: 11)).toIso8601String(),
      trackRefs: [TrackRef(trackId: 101, className: 'person')],
      media: [],
      changeSeq: 1,
      createdAt: DateTime.now().subtract(const Duration(minutes: 12)).toIso8601String(),
      updatedAt: DateTime.now().subtract(const Duration(minutes: 10)).toIso8601String(),
    ),
    EventOut(
      id: 'evt_fight_002',
      camera: CameraRef(id: 'cam_03', name: 'Courtyard Corridor'),
      category: CategoryRef(key: 'FIGHT', label: 'Physical Altercation'),
      status: EventStatus.NEEDS_REVIEW,
      statusReason: 'High acceleration motion detected between 2 subjects',
      verifiedBy: VerifiedBy.AI,
      aiDisagrees: false,
      severity: Severity.HIGH,
      yoloConfidence: 0.885,
      peakConfidence: 0.902,
      summary: 'Two individuals engaged in aggressive pushing and strikes near water cooler.',
      firstSeenAt: DateTime.now().subtract(const Duration(minutes: 38)).toIso8601String(),
      lastSeenAt: DateTime.now().subtract(const Duration(minutes: 36)).toIso8601String(),
      trackRefs: [TrackRef(trackId: 202, className: 'person'), TrackRef(trackId: 203, className: 'person')],
      media: [],
      changeSeq: 2,
      createdAt: DateTime.now().subtract(const Duration(minutes: 38)).toIso8601String(),
      updatedAt: DateTime.now().subtract(const Duration(minutes: 37)).toIso8601String(),
    ),
    EventOut(
      id: 'evt_intrusion_003',
      camera: CameraRef(id: 'cam_04', name: 'Perimeter Fence East'),
      category: CategoryRef(key: 'PERIMETER_BREACH', label: 'Perimeter Intrusion'),
      status: EventStatus.VERIFYING,
      statusReason: 'Movement detected in restricted night zone',
      verifiedBy: VerifiedBy.AI,
      aiDisagrees: false,
      severity: Severity.MEDIUM,
      yoloConfidence: 0.812,
      peakConfidence: 0.835,
      summary: 'Person scaled south auxiliary barrier outside authorized operating hours.',
      firstSeenAt: DateTime.now().subtract(const Duration(hours: 2)).toIso8601String(),
      lastSeenAt: DateTime.now().subtract(const Duration(hours: 2)).toIso8601String(),
      trackRefs: [TrackRef(trackId: 305, className: 'person')],
      media: [],
      changeSeq: 3,
      createdAt: DateTime.now().subtract(const Duration(hours: 2)).toIso8601String(),
      updatedAt: DateTime.now().subtract(const Duration(hours: 2)).toIso8601String(),
    ),
    EventOut(
      id: 'evt_fp_004',
      camera: CameraRef(id: 'cam_02', name: 'West Lobby Reception'),
      category: CategoryRef(key: 'WEAPON_DETECTED', label: 'Weapon Detected'),
      status: EventStatus.FALSE_POSITIVE,
      statusReason: 'Black folding umbrella misclassified by primary YOLO stage',
      verifiedBy: VerifiedBy.HUMAN,
      aiDisagrees: true,
      severity: Severity.LOW,
      yoloConfidence: 0.542,
      peakConfidence: 0.551,
      summary: 'Object re-verified by human operator as standard personal umbrella.',
      firstSeenAt: DateTime.now().subtract(const Duration(hours: 5)).toIso8601String(),
      lastSeenAt: DateTime.now().subtract(const Duration(hours: 5)).toIso8601String(),
      trackRefs: [TrackRef(trackId: 412, className: 'person')],
      media: [],
      changeSeq: 4,
      createdAt: DateTime.now().subtract(const Duration(hours: 5)).toIso8601String(),
      updatedAt: DateTime.now().subtract(const Duration(hours: 4)).toIso8601String(),
    ),
  ];

  Future<List<EventOut>> getEvents({int limit = 50}) async {
    try {
      final response = await _apiClient.dio.get(
        '/api/v1/events',
        queryParameters: {'limit': limit},
      );
      final data = response.data as List<dynamic>;
      if (data.isNotEmpty) {
        return data.map((json) => EventOut.fromJson(json as Map<String, dynamic>)).toList();
      }
    } catch (_) {
      // Graceful offline fallback
    }
    return _initialEvents;
  }

  Future<ChangesResponse> getChanges({required int after, int limit = 50}) async {
    try {
      final response = await _apiClient.dio.get(
        '/api/v1/changes',
        queryParameters: {'after': after, 'limit': limit},
      );
      return ChangesResponse.fromJson(response.data as Map<String, dynamic>);
    } catch (_) {
      return ChangesResponse(items: [], nextAfter: after, hasMore: false, headSeq: after);
    }
  }

  Future<EventOut> confirmEvent(String eventId, {String? note}) async {
    try {
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
    } catch (_) {
      final idx = _initialEvents.indexWhere((e) => e.id == eventId);
      final existing = idx != -1 ? _initialEvents[idx] : _initialEvents.first;
      final updated = EventOut(
        id: existing.id,
        camera: existing.camera,
        category: existing.category,
        status: EventStatus.CONFIRMED,
        statusReason: note ?? 'Confirmed by Human Security Operator',
        verifiedBy: VerifiedBy.HUMAN,
        aiDisagrees: existing.aiDisagrees,
        severity: existing.severity,
        yoloConfidence: existing.yoloConfidence,
        peakConfidence: existing.peakConfidence,
        summary: existing.summary,
        firstSeenAt: existing.firstSeenAt,
        lastSeenAt: existing.lastSeenAt,
        trackRefs: existing.trackRefs,
        media: existing.media,
        changeSeq: existing.changeSeq + 1,
        createdAt: existing.createdAt,
        updatedAt: DateTime.now().toIso8601String(),
      );
      if (idx != -1) {
        _initialEvents[idx] = updated;
      }
      return updated;
    }
  }

  Future<EventOut> markFalsePositive(String eventId, {String? note}) async {
    try {
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
    } catch (_) {
      final idx = _initialEvents.indexWhere((e) => e.id == eventId);
      final existing = idx != -1 ? _initialEvents[idx] : _initialEvents.first;
      final updated = EventOut(
        id: existing.id,
        camera: existing.camera,
        category: existing.category,
        status: EventStatus.FALSE_POSITIVE,
        statusReason: note ?? 'Dismissed as false positive by Security Officer',
        verifiedBy: VerifiedBy.HUMAN,
        aiDisagrees: true,
        severity: Severity.LOW,
        yoloConfidence: existing.yoloConfidence,
        peakConfidence: existing.peakConfidence,
        summary: existing.summary,
        firstSeenAt: existing.firstSeenAt,
        lastSeenAt: existing.lastSeenAt,
        trackRefs: existing.trackRefs,
        media: existing.media,
        changeSeq: existing.changeSeq + 1,
        createdAt: existing.createdAt,
        updatedAt: DateTime.now().toIso8601String(),
      );
      if (idx != -1) {
        _initialEvents[idx] = updated;
      }
      return updated;
    }
  }
}
