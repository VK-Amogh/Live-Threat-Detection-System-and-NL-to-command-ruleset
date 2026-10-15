import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'config.dart';

class AuthStore {
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();
  Future<String> getApiBaseUrl() async => (await SharedPreferences.getInstance()).getString(AppConfig.keyApiBaseUrl) ?? AppConfig.defaultApiBaseUrl;
  Future<void> setApiBaseUrl(String url) async {
    final parsed = Uri.tryParse(url);
    if (parsed == null || !['http', 'https'].contains(parsed.scheme) || parsed.host.isEmpty || parsed.userInfo.isNotEmpty) {
      throw const FormatException('Enter your server address, such as http://192.168.1.10:8000');
    }
    await (await SharedPreferences.getInstance()).setString(AppConfig.keyApiBaseUrl, url.replaceFirst(RegExp(r'/$'), ''));
  }
  Future<String?> getDeviceToken() => _secureStorage.read(key: AppConfig.keyDeviceToken);
  Future<String> getDeviceId() async => (await SharedPreferences.getInstance()).getString(AppConfig.keyDeviceId) ?? '';
  Future<String> getDeviceName() async => (await SharedPreferences.getInstance()).getString(AppConfig.keyDeviceName) ?? '';
  Future<void> savePairingSession({required String deviceId, required String deviceName, required String deviceToken}) async {
    await _secureStorage.write(key: AppConfig.keyDeviceToken, value: deviceToken);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.keyDeviceId, deviceId);
    await prefs.setString(AppConfig.keyDeviceName, deviceName);
  }
  Future<bool> isPaired() async { final token = await getDeviceToken(); return token != null && token.isNotEmpty && token != 'dev_mobile_opaque_token'; }
  Future<void> clearSession() async {
    await _secureStorage.delete(key: AppConfig.keyDeviceToken);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConfig.keyDeviceId);
    await prefs.remove(AppConfig.keyDeviceName);
  }
}
