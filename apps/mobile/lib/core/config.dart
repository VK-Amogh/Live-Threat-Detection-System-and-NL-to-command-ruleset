class AppConfig {
  static const defaultApiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
  static const keyApiBaseUrl = 'safespace_api_url';
  static const keyDeviceToken = 'safespace_device_token';
  static const keyDeviceId = 'safespace_device_id';
  static const keyDeviceName = 'safespace_device_name';
}
