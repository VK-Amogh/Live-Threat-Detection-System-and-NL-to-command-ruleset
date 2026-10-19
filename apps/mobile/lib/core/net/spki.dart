import 'dart:convert';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';

/// Public-key pinning helpers.
///
/// The app trusts the server's TLS *key*, not its certificate: the laptop re-issues the certificate whenever its
/// address changes (iBus hands out new DHCP addresses) but keeps the key, so a paired phone never has to be
/// re-configured. The pin is base64(SHA-256(SubjectPublicKeyInfo)) — the same value `services/api/app/tls.py` prints.

class _Tlv {
  final int tag, start, length;
  const _Tlv(this.tag, this.start, this.length);
  int get end => start + length;
}

_Tlv _read(Uint8List b, int pos) {
  final tag = b[pos];
  var length = b[pos + 1];
  var start = pos + 2;
  if (length & 0x80 != 0) {
    final count = length & 0x7f;
    length = 0;
    for (var i = 0; i < count; i++) {
      length = (length << 8) | b[start + i];
    }
    start += count;
  }
  return _Tlv(tag, start, length);
}

/// The SubjectPublicKeyInfo element (DER) of an X.509 certificate (DER).
Uint8List spkiOf(Uint8List certDer) {
  var t = _read(certDer, 0); // Certificate ::= SEQUENCE
  t = _read(certDer, t.start); // tbsCertificate ::= SEQUENCE
  var pos = t.start;
  var e = _read(certDer, pos);
  if (e.tag == 0xA0) {
    // [0] version (optional)
    pos = e.end;
    e = _read(certDer, pos);
  }
  pos = e.end; // past serialNumber
  for (var i = 0; i < 4; i++) {
    // signature, issuer, validity, subject
    e = _read(certDer, pos);
    pos = e.end;
  }
  e = _read(certDer, pos); // subjectPublicKeyInfo
  return Uint8List.sublistView(certDer, pos, e.end);
}

String pinOfDer(Uint8List certDer) => base64.encode(sha256.convert(spkiOf(certDer)).bytes);

/// HMAC-SHA256 (hex) of a plain string. The server computes the same over plain strings so no JSON canonical form
/// has to be shared: `id|<server_id>|<nonce>`, `discover|<server_id>|<ts>`, `routes|<routes_json>`.
String hmacHex(String key, String message) =>
    Hmac(sha256, utf8.encode(key)).convert(utf8.encode(message)).toString();
