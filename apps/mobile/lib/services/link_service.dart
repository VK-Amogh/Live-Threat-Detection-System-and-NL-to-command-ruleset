import 'dart:async';
import 'package:flutter/services.dart';

/// Delivers `safespace://pair?...` links to the app: the one that launched it, and any opened while it runs
/// (scanning the dashboard's QR code with the phone's camera app opens SafeSpace with the link).
class LinkService {
  static const MethodChannel _channel = MethodChannel('safespace/links');
  final StreamController<String> _links = StreamController<String>.broadcast();
  String? _pending;

  Stream<String> get stream => _links.stream;

  /// A link that arrived before anything was listening (cold start).
  String? takePending() {
    final link = _pending;
    _pending = null;
    return link;
  }

  Future<void> init() async {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'onLink' && call.arguments is String) _deliver(call.arguments as String);
    });
    try {
      final initial = await _channel.invokeMethod<String>('getInitialLink');
      if (initial != null && initial.isNotEmpty) _pending = initial;
    } catch (_) {}
  }

  void _deliver(String link) {
    if (_links.hasListener) {
      _links.add(link);
    } else {
      _pending = link;
    }
  }

  void dispose() => _links.close();
}
