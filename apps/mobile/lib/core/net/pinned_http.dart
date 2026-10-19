import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config.dart';
import 'spki.dart';

/// The TLS keys this phone trusts: the ones baked into the APK plus any delivered out of band by a pairing link
/// or by the server's HMAC-signed route list. A key is never learned from an unauthenticated connection.
class PinStore {
  static final Set<String> _pins = {...AppConfig.bakedPins};

  static Set<String> get pins => Set.unmodifiable(_pins);

  static Future<void> load() async {
    final saved = (await SharedPreferences.getInstance()).getStringList(AppConfig.keyPins) ?? const [];
    _pins.addAll(saved);
  }

  static Future<void> add(Iterable<String> pins) async {
    final fresh = pins.where((p) => p.isNotEmpty && !_pins.contains(p)).toList();
    if (fresh.isEmpty) return;
    _pins.addAll(fresh);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(AppConfig.keyPins, _pins.difference(AppConfig.bakedPins.toSet()).toList());
  }

  @visibleForTesting
  static void resetForTest(Iterable<String> pins) {
    _pins
      ..clear()
      ..addAll(pins);
  }
}

/// Installed once (`HttpOverrides.global`) so every dart:io client — Dio, Image.network, WebSockets — accepts the
/// server's private-CA certificate if, and only if, its public key matches a pin. Hostname is deliberately not
/// compared: the key is the identity, and the laptop's address changes with DHCP.
class PinnedHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    final client = super.createHttpClient(context);
    client.connectionTimeout = const Duration(seconds: 6);
    client.badCertificateCallback = (X509Certificate cert, String host, int port) {
      try {
        return PinStore.pins.contains(pinOfDer(cert.der));
      } catch (_) {
        return false;
      }
    };
    return client;
  }
}
