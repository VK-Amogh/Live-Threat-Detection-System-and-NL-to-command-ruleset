/// Build-time configuration. `scripts/build-apk.ps1` writes `.dart_defines.json` from the laptop's `.env` and the
/// live network, so the APK ships already knowing its server. Defaults keep a plain `flutter run` working.
class AppConfig {
  /// Identity of the one laptop this build belongs to. A host that cannot prove it knows the shared secret is ignored.
  static const serverId = String.fromEnvironment('SERVER_ID', defaultValue: 'ss-7f3c2a');

  /// Addresses to try first, comma separated (hotspot, iBus, Windows hotspot, Tailscale name, relay...).
  static const serverUrls = String.fromEnvironment('SERVER_URLS', defaultValue: 'http://10.11.229.33:8000');

  /// SHA-256 pins (base64) of the server's TLS public key, comma separated.
  static const tlsPins = String.fromEnvironment('TLS_PINS');

  /// Shared secret: authenticates the server to the app (HMAC challenge) and the app to discovery on open networks.
  static const cameraEnrollmentCode =
      String.fromEnvironment('CAMERA_ENROLLMENT_CODE', defaultValue: 'ss-enroll-np4a-7495-9f8e7d6c5b4a3210');

  static const discoveryPort = int.fromEnvironment('DISCOVERY_PORT', defaultValue: 47800);

  /// One-tap sign-in tiles for the built-in admin accounts ("email|Label", comma separated).
  static const accounts = String.fromEnvironment('ACCOUNTS', defaultValue: 'admin1@safespace.com|Admin 1,admin2@safespace.com|Admin 2');
  static const demoPassword = String.fromEnvironment('DEMO_PASSWORD', defaultValue: 'admin123');
  static const demoAutofill = bool.fromEnvironment('DEMO_AUTOFILL', defaultValue: true);

  static List<String> get bakedUrls => _split(serverUrls).map(normalizeUrl).toList();
  static List<String> get bakedPins => _split(tlsPins);
  static List<MapEntry<String, String>> get accountTiles => _split(accounts).map((entry) {
        final parts = entry.split('|');
        return MapEntry(parts.first.trim(), parts.length > 1 ? parts[1].trim() : parts.first.split('@').first);
      }).toList();

  static List<String> _split(String raw) => raw.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();

  static String normalizeUrl(String url) => url.trim().replaceFirst(RegExp(r'/+$'), '');

  static const keyApiBaseUrl = 'safespace_api_url';
  static const keyDeviceToken = 'safespace_device_token';
  static const keyDeviceId = 'safespace_device_id';
  static const keyDeviceName = 'safespace_device_name';
  static const keyCameraId = 'safespace_camera_id';
  static const keyScope = 'safespace_token_scope';
  static const keyInstallationId = 'safespace_installation_id';
  static const keyKnownRoutes = 'safespace_known_routes';
  static const keyPins = 'safespace_tls_pins';
  static const keyPhoneMode = 'safespace_phone_mode';
}
