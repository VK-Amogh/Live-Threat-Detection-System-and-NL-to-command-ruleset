import 'dart:typed_data';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import '../data/generated/models.dart';

class NotificationService {
  final FlutterLocalNotificationsPlugin _notifications = FlutterLocalNotificationsPlugin();

  Future<void> initialize() async {
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidSettings);
    await _notifications.initialize(initSettings);

    final androidPlatform = _notifications.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await androidPlatform?.requestNotificationsPermission();
  }

  Future<void> showThreatAlert(EventOut event) async {
    final isCritical = event.severity == Severity.CRITICAL;

    final androidDetails = AndroidNotificationDetails(
      'safespace_threats',
      'Threat Detections',
      channelDescription: 'Real-time security threat and weapon detection alerts',
      importance: isCritical ? Importance.max : Importance.high,
      priority: isCritical ? Priority.max : Priority.high,
      vibrationPattern: Int64List.fromList([0, 250, 250, 250]),
      enableLights: true,
    );

    final details = NotificationDetails(android: androidDetails);

    await _notifications.show(
      event.id.hashCode,
      '⚠️ ${event.severity.name} THREAT: ${event.category.label}',
      event.summary ?? 'Detection on ${event.camera.name}',
      details,
    );
  }
}
