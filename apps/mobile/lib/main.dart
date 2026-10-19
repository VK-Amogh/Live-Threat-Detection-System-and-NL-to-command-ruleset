import 'dart:io';
import 'package:flutter/material.dart';
import 'app.dart';
import 'core/api_client.dart';
import 'core/auth_store.dart';
import 'core/net/pinned_http.dart';
import 'core/net/route_manager.dart';
import 'services/link_service.dart';
import 'services/notification_service.dart';
import 'services/session_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Every dart:io client (Dio, Image.network, WebSockets) trusts the laptop's private-CA certificate by public-key pin.
  HttpOverrides.global = PinnedHttpOverrides();

  final notificationService = NotificationService();
  await notificationService.initialize();

  final authStore = AuthStore();
  final apiClient = ApiClient(authStore);
  final routes = RouteManager(authStore);
  await routes.init(); // baked addresses, remembered addresses, trusted TLS keys
  final links = LinkService();
  await links.init(); // a safespace://pair link that launched the app

  runApp(
    SafeSpaceApp(
      authStore: authStore,
      apiClient: apiClient,
      notificationService: notificationService,
      routes: routes,
      links: links,
      session: SessionService(apiClient, authStore, routes),
    ),
  );
}
