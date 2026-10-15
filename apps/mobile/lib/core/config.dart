class AppConfig {
  // Default connection targets
  static const String defaultApiBaseUrl = 'http://localhost:8000';
  static const String defaultLanBaseUrl = 'http://10.12.253.133:8000';
  
  // Hardcoded default device session for zero-friction pairing
  static const String defaultDeviceId = 'd1e2f3a4-5d0a-4c3e-9d57-2d8a6c1f9a50';
  static const String defaultDeviceName = 'Android Security Terminal';
  static const String defaultDeviceToken = 'dev_mobile_opaque_token';
  static const String defaultPairingCode = 'SAFE-9821';

  // Supabase Cloud Configuration
  static const String supabaseUrl = 'https://hvdqlslmjyskuctkqpyr.supabase.co';
  static const String supabaseAnonKey = 'sb_publishable_gSnkSDi-2tjHrl8YBXNxtQ_FVQfxyPN';

  // Storage Keys
  static const String keyApiBaseUrl = 'safespace_api_url';
  static const String keyDeviceToken = 'safespace_device_token';
  static const String keyDeviceId = 'safespace_device_id';
  static const String keyDeviceName = 'safespace_device_name';
}
