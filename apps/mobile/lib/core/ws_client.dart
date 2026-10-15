import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'api_client.dart';
import 'auth_store.dart';
import '../data/generated/models.dart';

typedef EventCallback = void Function(EventOut event, bool isUpdate);

class WebSocketService {
  final ApiClient _apiClient;
  final AuthStore _authStore;
  final EventCallback onEventReceived;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;
  bool _isDisposed = false;

  WebSocketService({
    required ApiClient apiClient,
    required AuthStore authStore,
    required this.onEventReceived,
  })  : _apiClient = apiClient,
        _authStore = authStore;

  Future<void> connect() async {
    if (_isDisposed) return;

    try {
      final isPaired = await _authStore.isPaired();
      if (!isPaired) return;

      // 1. Fetch short-lived ticket
      final response = await _apiClient.dio.post('/api/v1/ws-tickets');
      final ticket = response.data['ticket'] as String;

      // 2. Format WebSocket URL
      final baseUrl = await _authStore.getApiBaseUrl();
      final uri = Uri.parse(baseUrl);
      final wsScheme = uri.scheme == 'https' ? 'wss' : 'ws';
      final wsUri = Uri(
        scheme: wsScheme,
        host: uri.host,
        port: uri.port,
        path: '/api/v1/ws',
        queryParameters: {'ticket': ticket},
      );

      _channel = WebSocketChannel.connect(wsUri);
      await _channel!.ready;
      debugPrint('[WS] Connected to SafeSpace WebSocket at $wsUri');

      _subscription = _channel!.stream.listen(
        _handleMessage,
        onError: (err) {
          debugPrint('[WS] Error: $err');
          _scheduleReconnect();
        },
        onDone: () {
          debugPrint('[WS] Connection closed');
          _scheduleReconnect();
        },
      );
    } catch (e) {
      debugPrint('[WS] Connection failed: $e');
      _scheduleReconnect();
    }
  }

  void _handleMessage(dynamic message) {
    try {
      final data = jsonDecode(message.toString()) as Map<String, dynamic>;
      final type = data['type'] as String?;

      if (type == 'ping') {
        _channel?.sink.add(jsonEncode({'type': 'pong'}));
        return;
      }

      if (type == 'event.created' || type == 'event.updated') {
        final payload = data['data'] as Map<String, dynamic>?;
        if (payload != null && payload.containsKey('event')) {
          final event = EventOut.fromJson(payload['event'] as Map<String, dynamic>);
          onEventReceived(event, type == 'event.updated');
        }
      }
    } catch (e) {
      debugPrint('[WS] Message parsing error: $e');
    }
  }

  void _scheduleReconnect() {
    if (_isDisposed) return;
    _subscription?.cancel();
    _channel = null;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), connect);
  }

  void disconnect() {
    _isDisposed = true;
    _reconnectTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
  }
}
