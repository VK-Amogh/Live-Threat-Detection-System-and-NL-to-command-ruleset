import 'package:flutter/material.dart';
import '../../core/auth_store.dart';

class StatusScreen extends StatefulWidget {
  final AuthStore authStore;
  final VoidCallback onUnpaired;

  const StatusScreen({super.key, required this.authStore, required this.onUnpaired});

  @override
  State<StatusScreen> createState() => _StatusScreenState();
}

class _StatusScreenState extends State<StatusScreen> {
  String _hostUrl = '';
  bool _isPaired = false;

  @override
  void initState() {
    super.initState();
    _loadStatus();
  }

  Future<void> _loadStatus() async {
    final url = await widget.authStore.getApiBaseUrl();
    final paired = await widget.authStore.isPaired();
    setState(() {
      _hostUrl = url;
      _isPaired = paired;
    });
  }

  Future<void> _unpair() async {
    await widget.authStore.clearSession();
    widget.onUnpaired();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        title: const Text('System Status', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF1A1A1A),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white10),
              ),
              child: Column(
                children: [
                  _statusRow('LAN Host API', _hostUrl),
                  const Divider(color: Colors.white10),
                  _statusRow('Pairing Status', _isPaired ? 'PAIRED' : 'UNPAIRED',
                      statusColor: _isPaired ? Colors.greenAccent : Colors.orangeAccent),
                  const Divider(color: Colors.white10),
                  _statusRow('Supabase Cloud Sync', 'ACTIVE', statusColor: Colors.greenAccent),
                  const Divider(color: Colors.white10),
                  _statusRow('Project Ref', 'hvdqlslmjyskuctkqpyr'),
                ],
              ),
            ),
            const Spacer(),
            if (_isPaired)
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: Colors.redAccent),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: _unpair,
                  child: const Text('Unpair Device', style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold)),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _statusRow(String label, String value, {Color statusColor = Colors.white}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 13)),
          Text(value, style: TextStyle(color: statusColor, fontWeight: FontWeight.w600, fontSize: 13)),
        ],
      ),
    );
  }
}
