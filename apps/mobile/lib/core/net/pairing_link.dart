/// `safespace://pair?c=<code>&r=<control|camera>&s=<server id>&u=<url>&u=<url>&p=<pin>` — what the dashboard shows as a
/// QR code. Scanning it with the phone's camera app opens SafeSpace, which then knows the code, the role, every
/// address to try and the TLS key to trust, with nothing typed.
class PairingLink {
  final String code;
  final String role;
  final String serverId;
  final List<String> urls;
  final List<String> pins;

  const PairingLink({required this.code, required this.role, required this.serverId, required this.urls, required this.pins});

  bool get isCamera => role == 'camera';

  /// Accepts a full link, or a bare pairing code (which then relies on the addresses the app already knows).
  static PairingLink? parse(String? text, {String defaultServerId = ''}) {
    final raw = text?.trim() ?? '';
    if (raw.isEmpty) return null;
    final uri = Uri.tryParse(raw);
    if (uri != null && uri.scheme == 'safespace' && uri.host == 'pair') {
      final code = uri.queryParameters['c']?.toUpperCase() ?? '';
      if (code.length < 4) return null;
      return PairingLink(
        code: code,
        role: uri.queryParameters['r'] == 'camera' ? 'camera' : 'control',
        serverId: uri.queryParameters['s'] ?? defaultServerId,
        urls: (uri.queryParametersAll['u'] ?? const []).where((u) => u.startsWith('http')).map((u) => u.replaceFirst(RegExp(r'/+$'), '')).toList(),
        pins: uri.queryParametersAll['p'] ?? const [],
      );
    }
    if (RegExp(r'^[A-Za-z0-9]{4,32}$').hasMatch(raw)) {
      return PairingLink(code: raw.toUpperCase(), role: 'control', serverId: defaultServerId, urls: const [], pins: const []);
    }
    return null;
  }
}
