import 'dart:typed_data';
import 'package:flutter/services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import '../core/auth_store.dart';
import '../core/net/route_manager.dart';
import '../data/generated/models.dart';

class NotificationService {
  static const _alertsChannel = MethodChannel('safespace/alerts');
  final FlutterLocalNotificationsPlugin _notifications =
      FlutterLocalNotificationsPlugin();

  Future<void> initialize() async {
    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidSettings);
    await _notifications.initialize(initSettings);

    final androidPlatform =
        _notifications.resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    await androidPlatform?.requestNotificationsPermission();
  }

  Future<void> startAlertMonitor(
      AuthStore authStore, RouteManager routes) async {
    if (await authStore.getScope() != 'admin') return;
    final token = await authStore.getDeviceToken();
    if (token == null || token.isEmpty) return;
    final urls = <String>{
      if (routes.active?.ok == true) routes.active!.route.url,
      await authStore.getApiBaseUrl(),
      ...routes.known.map((route) => route.url),
    }.toList();
    await _alertsChannel
        .invokeMethod<void>('start', {'token': token, 'urls': urls});
  }

  Future<void> stopAlertMonitor() => _alertsChannel.invokeMethod<void>('stop');

  Future<void> showTestAlert() async {
    final androidPlatform =
        _notifications.resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    await androidPlatform?.requestNotificationsPermission();
    await _notifications.show(
      42,
      'SafeSpace test alert',
      'Notifications are enabled on this phone.',
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'safespace_native_alerts',
          'Security alerts',
          channelDescription: 'New SafeSpace rule and threat alerts',
          importance: Importance.high,
          priority: Priority.high,
        ),
      ),
    );
  }

  Future<void> showThreatAlert(EventOut event) async {
    final isCritical = event.severity == Severity.CRITICAL;
    final isRule = event.category.key == 'RULE_ALERT';

    final androidDetails = AndroidNotificationDetails(
      'safespace_threats',
      'Threat Detections',
      channelDescription:
          'Real-time security threat and weapon detection alerts',
      importance: isCritical ? Importance.max : Importance.high,
      priority: isCritical ? Priority.max : Priority.high,
      vibrationPattern: Int64List.fromList([0, 250, 250, 250]),
      enableLights: true,
    );

    final details = NotificationDetails(android: androidDetails);

    await _notifications.show(
      event.id.hashCode,
      isRule
          ? 'SafeSpace rule: ${event.category.label}'
          : '⚠️ ${event.severity.name} THREAT: ${event.category.label}',
      isRule
          ? 'Rule triggered on ${event.camera.name}'
          : '${event.category.label} detected on ${event.camera.name}',
      details,
    );
  }
}
