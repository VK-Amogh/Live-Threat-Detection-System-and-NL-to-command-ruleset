import 'package:flutter/material.dart';
import 'app.dart';
import 'core/api_client.dart';
import 'core/auth_store.dart';
import 'services/notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Local Notifications
  final notificationService = NotificationService();
  await notificationService.initialize();

  // Initialize Core Services
  final authStore = AuthStore();
  final apiClient = ApiClient(authStore);

  runApp(
    SafeSpaceApp(
      authStore: authStore,
      apiClient: apiClient,
      notificationService: notificationService,
    ),
  );
}
