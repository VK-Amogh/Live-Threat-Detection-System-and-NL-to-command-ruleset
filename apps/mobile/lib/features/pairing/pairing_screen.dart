import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/config.dart';
import '../../core/net/pairing_link.dart';
import '../../core/net/route_manager.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_card.dart';
import '../../services/link_service.dart';
import '../../services/session_service.dart';

/// First screen: find the laptop, then join it. Joining is one tap (the built-in admin accounts), or nothing at all
/// (a pairing link from the dashboard's QR code). Which of these a network allows is decided by the laptop.
class PairingScreen extends StatefulWidget {
  final SessionService session;
  final RouteManager routes;
  final LinkService links;
  final VoidCallback onPaired;

  const PairingScreen({
    super.key,
    required this.session,
    required this.routes,
    required this.links,
    required this.onPaired,
  });

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final _address = TextEditingController();
  final _email = TextEditingController(
      text: AppConfig.accountTiles.isEmpty
          ? ''
          : AppConfig.accountTiles.first.key);
  final _password = TextEditingController();
  final _code = TextEditingController();
  StreamSubscription<String>? _linkSub;
  bool _busy = false;
  bool _searching = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    widget.routes.addListener(_onRoutes);
    _linkSub = widget.links.stream.listen(_openLink);
    final pending = widget.links.takePending();
    if (pending != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _openLink(pending));
    } else {
      _find();
    }
  }

  @override
  void dispose() {
    widget.routes.removeListener(_onRoutes);
    _linkSub?.cancel();
    for (final c in [_address, _email, _password, _code]) {
      c.dispose();
    }
    super.dispose();
  }

  void _onRoutes() {
    if (mounted) setState(() {});
  }

  Future<void> _find() async {
    setState(() {
      _searching = true;
      _error = null;
    });
    await widget.routes.resolve();
    if (mounted) setState(() => _searching = false);
  }

  Future<void> _run(Future<SessionResult> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
      if (mounted) widget.onPaired();
    } catch (e) {
      if (mounted) setState(() => _error = SessionService.describe(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openLink(String raw) async {
    final link = PairingLink.parse(raw, defaultServerId: AppConfig.serverId);
    if (link == null) {
      if (mounted) {
        setState(
            () => _error = 'That is not a SafeSpace pairing link or code.');
      }
      return;
    }
    await _run(() => widget.session.redeem(link));
  }

  Future<void> _addAddress() async {
    final text = _address.text.trim();
    if (text.isEmpty) return;
    final url = text.startsWith('http') ? text : 'http://$text';
    await widget.routes.learn([url], source: 'manual');
    _address.clear();
    await _find();
  }

  @override
  Widget build(BuildContext context) {
    final active = widget.routes.active;
    final connected = active?.ok == true;
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Connect your phone', style: AppTypography.screenTitle),
                  const SizedBox(height: AppSpacing.lg),
                  _connectionCard(active, connected),
                  const SizedBox(height: AppSpacing.lg),
                  if (connected && active!.passwordLogin)
                    ..._quickJoin(active)
                  else if (connected)
                    _linkOnly(active!),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.lg),
                      child: Text(_error!, style: AppTypography.body),
                    ),
                  _pairWithCode(),
                  const SizedBox(height: AppSpacing.md),
                  Theme(
                    data: Theme.of(context)
                        .copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      tilePadding: EdgeInsets.zero,
                      title: Text('Advanced', style: AppTypography.support),
                      children: [
                        _field(_address, 'Laptop address',
                            hint: 'http://10.11.229.33:8000'),
                        AppButton.secondary(
                            label: 'Use this address',
                            onPressed: _busy ? null : _addAddress),
                        const SizedBox(height: AppSpacing.lg),
                        if (connected && active!.passwordLogin) ...[
                          _field(_email, 'Email'),
                          _field(_password, 'Password', secret: true),
                          AppButton.secondary(
                            label: 'Sign in with a password',
                            onPressed: _busy
                                ? null
                                : () => _run(() => widget.session.signIn(
                                    _email.text.trim(), _password.text)),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _connectionCard(RouteStatus? active, bool connected) {
    return AppCard(
      onTap: _showDetails,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(
              Icons.circle,
              size: 14,
              color:
                  connected ? const Color(0xFF38C878) : const Color(0xFFE65757),
            ),
            const Spacer(),
            Text('Details', style: AppTypography.caption),
          ]),
          const SizedBox(height: AppSpacing.md),
          Text(
              connected
                  ? (active!.routeLabel ?? 'Your laptop')
                  : 'Join your Nothing Phone hotspot',
              style: AppTypography.cardTitle),
          const SizedBox(height: AppSpacing.xs),
          Text(
            connected ? active!.route.url : (widget.session.explainNoRoute()),
            style: AppTypography.caption,
          ),
          if (!connected && !_searching) ...[
            const SizedBox(height: AppSpacing.md),
            AppButton.secondary(label: 'Try again', onPressed: _find),
          ],
        ],
      ),
    );
  }

  List<Widget> _quickJoin(RouteStatus active) => [
        Text('Sign in', style: AppTypography.caption),
        const SizedBox(height: AppSpacing.sm),
        Row(children: [
          for (final account in AppConfig.accountTiles) ...[
            Expanded(
              child: AppButton.secondary(
                label: account.value,
                onPressed: _busy
                    ? null
                    : () => _run(() => widget.session
                        .signIn(account.key, AppConfig.demoPassword)),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
          ],
        ]),
        if (active.enroll) ...[
          const SizedBox(height: AppSpacing.sm),
          AppButton.secondary(
              label: 'Use this phone as a camera',
              onPressed:
                  _busy ? null : () => _run(widget.session.enrollCamera)),
        ],
        const SizedBox(height: AppSpacing.lg),
      ];

  Widget _linkOnly(RouteStatus active) => Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.lg),
        child: AppCard(
          child: Text(
            '${active.routeLabel ?? 'This network'} needs a pairing link. On the laptop dashboard open System → Add a phone, '
            'then scan the QR code with this phone’s camera. SafeSpace opens and connects by itself.',
            style: AppTypography.support,
          ),
        ),
      );

  Widget _pairWithCode() => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Have a pairing link or code?', style: AppTypography.caption),
          const SizedBox(height: AppSpacing.sm),
          _field(_code, 'Pairing code or link', hint: '8B415FAC'),
          AppButton(
              label: 'Pair this phone',
              expand: true,
              isLoading: _busy,
              onPressed: _busy ? null : () => _openLink(_code.text)),
        ],
      );

  void _showDetails() {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius:
              BorderRadius.vertical(top: Radius.circular(AppRadii.dialog))),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Connection details', style: AppTypography.sectionHeading),
              const SizedBox(height: AppSpacing.md),
              if (widget.routes.lastProbes.isEmpty)
                Text('No address has been tried yet.',
                    style: AppTypography.support),
              for (final p in widget.routes.lastProbes)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.md),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(p.route.url,
                            style: AppTypography.body
                                .copyWith(fontWeight: FontWeight.w600)),
                        Text(
                          p.ok
                              ? 'Your laptop · ${p.rttMs} ms · ${p.routeLabel ?? ''}'
                              : (p.error ?? 'No answer'),
                          style: AppTypography.caption,
                        ),
                      ]),
                ),
              const SizedBox(height: AppSpacing.md),
              AppButton(
                label: 'Check again',
                expand: true,
                onPressed: () async {
                  Navigator.pop(ctx);
                  await _find();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _field(TextEditingController c, String label,
          {String? hint, bool secret = false}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.md),
        child: TextField(
          controller: c,
          obscureText: secret,
          autocorrect: false,
          enableSuggestions: false,
          style: AppTypography.body,
          decoration: InputDecoration(
            labelText: label,
            hintText: hint,
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppRadii.card)),
          ),
        ),
      );
}
