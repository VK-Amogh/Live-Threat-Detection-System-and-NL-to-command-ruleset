import '../../core/api_client.dart';

class RulesRepository {
  final ApiClient api;
  RulesRepository(this.api);

  Future<List<Map<String, dynamic>>> cameras() async {
    final response = await api.dio.get('/api/v1/cameras');
    return (response.data as List).map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }

  Future<List<Map<String, dynamic>>> rules(String cameraId) async {
    final response = await api.dio.get('/api/v1/rules', queryParameters: {'camera_id': cameraId});
    return (response.data as List).map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }

  Future<List<Map<String, dynamic>>> templates() async {
    final response = await api.dio.get('/api/v1/rules/templates');
    return (response.data as List).map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }

  Future<List<Map<String, dynamic>>> rulesets() async {
    final response = await api.dio.get('/api/v1/rulesets');
    final raw = response.data;
    final items = raw is Map ? (raw['items'] as List? ?? const []) : (raw as List);
    return items.map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }

  Future<String> getSystemMode() async {
    final response = await api.dio.get('/api/v1/system/mode');
    return (response.data as Map)['mode'] as String? ?? 'HOME';
  }

  Future<String> setSystemMode(String mode) async {
    final response = await api.dio.put('/api/v1/system/mode', data: {'mode': mode});
    return (response.data as Map)['mode'] as String? ?? mode;
  }

  Future<Map<String, dynamic>> compile(String cameraId, String text, bool visual) async {
    final response = await api.dio.post('/api/v1/rules/compile', data: {
      'camera_id': cameraId,
      'text': text,
      'needs_visual_review': visual,
    });
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> createRuleset({
    required String name,
    required List<String> cameraIds,
    required String text,
    String? templateId,
    String? mode,
    Map<String, dynamic>? schedule,
    bool visual = false,
  }) async {
    final response = await api.dio.post('/api/v1/rulesets', data: {
      'name': name,
      'description': text,
      'camera_ids': cameraIds,
      'template_id': templateId,
      'text': text,
      'mode': mode,
      'schedule': schedule,
      'needs_visual_review': visual,
    });
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> activateRuleset(String id, String readbackHash) async {
    await api.dio.post('/api/v1/rulesets/$id/activate', data: {
      'confirmed_readback_hash': readbackHash,
      'acknowledge_experimental': true,
    });
  }

  Future<void> activate(String id, int version, String hash, bool experimental) async {
    await api.dio.post('/api/v1/rules/$id/activate', data: {
      'expected_version': version,
      'confirmed_readback_hash': hash,
      'acknowledge_experimental': experimental,
    });
  }

  Future<void> disable(String id, int version) async {
    await api.dio.patch('/api/v1/rules/$id', data: {'expected_version': version, 'status': 'disabled'});
  }

  Future<Map<String, dynamic>> dryRun(String ruleId) async {
    final response = await api.dio.post('/api/v1/rules/$ruleId/dry-run', data: {
      'synthetic_tracks': [
        {
          'track_id': 1,
          'class_name': 'person',
          'confidence': 0.92,
          'bbox': [120, 120, 260, 380],
          'dwell_seconds': 12.0,
        }
      ],
    });
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>?> getGeometry(String cameraId) async {
    final response = await api.dio.get('/api/v1/cameras/$cameraId/geometry');
    if (response.data == null) return null;
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> saveGeometry(String cameraId, Map<String, dynamic> geometry) async {
    await api.dio.put('/api/v1/cameras/$cameraId/geometry', data: geometry);
  }
}
