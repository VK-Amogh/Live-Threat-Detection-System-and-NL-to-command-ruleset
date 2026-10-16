import 'package:flutter/material.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_card.dart';
import '../../data/repositories/rules_repository.dart';

class RulesScreen extends StatefulWidget {
  final RulesRepository repository;
  const RulesScreen({super.key, required this.repository});

  @override
  State<RulesScreen> createState() => _RulesScreenState();
}

class _RulesScreenState extends State<RulesScreen> {
  final _text = TextEditingController();
  List<Map<String, dynamic>> _cameras = [];
  List<Map<String, dynamic>> _rules = [];
  String? _cameraId;
  Map<String, dynamic>? _draft;
  String? _error;
  bool _visual = false;
  bool _ack = false;
  bool _busy = false;

  @override
  void initState() { super.initState(); _load(); }

  @override
  void dispose() { _text.dispose(); super.dispose(); }

  Future<void> _load() async {
    try {
      final cameras = await widget.repository.cameras();
      final selected = cameras.any((camera) => camera['id'] == _cameraId)
          ? _cameraId : (cameras.isEmpty ? null : cameras.first['id'] as String);
      final rules = selected == null ? <Map<String, dynamic>>[] : await widget.repository.rules(selected);
      if (mounted) setState(() { _cameras = cameras; _cameraId = selected; _rules = rules; _error = null; });
    } catch (error) { if (mounted) setState(() => _error = '$error'); }
  }

  Future<void> _compile() async {
    if (_cameraId == null || _text.text.trim().isEmpty) return;
    setState(() { _busy = true; _error = null; _draft = null; });
    try {
      final draft = await widget.repository.compile(_cameraId!, _text.text.trim(), _visual);
      if (mounted) setState(() { _draft = draft; _ack = false; });
      await _load();
    } catch (error) { if (mounted) setState(() => _error = '$error'); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Future<void> _activate(Map<String, dynamic> record) async {
    final spec = Map<String, dynamic>.from(record['spec'] as Map);
    if (spec['support_level'] == 'EXPERIMENTAL' && !_ack) {
      setState(() => _error = 'Acknowledge the experimental limitation first.'); return;
    }
    setState(() { _busy = true; _error = null; });
    try {
      await widget.repository.activate(spec['rule_id'] as String, spec['version'] as int,
          record['readback_hash'] as String, _ack);
      if (mounted) setState(() => _draft = null);
      await _load();
    } catch (error) { if (mounted) setState(() => _error = '$error'); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Future<void> _disable(Map<String, dynamic> record) async {
    setState(() { _busy = true; _error = null; });
    try { await widget.repository.disable(record['id'] as String, record['version'] as int); await _load(); }
    catch (error) { if (mounted) setState(() => _error = '$error'); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Widget _ruleCard(Map<String, dynamic> record) {
    final spec = Map<String, dynamic>.from(record['spec'] as Map);
    final active = record['status'] == 'active';
    final canActivate = record['can_activate'] == true && record['readback_hash'] != null;
    return Padding(padding: const EdgeInsets.only(bottom: AppSpacing.md), child: AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${spec['name']}', style: AppTypography.cardHeading),
        const SizedBox(height: AppSpacing.xs),
        Text('${record['status']} · ${spec['support_level']} · version ${record['version']}', style: AppTypography.caption),
        const SizedBox(height: AppSpacing.sm),
        Text('${record['readback'] ?? record['text']}', style: AppTypography.body),
        if (spec['unsupported_reason'] != null) Text('${spec['unsupported_reason']}', style: AppTypography.support),
        if (!active && spec['support_level'] == 'EXPERIMENTAL')
          CheckboxListTile(value: _ack, onChanged: (value) => setState(() => _ack = value == true),
            title: Text('I understand this is experimental', style: AppTypography.support), contentPadding: EdgeInsets.zero),
        const SizedBox(height: AppSpacing.sm),
        if (active) AppButton.secondary(label: 'Disable', onPressed: _busy ? null : () => _disable(record))
        else if (canActivate) AppButton.secondary(label: 'Confirm and activate', onPressed: _busy ? null : () => _activate(record)),
      ]),
    ));
  }

  @override
  Widget build(BuildContext context) => Scaffold(backgroundColor: AppColors.background,
    body: SafeArea(bottom: false, child: RefreshIndicator(onRefresh: _load,
      child: ListView(padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, 100), children: [
        Text('Camera Rules', style: AppTypography.screenTitle),
        Text('Describe what to watch, then confirm the exact rule.', style: AppTypography.support),
        const SizedBox(height: AppSpacing.lg),
        if (_error != null) Text(_error!, style: AppTypography.body.copyWith(color: AppColors.foreground)),
        if (_cameras.isEmpty) Text('Add and start a server camera from the dashboard first.', style: AppTypography.body)
        else ...[
          DropdownButtonFormField<String>(value: _cameraId, dropdownColor: AppColors.surface,
            decoration: const InputDecoration(labelText: 'Camera'),
            items: _cameras.map((camera) => DropdownMenuItem<String>(value: camera['id'] as String,
              child: Text('${camera['name']}'))).toList(),
            onChanged: (value) { setState(() { _cameraId = value; _draft = null; }); _load(); }),
          const SizedBox(height: AppSpacing.md),
          TextField(controller: _text, maxLines: 3,
            decoration: const InputDecoration(labelText: 'Monitoring request',
              hintText: 'Alert when a person stays in the driveway for 3 seconds')),
          SwitchListTile(value: _visual, onChanged: (value) => setState(() => _visual = value),
            title: Text('Add a later visual summary', style: AppTypography.body), contentPadding: EdgeInsets.zero),
          AppButton(label: _busy ? 'Working…' : 'Compile rule', expand: true,
            onPressed: _busy ? null : _compile),
        ],
        if (_draft != null) ...[
          const SizedBox(height: AppSpacing.lg),
          Text('Readback', style: AppTypography.cardHeading),
          const SizedBox(height: AppSpacing.sm),
          _ruleCard({..._draft!, 'status': 'draft', 'text': _text.text,
            'version': (_draft!['spec'] as Map)['version']}),
          for (final problem in (_draft!['problems'] as List? ?? []))
            Text('$problem', style: AppTypography.support),
        ],
        const SizedBox(height: AppSpacing.xl),
        Text('Saved rules', style: AppTypography.cardHeading),
        const SizedBox(height: AppSpacing.md),
        if (_rules.isEmpty) Text('No rules saved for this camera.', style: AppTypography.support)
        else for (final rule in _rules) _ruleCard(rule),
      ]))));
}
