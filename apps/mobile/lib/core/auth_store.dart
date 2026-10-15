import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'config.dart';

class AuthStore {
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();

  Future<String> getApiBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(AppConfig.keyApiBaseUrl) ?? AppConfig.defaultApiBaseUrl;
  }

  Future<void> setApiBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.keyApiBaseUrl, url);
  }

  Future<String?> getDeviceToken() async {
    final token = await _secureStorage.read(key: AppConfig.keyDeviceToken);
    return token ?? AppConfig.defaultDeviceToken;
  }

  Future<String> getDeviceId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(AppConfig.keyDeviceId) ?? AppConfig.defaultDeviceId;
  }

  Future<String> getDeviceName() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(AppConfig.keyDeviceName) ?? AppConfig.defaultDeviceName;
  }

  Future<void> savePairingSession({
    required String deviceId,
    required String deviceName,
    required String deviceToken,
  }) async {
    await _secureStorage.write(key: AppConfig.keyDeviceToken, value: deviceToken);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.keyDeviceId, deviceId);
    await prefs.setString(AppConfig.keyDeviceName, deviceName);
    await prefs.setBool('safespace_unpaired_flag', false);
  }

  Future<void> seedHardcodedSession() async {
    await savePairingSession(
      deviceId: AppConfig.defaultDeviceId,
      deviceName: AppConfig.defaultDeviceName,
      deviceToken: AppConfig.defaultDeviceToken,
    );
  }

  Future<bool> isPaired() async {
    final prefs = await SharedPreferences.getInstance();
    final explicitlyUnpaired = prefs.getBool('safespace_unpaired_flag') ?? false;
    if (explicitlyUnpaired) {
      final token = await _secureStorage.read(key: AppConfig.keyDeviceToken);
      return token != null && token.isNotEmpty;
    }

    // Default: auto-seed hardcoded session for effortless zero-setup launch
    final token = await _secureStorage.read(key: AppConfig.keyDeviceToken);
    if (token == null || token.isEmpty) {
      await seedHardcodedSession();
    }
    return true;
  }

  Future<void> clearSession() async {
    await _secureStorage.delete(key: AppConfig.keyDeviceToken);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConfig.keyDeviceId);
    await prefs.remove(AppConfig.keyDeviceName);
    await prefs.setBool('safespace_unpaired_flag', true);
  }
}
