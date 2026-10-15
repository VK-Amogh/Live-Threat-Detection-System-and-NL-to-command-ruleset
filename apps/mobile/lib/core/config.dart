class AppConfig {
  // Default LAN host (for Android emulator 10.0.2.2; on physical phone use Wi-Fi IP e.g. 192.168.1.x)
  static const String defaultApiBaseUrl = 'http://10.0.2.2:8000';
  
  // Supabase Cloud Configuration
  static const String supabaseUrl = 'https://hvdqlslmjyskuctkqpyr.supabase.co';
  static const String supabaseAnonKey = 'sb_publishable_gSnkSDi-2tjHrl8YBXNxtQ_FVQfxyPN';

  // Storage Keys
  static const String keyApiBaseUrl = 'safespace_api_url';
  static const String keyDeviceToken = 'safespace_device_token';
  static const String keyDeviceId = 'safespace_device_id';
  static const String keyDeviceName = 'safespace_device_name';
}
