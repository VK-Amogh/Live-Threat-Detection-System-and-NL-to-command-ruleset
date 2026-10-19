import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/api_client.dart';
import '../core/auth_store.dart';
import '../core/config.dart';
import '../core/device_info.dart';
import '../core/net/pairing_link.dart';
import '../core/net/route_manager.dart';

class SessionResult {
  final String scope; // admin | camera
  final String role; // control | camera
  final String? cameraId;
  const SessionResult(this.scope, this.role, this.cameraId);
  bool get isCamera => scope == 'camera';
}

/// Everything that turns "a phone with the app" into "a device the laptop knows": sign in, enroll as a camera, or
/// redeem a pairing link. One place, so the request bodies match what the server validates (it rejects unknown fields).
class SessionService {
  static const appVersion = '3.1.0';

  SessionService(this.api, this.store, this.routes);
  final ApiClient api;
  final AuthStore store;
  final RouteManager routes;

  Future<RouteStatus> connect() async {
    final status = await routes.resolve();
    if (status == null) throw SessionException(explainNoRoute());
    return status;
  }

  /// Plain-language reason nothing answered, built from the last probe round.
  String explainNoRoute() {
    final probes = routes.lastProbes;
    final refused = probes.where((p) => p.reachable && p.error != null).toList();
    if (refused.isNotEmpty) return refused.first.error!;
    if (probes.isEmpty) return 'No laptop address is known yet. Open the pairing link from the dashboard on this phone.';
    return 'Cannot reach your laptop from this network. ${probes.first.error ?? ''}'.trim();
  }

  Future<Map<String, dynamic>> _identity() async {
    final d = await DeviceInfoService.read();
    return {
      'installation_id': await store.getInstallationId(),
      'model': d.model,
      'os_version': d.osVersion,
      'app_version': appVersion,
    };
  }

  Future<SessionResult> signIn(String email, String password) async {
    await _ensureConnected();
    final id = await _identity();
    final r = await _post('/api/v1/auth/login', {
      'username': email,
      'password': password,
      'device_name': id['model'],
      'client_type': 'mobile',
      'role': 'control',
      ...id,
    });
    return _save(r, tokenKey: 'device_token');
  }

  Future<SessionResult> enrollCamera() async {
    await _ensureConnected();
    final id = await _identity();
    final r = await _post('/api/v1/devices/enroll', {
      'enrollment_code': AppConfig.cameraEnrollmentCode,
      'device_name': '${id['model']} camera',
      'role': 'camera',
      ...id,
    });
    return _save(r, tokenKey: 'token');
  }

  Future<SessionResult> redeem(PairingLink link) async {
    if (link.serverId.isNotEmpty && link.serverId != AppConfig.serverId) {
      throw const SessionException('This link belongs to a different SafeSpace server.');
    }
    await routes.learn(link.urls, source: 'link', pins: link.pins);
    await _ensureConnected();
    final id = await _identity();
    final r = await _post('/api/v1/auth/pair', {
      'code': link.code,
      'device_name': link.isCamera ? '${id['model']} camera' : id['model'],
      ...id,
    });
    return _save(r, tokenKey: 'device_token');
  }

  Future<void> _ensureConnected() async {
    if (routes.connected) return;
    await connect();
  }

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
    try {
      final r = await api.dio.post(path, data: body);
      return Map<String, dynamic>.from(r.data as Map);
    } on DioException catch (e) {
      throw SessionException(describe(e));
    }
  }

  Future<SessionResult> _save(Map<String, dynamic> r, {required String tokenKey}) async {
    final scope = (r['scope'] as String?) ?? 'admin';
    await store.savePairingSession(
      deviceId: r['device_id'] as String,
      deviceName: (r['device_name'] as String?) ?? 'This phone',
      deviceToken: r[tokenKey] as String,
      cameraId: r['camera_id'] as String?,
      scope: scope,
    );
    final role = scope == 'camera' ? 'camera' : 'control';
    await (await SharedPreferences.getInstance()).setString(AppConfig.keyPhoneMode, role == 'camera' ? 'camera' : 'admin');
    return SessionResult(scope, role, r['camera_id'] as String?);
  }

  /// A message a person can act on, whatever went wrong underneath.
  static String describe(Object e) {
    if (e is SessionException) return e.message;
    if (e is DioException) {
      final data = e.response?.data;
      if (data is Map && data['detail'] is String) return data['detail'] as String;
      if (data is Map && data['detail'] is List) return 'The laptop could not accept that request.';
      switch (e.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.receiveTimeout:
        case DioExceptionType.sendTimeout:
          return 'The laptop did not answer in time. Check that you are on a network it can be reached from.';
        default:
          return 'Cannot reach your laptop from this network.';
      }
    }
    return e.toString();
  }
}

class SessionException implements Exception {
  final String message;
  const SessionException(this.message);
  @override
  String toString() => message;
}
