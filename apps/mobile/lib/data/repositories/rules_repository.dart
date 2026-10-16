import '../../core/api_client.dart';

class RulesRepository {
  final ApiClient api;
  RulesRepository(this.api);

  Future<List<Map<String, dynamic>>> cameras() async {
    final response = await api.dio.get('/api/v1/cameras');
    return (response.data as List).map((item) => Map<String, dynamic>.from(item)).toList();
  }

  Future<List<Map<String, dynamic>>> rules(String cameraId) async {
    final response = await api.dio.get('/api/v1/rules', queryParameters: {'camera_id': cameraId});
    return (response.data as List).map((item) => Map<String, dynamic>.from(item)).toList();
  }

  Future<Map<String, dynamic>> compile(String cameraId, String text, bool visual) async {
    final response = await api.dio.post('/api/v1/rules/compile', data: {
      'camera_id': cameraId, 'text': text, 'needs_visual_review': visual,
    });
    return Map<String, dynamic>.from(response.data);
  }

  Future<void> activate(String id, int version, String hash, bool experimental) async {
    await api.dio.post('/api/v1/rules/$id/activate', data: {
      'expected_version': version, 'confirmed_readback_hash': hash,
      'acknowledge_experimental': experimental,
    });
  }

  Future<void> disable(String id, int version) async {
    await api.dio.patch('/api/v1/rules/$id', data: {'expected_version': version, 'status': 'disabled'});
  }
}
