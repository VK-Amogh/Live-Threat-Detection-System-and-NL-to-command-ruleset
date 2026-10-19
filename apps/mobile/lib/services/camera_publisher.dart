import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:camera/camera.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import '../core/auth_store.dart';
import '../core/device_info.dart';
import '../core/net/route_manager.dart';

enum PublisherState { idle, starting, live, reconnecting }

/// Streams the phone's camera to the laptop as a CCTV feed.
///
/// * frames come from the camera's image stream (not takePicture, which is slow and plays a shutter sound),
///   are rotated upright and JPEG-encoded natively, and are sent as SSF1 packets over one WebSocket;
/// * at most two frames are ever in flight: a slow network drops frames on the phone instead of building a backlog,
///   so the picture stays live;
/// * the laptop steers quality (fps, JPEG quality) through its acknowledgements, and can send commands
///   (torch, flip lens, stealth, full-resolution still);
/// * if the connection drops, it reconnects (re-finding the laptop on whatever network it is now on) and carries on.
class CameraPublisher extends ChangeNotifier {
  CameraPublisher({required this.store, required this.routes, this.onCommand});

  static const _jpeg = MethodChannel('safespace/jpeg');
  static const _screen = MethodChannel('safespace/screen');
  static const _rotations = {
    DeviceOrientation.portraitUp: 0,
    DeviceOrientation.landscapeLeft: 90,
    DeviceOrientation.portraitDown: 180,
    DeviceOrientation.landscapeRight: 270,
  };

  final AuthStore store;
  final RouteManager routes;

  /// Commands the laptop sends that the screen must act on (stealth, lens, torch).
  final void Function(String action, Map<String, dynamic> params)? onCommand;

  CameraController? controller;
  PublisherState state = PublisherState.idle;
  String? error;
  String? cameraId;
  String profile = 'normal';
  int targetFps = 10;
  int jpegQuality = 72;
  int sent = 0;
  int dropped = 0;
  int viewers = 0;
  double fpsOut = 0;
  int? lastRttMs;
  String? lastSnapshotNote;

  WebSocket? _ws;
  bool _running = false;
  bool _encoding = false;
  int _inFlight = 0;
  int _seq = 0;
  DateTime _lastSent = DateTime.fromMillisecondsSinceEpoch(0);
  DateTime _lastAck = DateTime.now();
  DateTime _windowStart = DateTime.now();
  int _windowCount = 0;
  bool _nextFrameIsFull = false;
  Timer? _telemetry;
  Timer? _watchdog;
  final Map<int, DateTime> _sentAt = {};
  bool torchOn = false;
  bool stealth = false;

  bool get live => state == PublisherState.live;

  bool _disposed = false;

  void _set(PublisherState s, {String? err}) {
    state = s;
    error = err;
    if (!_disposed) notifyListeners();
  }

  Future<void> start(CameraDescription camera) async {
    if (_running) return;
    _set(PublisherState.starting);
    try {
      cameraId = await store.getCameraId() ?? await _lookUpCameraId();
      if (cameraId == null) throw StateError('This phone is not registered as a camera yet. Pair it again.');
      final c = CameraController(camera, ResolutionPreset.high, enableAudio: false, imageFormatGroup: ImageFormatGroup.nv21);
      controller = c;
      await c.initialize();
      sent = dropped = 0;
      _inFlight = 0;
      _running = true;
      await _connect();
      await c.startImageStream(_onImage);
      unawaited(_screen.invokeMethod('keepAwake', {'on': true}));
      _telemetry = Timer.periodic(const Duration(seconds: 10), (_) => _sendTelemetry());
      _watchdog = Timer.periodic(const Duration(seconds: 2), (_) => _checkHealth());
      _set(PublisherState.live);
    } catch (e) {
      await stop();
      _set(PublisherState.idle, err: 'Could not start the camera: $e');
    }
  }

  /// The laptop names a phone's camera `cam_` + the first 12 hex characters of SHA-256(installation id). Computing it here
  /// lets a phone that was paired as a control phone become a camera without pairing again.
  Future<String?> _lookUpCameraId() async {
    final id = await store.getInstallationId();
    return 'cam_${sha256.convert(utf8.encode(id)).toString().substring(0, 12)}';
  }

  Future<void> stop() async {
    _running = false;
    _telemetry?.cancel();
    _watchdog?.cancel();
    final c = controller;
    controller = null;
    try {
      if (c != null && c.value.isStreamingImages) await c.stopImageStream();
    } catch (_) {}
    try {
      await _ws?.close();
    } catch (_) {}
    _ws = null;
    try {
      await c?.dispose();
    } catch (_) {}
    unawaited(_screen.invokeMethod('keepAwake', {'on': false}));
    unawaited(_screen.invokeMethod('setBrightness', {'level': null}));
    _sentAt.clear();
    _set(PublisherState.idle, err: error);
  }

  // --- connection -----------------------------------------------------------------------------------------------

  Future<void> _connect() async {
    final base = await store.getApiBaseUrl();
    final token = await store.getDeviceToken();
    final wsBase = base.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://');
    final ws = await WebSocket.connect(
      '$wsBase/api/v1/cameras/${Uri.encodeComponent(cameraId!)}/publish',
      headers: {'Authorization': 'Bearer $token'}, // in a header, never in the URL
    ).timeout(const Duration(seconds: 5));
    ws.pingInterval = const Duration(seconds: 15);
    _ws = ws;
    _inFlight = 0;
    _lastAck = DateTime.now();
    ws.listen(_onMessage, onDone: () => _lost(ws), onError: (_) => _lost(ws), cancelOnError: true);
  }

  bool _reconnecting = false;

  Future<void> _lost(WebSocket ws) async {
    if (!_running || _ws != ws || _reconnecting) return;
    _reconnecting = true;
    _ws = null;
    _set(PublisherState.reconnecting, err: 'Connection lost. Reconnecting…');
    var delay = 1;
    while (_running) {
      await Future<void>.delayed(Duration(seconds: delay));
      if (!_running) break;
      try {
        await routes.resolve(discover: delay > 2); // the phone may have moved to another network
        await _connect();
        _reconnecting = false;
        _set(PublisherState.live);
        return;
      } catch (_) {
        delay = delay >= 8 ? 8 : delay * 2;
      }
    }
    _reconnecting = false;
  }

  void _checkHealth() {
    // Frames in flight but no acknowledgement for 4 s: the socket is half-dead.
    if (_running && _ws != null && _inFlight > 0 && DateTime.now().difference(_lastAck).inSeconds >= 4) {
      final ws = _ws!;
      _inFlight = 0;
      ws.close();
      unawaited(_lost(ws));
    }
  }

  // --- messages from the laptop -----------------------------------------------------------------------------------

  void _onMessage(dynamic data) {
    if (data is! String) return;
    Map<String, dynamic> msg;
    try {
      msg = jsonDecode(data) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    switch (msg['type']) {
      case 'ready':
        _applyLadder(msg);
      case 'ack':
        if (_inFlight > 0) _inFlight--;
        _lastAck = DateTime.now();
        viewers = (msg['viewer_count'] as num?)?.toInt() ?? viewers;
        final seq = (msg['seq'] as num?)?.toInt();
        final at = seq == null ? null : _sentAt.remove(seq);
        if (at != null) lastRttMs = DateTime.now().difference(at).inMilliseconds;
        _applyLadder(msg);
        notifyListeners();
      case 'telemetry_ack':
        viewers = (msg['viewer_count'] as num?)?.toInt() ?? viewers;
        _applyLadder(msg);
      case 'command':
        unawaited(_command((msg['action'] as String?) ?? '', Map<String, dynamic>.from((msg['params'] as Map?) ?? const {})));
      case 'error':
        error = msg['message'] as String?;
        notifyListeners();
    }
  }

  void _applyLadder(Map<String, dynamic> msg) {
    profile = (msg['profile'] as String?) ?? profile;
    final fps = (msg['fps'] as num?)?.toInt();
    final q = (msg['jpeg_quality'] as num?)?.toInt();
    if (fps != null && fps >= 1) targetFps = fps.clamp(1, 15);
    if (q != null && q >= 30) jpegQuality = q.clamp(40, 85);
  }

  Future<void> _command(String action, Map<String, dynamic> params) async {
    switch (action) {
      case 'toggle_torch':
        await setTorch(params['enabled'] as bool? ?? !torchOn);
      case 'take_full_snapshot':
        _nextFrameIsFull = true;
      case 'ping':
        _ws?.add(jsonEncode({'type': 'ping'}));
      default:
        onCommand?.call(action, params); // switch_lens, enter_stealth, exit_stealth, set_profile, ...
    }
  }

  Future<void> setTorch(bool on) async {
    final c = controller;
    if (c == null || !c.value.isInitialized) return;
    try {
      await c.setFlashMode(on ? FlashMode.torch : FlashMode.off);
      torchOn = on;
      notifyListeners();
    } catch (_) {
      error = 'The torch is not available on this lens.';
      notifyListeners();
    }
  }

  /// Computes the 16:9 landscape crop dimensions (even-aligned for YUV420) matching MainActivity.kt.
  static (int, int) crop16By9Dimensions(int w, int h) {
    final int cropW;
    final int cropH;
    if (w * 9 > h * 16) {
      cropW = ((h * 16) ~/ 9) & ~1;
      cropH = h & ~1;
    } else {
      cropW = w & ~1;
      cropH = ((w * 9) ~/ 16) & ~1;
    }
    return (cropW, cropH);
  }

  /// Ask the laptop to save the current frame (works for camera-scoped phones, which cannot call the admin API).
  void requestSnapshot() {
    _ws?.add(jsonEncode({'type': 'snapshot', 'kind': 'stream'}));
    lastSnapshotNote = '16:9 snapshot saved on the laptop';
    notifyListeners();
  }

  Future<void> _sendTelemetry() async {
    final ws = _ws;
    if (ws == null) return;
    final d = await DeviceInfoService.read();
    ws.add(jsonEncode({
      'type': 'telemetry',
      'battery_pct': d.batteryPct,
      'charging': d.charging,
      'temp_c': d.tempC,
      'wifi_rssi': d.wifiRssi,
      'dropped_frames': dropped,
      'stealth_mode': stealth,
      'torch_enabled': torchOn,
      'lens_facing': controller?.description.lensDirection == CameraLensDirection.front ? 'front' : 'back',
    }));
  }

  // --- frames -------------------------------------------------------------------------------------------------------

  void _onImage(CameraImage image) {
    if (!_running) return;
    final now = DateTime.now();
    if (now.difference(_lastSent).inMilliseconds < 1000 ~/ targetFps) return; // not due yet; not a drop
    final ws = _ws;
    if (ws == null || _encoding || _inFlight >= 2) {
      if (ws != null) dropped++; // a live view must never lag behind: skip the frame
      return;
    }
    _lastSent = now;
    _encoding = true;
    unawaited(_encodeAndSend(image, ws).whenComplete(() => _encoding = false));
  }

  int _rotation(CameraController c) {
    final sensor = c.description.sensorOrientation;
    final device = _rotations[c.value.deviceOrientation] ?? 0;
    return c.description.lensDirection == CameraLensDirection.front ? (sensor + device) % 360 : (sensor - device + 360) % 360;
  }

  Future<void> _encodeAndSend(CameraImage image, WebSocket ws) async {
    final c = controller;
    if (c == null) return;
    try {
      final w = image.width, h = image.height;
      final nv21 = _tightNv21(image);
      final rotation = _rotation(c);
      final fullFrame = _nextFrameIsFull;
      final jpeg = await _jpeg.invokeMethod<Uint8List>('nv21ToJpeg', {
        'nv21': nv21,
        'width': w,
        'height': h,
        'quality': fullFrame ? 88 : jpegQuality,
        'rotation': rotation,
      });
      if (jpeg == null || !_running || _ws != ws) return;
      final swap = rotation == 90 || rotation == 270;
      final (outW, outH) = crop16By9Dimensions(swap ? h : w, swap ? w : h);
      final seq = ++_seq;
      _sentAt[seq] = DateTime.now();
      if (_sentAt.length > 40) _sentAt.remove(_sentAt.keys.first);
      ws.add(_pack(jpeg, outW, outH, flags: fullFrame ? 1 : 0, seq: seq));
      if (fullFrame) _nextFrameIsFull = false;
      _inFlight++;
      sent++;
      _windowCount++;
      final span = DateTime.now().difference(_windowStart).inMilliseconds / 1000.0;
      if (span >= 2) {
        fpsOut = _windowCount / span;
        _windowCount = 0;
        _windowStart = DateTime.now();
        notifyListeners();
      }
    } catch (e) {
      error = 'Encoding failed: $e';
    }
  }

  /// The camera plugin may pad each row; the encoder needs the rows packed tightly (Y plane, then interleaved VU).
  Uint8List _tightNv21(CameraImage image) {
    final w = image.width, h = image.height;
    final plane = image.planes.first;
    if (image.planes.length == 1 && plane.bytesPerRow == w) return plane.bytes;
    final out = Uint8List(w * h * 3 ~/ 2);
    final stride = plane.bytesPerRow;
    var o = 0;
    for (var row = 0; row < h; row++) {
      out.setRange(o, o + w, plane.bytes, row * stride);
      o += w;
    }
    final chromaStart = stride * h;
    for (var row = 0; row < h ~/ 2; row++) {
      out.setRange(o, o + w, plane.bytes, chromaStart + row * stride);
      o += w;
    }
    return out;
  }

  /// SSF1: magic | flags u8 | orientation u8 | width u16 | height u16 | seq u32 | captured_ms u64 (big-endian), then the JPEG.
  Uint8List _pack(Uint8List jpeg, int width, int height, {int flags = 0, int? seq}) {
    final out = Uint8List(22 + jpeg.length);
    final bd = ByteData.view(out.buffer);
    out.setRange(0, 4, const [0x53, 0x53, 0x46, 0x31]);
    out[4] = flags;
    out[5] = 0;
    bd.setUint16(6, width);
    bd.setUint16(8, height);
    bd.setUint32(10, seq ?? ++_seq);
    bd.setUint64(14, DateTime.now().millisecondsSinceEpoch);
    out.setRange(22, out.length, jpeg);
    return out;
  }

  @visibleForTesting
  Uint8List packForTest(Uint8List jpeg, int width, int height, {int flags = 0, int seq = 1}) => _pack(jpeg, width, height, flags: flags, seq: seq);

  @override
  void dispose() {
    _disposed = true;
    unawaited(stop());
    super.dispose();
  }
}
