import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../auth_store.dart';
import '../config.dart';
import 'pinned_http.dart';
import 'spki.dart';

/// One address the laptop might be reachable at.
class ServerRoute {
  final String url; // base URL without a trailing slash
  final String source; // baked | discovery | link | server | manual | last
  const ServerRoute(this.url, this.source);

  bool get tls => url.startsWith('https://');
  String get host => Uri.tryParse(url)?.host ?? url;

  @override
  bool operator ==(Object other) => other is ServerRoute && other.url == url;
  @override
  int get hashCode => url.hashCode;
}

/// The result of asking one address "are you my laptop?".
class RouteStatus {
  final ServerRoute route;
  final bool reachable; // got an HTTP answer
  final bool verified; // and it proved it knows the shared secret
  final int? rttMs;
  final String? serverRoute; // loopback | trusted_lan | ibus_lan | tailnet | relay, as the SERVER classified this connection
  final String? routeLabel;
  final String? mode;
  final Map<String, dynamic> capabilities;
  final String? error; // plain-language reason, shown on the diagnostics sheet
  const RouteStatus(this.route,
      {this.reachable = false,
      this.verified = false,
      this.rttMs,
      this.serverRoute,
      this.routeLabel,
      this.mode,
      this.capabilities = const {},
      this.error});

  bool get ok => reachable && verified;
  bool get passwordLogin => capabilities['password_login'] == true;
  bool get enroll => capabilities['enroll'] == true;
  bool get reducedQuality => capabilities['ladder'] == 'reduced';
}

/// Finds, verifies and keeps the best route to the laptop, whatever network the phone is on.
///
/// * races every known address in parallel and keeps only those that prove they are the genuine server;
/// * stays on the current route unless it fails or another is clearly faster (no flapping between networks);
/// * re-resolves when the phone's own addresses change (Wi-Fi <-> mobile data, new network);
/// * learns new addresses from the server's HMAC-signed route list and from UDP discovery.
class RouteManager extends ChangeNotifier {
  RouteManager(this._store, {Dio? dio})
      : _dio = dio ??
            Dio(BaseOptions(
              connectTimeout: const Duration(milliseconds: 2500),
              receiveTimeout: const Duration(milliseconds: 2500),
              validateStatus: (_) => true,
              headers: {'Accept': 'application/json'},
            ));

  final AuthStore _store;
  final Dio _dio;
  final List<ServerRoute> _known = [];
  List<RouteStatus> _last = const [];
  RouteStatus? _active;
  Timer? _monitor;
  String _addressSignature = '';
  int _failures = 0;
  bool _resolving = false;

  RouteStatus? get active => _active;
  List<RouteStatus> get lastProbes => _last;
  List<ServerRoute> get known => List.unmodifiable(_known);
  bool get connected => _active?.ok == true;

  Future<void> init() async {
    await PinStore.load();
    final prefs = await SharedPreferences.getInstance();
    for (final url in AppConfig.bakedUrls) {
      _remember(ServerRoute(url, 'baked'));
    }
    for (final url in prefs.getStringList(AppConfig.keyKnownRoutes) ?? const []) {
      _remember(ServerRoute(url, 'last'));
    }
    final saved = prefs.getString(AppConfig.keyApiBaseUrl);
    if (saved != null && saved.isNotEmpty) _remember(ServerRoute(AppConfig.normalizeUrl(saved), 'last'));
  }

  void _remember(ServerRoute route) {
    if (!route.url.startsWith('http') || _known.contains(route)) return;
    _known.add(route);
  }

  /// Add addresses learned from a pairing link, discovery or the server itself, plus any TLS keys that came with them.
  Future<void> learn(Iterable<String> urls, {required String source, Iterable<String> pins = const []}) async {
    await PinStore.add(pins);
    for (final url in urls) {
      _remember(ServerRoute(AppConfig.normalizeUrl(url), source));
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(
        AppConfig.keyKnownRoutes, _known.where((r) => r.source != 'baked').map((r) => r.url).take(24).toList());
  }

  /// Start watching the active route and the phone's own addresses.
  void startMonitoring() {
    _monitor?.cancel();
    _monitor = Timer.periodic(const Duration(seconds: 5), (_) => _tick());
  }

  void stopMonitoring() => _monitor?.cancel();

  Future<void> _tick() async {
    if (_resolving) return;
    final signature = await _addresses();
    final networkChanged = _addressSignature.isNotEmpty && signature != _addressSignature;
    _addressSignature = signature;
    final current = _active;
    if (current == null || networkChanged) {
      await resolve();
      return;
    }
    try {
      final r = await _dio.get('${current.route.url}/api/v1/health/live');
      if (r.statusCode == 200) {
        _failures = 0;
        return;
      }
    } catch (_) {}
    if (++_failures >= 2) {
      _failures = 0;
      await resolve();
    }
  }

  Future<String> _addresses() async {
    try {
      final all = await NetworkInterface.list(type: InternetAddressType.IPv4, includeLoopback: false);
      return (all.expand((i) => i.addresses.map((a) => '${i.name}:${a.address}')).toList()..sort()).join(',');
    } catch (_) {
      return '';
    }
  }

  /// Probe every candidate and pick the best verified one.
  Future<RouteStatus?> resolve({bool discover = true}) async {
    if (_resolving) return _active;
    _resolving = true;
    try {
      if (discover) {
        final found = await discoverRoutes();
        if (found.isNotEmpty) await learn(found, source: 'discovery');
      }
      final results = await Future.wait(_known.map(probe));
      _last = results;
      final good = results.where((s) => s.ok).toList()..sort((a, b) => (a.rttMs ?? 9999).compareTo(b.rttMs ?? 9999));
      RouteStatus? best = good.isEmpty ? null : good.first;
      final current = _active;
      if (best != null && current != null) {
        final still = good.where((s) => s.route == current.route).toList();
        // Hysteresis: stay put unless the best route is clearly faster.
        if (still.isNotEmpty && (still.first.rttMs ?? 9999) <= (best.rttMs ?? 9999) * 1.4 + 30) best = still.first;
      }
      _active = best;
      _addressSignature = await _addresses();
      if (best != null) {
        await _store.setApiBaseUrl(best.route.url);
        await learn(await _adoptSignedRoutes(best), source: 'server');
      }
      notifyListeners();
      return best;
    } finally {
      _resolving = false;
    }
  }

  /// Ask one address who it is. Only an answer that carries the correct HMAC of our random nonce is accepted.
  Future<RouteStatus> probe(ServerRoute route) async {
    final nonce = base64Url.encode(List<int>.generate(12, (_) => Random.secure().nextInt(256)));
    final sw = Stopwatch()..start();
    try {
      final r = await _dio.get('${route.url}/api/v1/health/identity', queryParameters: {'nonce': nonce});
      sw.stop();
      final data = r.data is Map ? Map<String, dynamic>.from(r.data as Map) : <String, dynamic>{};
      if (r.statusCode != 200) {
        return RouteStatus(route,
            reachable: true, rttMs: sw.elapsedMilliseconds, error: (data['detail'] as String?) ?? 'The laptop refused this connection (HTTP ${r.statusCode}).');
      }
      final proofOk = data['server_id'] == AppConfig.serverId &&
          data['proof'] == hmacHex(AppConfig.cameraEnrollmentCode, 'id|${AppConfig.serverId}|$nonce');
      if (!proofOk) {
        return RouteStatus(route,
            reachable: true, rttMs: sw.elapsedMilliseconds, error: 'Something answered, but it is not your SafeSpace laptop.');
      }
      return RouteStatus(route,
          reachable: true,
          verified: true,
          rttMs: sw.elapsedMilliseconds,
          serverRoute: data['route'] as String?,
          routeLabel: data['route_label'] as String?,
          mode: data['mode'] as String?,
          capabilities: Map<String, dynamic>.from((data['route_capabilities'] as Map?) ?? const {}));
    } on DioException catch (e) {
      return RouteStatus(route, error: _explain(e, route));
    } catch (e) {
      return RouteStatus(route, error: 'Could not check ${route.url}: $e');
    }
  }

  String _explain(DioException e, ServerRoute route) {
    final inner = e.error;
    if (inner is HandshakeException || inner is TlsException) {
      return 'The laptop\'s encryption key does not match this app (re-pair with a fresh link from the dashboard).';
    }
    if (e.type == DioExceptionType.connectionTimeout || e.type == DioExceptionType.receiveTimeout) {
      return 'No answer from ${route.host}. If this Wi-Fi blocks devices from reaching each other (common on public or guest Wi-Fi), '
          'use your own hotspot, Tailscale or the relay.';
    }
    if (inner is SocketException) return 'Cannot reach ${route.host} from this network.';
    return 'Cannot reach ${route.url}.';
  }

  /// If the server's signed route list verifies, trust the addresses and TLS keys in it.
  Future<List<String>> _adoptSignedRoutes(RouteStatus via) async {
    try {
      final r = await _dio.get('${via.route.url}/api/v1/health/identity');
      final data = Map<String, dynamic>.from(r.data as Map);
      final text = data['routes_json'] as String?;
      if (text == null || data['routes_sig'] != hmacHex(AppConfig.cameraEnrollmentCode, 'routes|$text')) return const [];
      final doc = jsonDecode(text) as Map<String, dynamic>;
      if (doc['server_id'] != AppConfig.serverId) return const [];
      await PinStore.add(((doc['pins'] as List?) ?? const []).cast<String>());
      return ((doc['routes'] as List?) ?? const []).map((e) => (e as Map)['url'] as String).toList();
    } catch (_) {
      return const [];
    }
  }

  /// UDP query so a phone finds the laptop again after DHCP changed its address. On open Wi-Fi the query carries an
  /// HMAC proof, so the laptop answers only devices that hold the shared secret.
  Future<List<String>> discoverRoutes({Duration wait = const Duration(milliseconds: 900)}) async {
    RawDatagramSocket? socket;
    try {
      socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
      socket.broadcastEnabled = true;
      final ts = DateTime.now().millisecondsSinceEpoch ~/ 1000;
      final query = utf8.encode(jsonEncode({
        'op': 'discover',
        'app': 'safespace',
        'v': 1,
        'server_id': AppConfig.serverId,
        'ts': ts,
        'proof': hmacHex(AppConfig.cameraEnrollmentCode, 'discover|${AppConfig.serverId}|$ts'),
      }));
      final targets = <String>{'255.255.255.255'};
      for (final iface in await NetworkInterface.list(type: InternetAddressType.IPv4, includeLoopback: false)) {
        for (final a in iface.addresses) {
          final p = a.address.split('.');
          targets..add('${p[0]}.${p[1]}.${p[2]}.255')..add('${p[0]}.${p[1]}.255.255');
        }
      }
      for (final route in _known) {
        targets.add(route.host); // unicast to the address we last knew
      }
      for (final target in targets) {
        try {
          final addr = InternetAddress.tryParse(target);
          if (addr != null) {
            socket.send(query, addr, AppConfig.discoveryPort);
          }
        } catch (_) {}
      }
      final urls = <String>[];
      final done = Completer<void>();
      final sub = socket.listen((event) {
        if (event != RawSocketEvent.read) return;
        final dg = socket?.receive();
        if (dg == null) return;
        try {
          final map = jsonDecode(utf8.decode(dg.data)) as Map<String, dynamic>;
          final text = map['routes_json'] as String?;
          if (map['op'] != 'announce' || text == null) return;
          if (map['routes_sig'] != hmacHex(AppConfig.cameraEnrollmentCode, 'routes|$text')) return;
          final doc = jsonDecode(text) as Map<String, dynamic>;
          if (doc['server_id'] != AppConfig.serverId) return;
          urls.addAll(((doc['routes'] as List?) ?? const []).map((e) => (e as Map)['url'] as String));
          PinStore.add(((doc['pins'] as List?) ?? const []).cast<String>());
        } catch (_) {}
      });
      Timer(wait, () {
        if (!done.isCompleted) done.complete();
      });
      await done.future;
      await sub.cancel();
      return urls;
    } catch (_) {
      return const [];
    } finally {
      socket?.close();
    }
  }

  @override
  void dispose() {
    _monitor?.cancel();
    super.dispose();
  }
}
