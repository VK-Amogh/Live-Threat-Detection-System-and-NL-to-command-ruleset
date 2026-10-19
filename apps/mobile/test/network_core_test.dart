import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/auth_store.dart';
import 'package:safespace_mobile/core/net/pairing_link.dart';
import 'package:safespace_mobile/core/net/route_manager.dart';
import 'package:safespace_mobile/core/net/spki.dart';
import 'package:safespace_mobile/services/camera_publisher.dart';

/// Reference values below were computed by the server (services/api/app/network_policy.py, tls.py) so these tests prove
/// the phone and the laptop agree byte for byte.
const secret = 'ss-enroll-np4a-7495-9f8e7d6c5b4a3210';

Uint8List pemToDer(String pem) =>
    base64.decode(pem.split('\n').map((l) => l.trim()).where((l) => l.isNotEmpty && !l.startsWith('-----')).join());

void main() {
  test('the TLS key pin matches the one the server computes (and openssl)', () {
    final der = pemToDer(File('test/fixtures/server.pem').readAsStringSync());
    expect(pinOfDer(der), '3BM5h70nVwnA4AuW0+DiTTksQgyyTNmWlgSHbjBdz6Q=');
  });

  test('HMAC proofs agree with the server', () {
    expect(hmacHex(secret, 'id|ss-7f3c2a|nonce-abc'), '512b13e200e6b12b06529c3a4e7a3c37c9c98de0e5cba389da2cb61c9dc472a8');
    expect(hmacHex(secret, 'discover|ss-7f3c2a|1760000000'), 'cee9251e0116c9b0a7f69cf385afd0e5c67c9dfa24ee682a1d87f7ad07028917');
    expect(hmacHex(secret, 'routes|{"a":1}'), '090d10275f6636fe120018c931e69cc99a68d6cc7765a939b7031690845bc07c');
  });

  test('SSF1 frames have the layout the server parses', () {
    final pub = _publisher();
    final jpeg = Uint8List.fromList([0xff, 0xd8, 1, 2, 3, 0xff, 0xd9]);
    final out = pub.packForTest(jpeg, 960, 540, flags: 1, seq: 7);
    final bd = ByteData.sublistView(out);
    expect(String.fromCharCodes(out.sublist(0, 4)), 'SSF1');
    expect(out[4], 1);
    expect(bd.getUint16(6), 960);
    expect(bd.getUint16(8), 540);
    expect(bd.getUint32(10), 7);
    expect(out.sublist(22), jpeg);
  });

  test('crop16By9Dimensions center-crops sensor resolutions to 16:9', () {
    expect(CameraPublisher.crop16By9Dimensions(1280, 720), (1280, 720));
    expect(CameraPublisher.crop16By9Dimensions(640, 480), (640, 360));
    expect(CameraPublisher.crop16By9Dimensions(720, 1280), (720, 404));
    expect(CameraPublisher.crop16By9Dimensions(1920, 1080), (1920, 1080));
  });

  group('pairing links', () {
    test('parse the link the dashboard QR code carries', () {
      final link = PairingLink.parse(
          'safespace://pair?c=8b415fac&r=camera&s=ss-7f3c2a&u=http%3A%2F%2F10.11.229.33%3A8000&u=https%3A%2F%2F10.11.229.33%3A8443&p=3BM5h70n%2BDi',
          defaultServerId: 'x')!;
      expect(link.code, '8B415FAC');
      expect(link.isCamera, isTrue);
      expect(link.serverId, 'ss-7f3c2a');
      expect(link.urls, ['http://10.11.229.33:8000', 'https://10.11.229.33:8443']);
      expect(link.pins, ['3BM5h70n+Di']);
    });
    test('accept a typed code, reject nonsense', () {
      expect(PairingLink.parse('ab12cd34')!.code, 'AB12CD34');
      expect(PairingLink.parse('ab12cd34')!.isCamera, isFalse);
      expect(PairingLink.parse('not a link!'), isNull);
      expect(PairingLink.parse(''), isNull);
    });
  });
}

CameraPublisher _publisher() {
  final store = AuthStore();
  return CameraPublisher(store: store, routes: RouteManager(store));
}
