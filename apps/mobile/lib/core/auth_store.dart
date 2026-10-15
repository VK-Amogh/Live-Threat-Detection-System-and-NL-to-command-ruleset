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
    return await _secureStorage.read(key: AppConfig.keyDeviceToken);
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
  }

  Future<bool> isPaired() async {
    final token = await getDeviceToken();
    return token != null && token.isNotEmpty;
  }

  Future<void> clearSession() async {
    await _secureStorage.delete(key: AppConfig.keyDeviceToken);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConfig.keyDeviceId);
    await prefs.remove(AppConfig.keyDeviceName);
  }
}
