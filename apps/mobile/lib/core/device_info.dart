import 'dart:io';
import 'package:flutter/services.dart';

/// What the phone knows about itself, from the native side. Reported to the laptop as telemetry only; none of it is
/// ever used to allow or deny access (an SSID would need a location permission and proves nothing).
class DeviceSnapshot {
  final String model;
  final String osVersion;
  final String localIp;
  final String interfaceName;
  final bool onWifi;
  final int batteryPct;
  final bool charging;
  final double tempC;
  final int? wifiRssi;
  const DeviceSnapshot({
    this.model = 'Android phone',
    this.osVersion = 'Android',
    this.localIp = '',
    this.interfaceName = '',
    this.onWifi = true,
    this.batteryPct = 100,
    this.charging = false,
    this.tempC = 34,
    this.wifiRssi,
  });
}

class DeviceInfoService {
  static const MethodChannel _channel = MethodChannel('safespace/network');

  static Future<DeviceSnapshot> read() async {
    try {
      final m = await _channel.invokeMapMethod<String, dynamic>('getDeviceInfo');
      if (m != null) {
        return DeviceSnapshot(
          model: (m['device_model'] as String?) ?? 'Android phone',
          osVersion: (m['os_version'] as String?) ?? 'Android',
          localIp: (m['local_ip'] as String?) ?? '',
          interfaceName: (m['interface_name'] as String?) ?? '',
          onWifi: m['on_wifi'] != false,
          batteryPct: (m['battery_pct'] as num?)?.toInt() ?? 100,
          charging: m['is_charging'] == true,
          tempC: (m['temp_c'] as num?)?.toDouble() ?? 34,
          wifiRssi: (m['wifi_rssi'] as num?)?.toInt(),
        );
      }
    } catch (_) {
      // fall through to what dart:io can see
    }
    try {
      for (final i in await NetworkInterface.list(type: InternetAddressType.IPv4, includeLoopback: false)) {
        if (i.addresses.isNotEmpty) return DeviceSnapshot(localIp: i.addresses.first.address, interfaceName: i.name);
      }
    } catch (_) {}
    return const DeviceSnapshot();
  }
}
