import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import 'config.dart';

class AuthStore {
  static const _androidOptions = AndroidOptions(
    encryptedSharedPreferences: true,
    resetOnError: true,
  );

  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage(
    aOptions: _androidOptions,
  );

  Future<String> getApiBaseUrl() async {
    final saved = (await SharedPreferences.getInstance()).getString(AppConfig.keyApiBaseUrl);
    if (saved == null || saved.isEmpty) {
      return AppConfig.bakedUrls.isEmpty ? 'http://127.0.0.1:8000' : AppConfig.bakedUrls.first;
    }
    return saved;
  }

  /// The active route. Any http(s) address is valid: which networks are acceptable is decided by the server's
  /// network policy and by the route manager's identity check, not by a hardcoded subnet in the app.
  Future<void> setApiBaseUrl(String url) async {
    final parsed = Uri.tryParse(url.trim());
    if (parsed == null || !['http', 'https'].contains(parsed.scheme) || parsed.host.isEmpty || parsed.userInfo.isNotEmpty) {
      throw const FormatException("Enter your laptop's address, such as http://192.168.1.10:8000 or https://192.168.1.10:8443");
    }
    await (await SharedPreferences.getInstance()).setString(AppConfig.keyApiBaseUrl, AppConfig.normalizeUrl(url));
  }

  /// A random id created on first launch. The server derives this phone's device id and camera id from it, so
  /// signing in again (or re-pairing) never creates a second camera and never orphans a camera's rules or recordings.
  Future<String> getInstallationId() async {
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(AppConfig.keyInstallationId);
    if (id == null || id.length < 8) {
      id = const Uuid().v4();
      await prefs.setString(AppConfig.keyInstallationId, id);
    }
    return id;
  }

  Future<String?> getDeviceToken() async {
    try {
      return await _secureStorage.read(key: AppConfig.keyDeviceToken);
    } catch (e) {
      debugPrint('[AuthStore] Error reading device token (resetting storage): $e');
      try {
        await _secureStorage.deleteAll();
      } catch (_) {}
      return null;
    }
  }

  Future<String> getDeviceId() async => (await SharedPreferences.getInstance()).getString(AppConfig.keyDeviceId) ?? '';
  Future<String> getDeviceName() async => (await SharedPreferences.getInstance()).getString(AppConfig.keyDeviceName) ?? '';
  Future<String?> getCameraId() async => (await SharedPreferences.getInstance()).getString(AppConfig.keyCameraId);
  Future<String> getScope() async => (await SharedPreferences.getInstance()).getString(AppConfig.keyScope) ?? 'admin';

  Future<void> savePairingSession({
    required String deviceId,
    required String deviceName,
    required String deviceToken,
    String? cameraId,
    String scope = 'admin',
  }) async {
    try {
      await _secureStorage.write(key: AppConfig.keyDeviceToken, value: deviceToken);
    } catch (e) {
      debugPrint('[AuthStore] Error writing device token (retrying after reset): $e');
      try {
        await _secureStorage.deleteAll();
        await _secureStorage.write(key: AppConfig.keyDeviceToken, value: deviceToken);
      } catch (_) {}
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.keyDeviceId, deviceId);
    await prefs.setString(AppConfig.keyDeviceName, deviceName);
    await prefs.setString(AppConfig.keyScope, scope);
    if (cameraId != null && cameraId.isNotEmpty) {
      await prefs.setString(AppConfig.keyCameraId, cameraId);
    }
  }

  Future<bool> isPaired() async {
    try {
      final token = await getDeviceToken();
      return token != null && token.isNotEmpty && token != 'dev_mobile_opaque_token';
    } catch (e) {
      debugPrint('[AuthStore] isPaired error: $e');
      return false;
    }
  }

  Future<void> clearSession() async {
    try {
      await _secureStorage.delete(key: AppConfig.keyDeviceToken);
    } catch (e) {
      try {
        await _secureStorage.deleteAll();
      } catch (_) {}
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConfig.keyDeviceId);
    await prefs.remove(AppConfig.keyDeviceName);
    await prefs.remove(AppConfig.keyCameraId);
    await prefs.remove(AppConfig.keyScope);
  }
}
