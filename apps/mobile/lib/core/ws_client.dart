import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
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
  Timer? _pollTimer;
  bool _isDisposed = false;
  bool _catchingUp = false;
  bool _catchAgain = false;
  int _lastSeq = 0;
  bool _initialSync = false;
  SharedPreferences? _prefs;
  String _cursorKey = 'safespace.changeSeq';

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
      _prefs ??= await SharedPreferences.getInstance();
      _cursorKey = 'safespace.changeSeq.${await _authStore.getDeviceId()}';
      _initialSync = !(_prefs?.containsKey(_cursorKey) ?? false);
      _lastSeq = _prefs?.getInt(_cursorKey) ?? 0;

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
      _pollTimer?.cancel();
      _pollTimer = Timer.periodic(const Duration(seconds: 5), (_) => _catchUp());
      await _catchUp();
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

      if (type == 'hello' && (data['data']?['head_seq'] as int? ?? 0) < _lastSeq) {
        _lastSeq = 0;
        _catchUp();
      }
      if (type == 'event.created' || type == 'event.updated') _catchUp();
    } catch (e) {
      debugPrint('[WS] Message parsing error: $e');
    }
  }

  Future<void> _catchUp() async {
    if (_isDisposed) return;
    if (_catchingUp) { _catchAgain = true; return; }
    _catchingUp = true;
    var failed = false;
    try {
      do {
        _catchAgain = false;
        final response = await _apiClient.dio.get('/api/v1/changes',
            queryParameters: {'after': _lastSeq, 'limit': 200});
        final page = ChangesResponse.fromJson(Map<String, dynamic>.from(response.data));
        if (page.headSeq < _lastSeq) { _lastSeq = 0; _catchAgain = true; continue; }
        for (final event in page.items) {
          if (event.changeSeq <= _lastSeq) continue;
          _lastSeq = event.changeSeq;
          onEventReceived(event, _initialSync || event.createdAt != event.updatedAt);
          await _prefs?.setInt(_cursorKey, _lastSeq);
        }
        if (page.hasMore) _catchAgain = true;
        if (!page.hasMore) {
          _initialSync = false;
          await _prefs?.setInt(_cursorKey, _lastSeq);
        }
      } while (_catchAgain && !_isDisposed);
    } catch (error) {
      failed = true;
      debugPrint('[WS] Change-feed catch-up failed: $error');
    } finally {
      _catchingUp = false;
      if (_catchAgain && !failed && !_isDisposed) _catchUp();
    }
  }

  void _scheduleReconnect() {
    if (_isDisposed) return;
    _subscription?.cancel();
    _pollTimer?.cancel();
    _channel = null;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), connect);
  }

  void disconnect() {
    _isDisposed = true;
    _reconnectTimer?.cancel();
    _pollTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
  }
}
