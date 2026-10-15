import 'package:flutter/material.dart';
import '../../core/api_client.dart';
import '../../core/auth_store.dart';

class PairingScreen extends StatefulWidget {
  final AuthStore authStore;
  final ApiClient apiClient;
  final VoidCallback onPaired;

  const PairingScreen({
    super.key,
    required this.authStore,
    required this.apiClient,
    required this.onPaired,
  });

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final _urlController = TextEditingController();
  final _codeController = TextEditingController();
  final _deviceNameController = TextEditingController(text: 'Android Security Device');
  bool _isLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadCurrentUrl();
  }

  Future<void> _loadCurrentUrl() async {
    final url = await widget.authStore.getApiBaseUrl();
    _urlController.text = url;
  }

  Future<void> _submitPairing() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    final hostUrl = _urlController.text.trim();
    final code = _codeController.text.trim();
    final deviceName = _deviceNameController.text.trim();

    if (hostUrl.isEmpty || code.isEmpty) {
      setState(() {
        _error = 'Please provide both Host URL and Pairing Code.';
        _isLoading = false;
      });
      return;
    }

    try {
      await widget.authStore.setApiBaseUrl(hostUrl);

      final response = await widget.apiClient.dio.post(
        '/api/v1/auth/pair',
        data: {
          'code': code,
          'device_name': deviceName,
        },
      );

      final data = response.data as Map<String, dynamic>;
      final deviceId = data['device_id'] as String;
      final deviceToken = data['device_token'] as String;

      await widget.authStore.savePairingSession(
        deviceId: deviceId,
        deviceName: deviceName,
        deviceToken: deviceToken,
      );

      widget.onPaired();
    } catch (e) {
      setState(() {
        _error = 'Pairing failed: $e';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        title: const Text('Pair Device', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Connect to SafeSpace Host',
              style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              'Scan QR from the dashboard or enter the 10-minute code generated on your local PC.',
              style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 13, height: 1.4),
            ),
            const SizedBox(height: 24),
            TextField(
              controller: _urlController,
              style: const TextStyle(color: Colors.white),
              decoration: _inputDecoration('Host API URL (e.g. http://192.168.1.100:8000)'),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _codeController,
              style: const TextStyle(color: Colors.white, letterSpacing: 2, fontWeight: FontWeight.bold),
              decoration: _inputDecoration('Pairing Code (e.g. SAFE-9821)'),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _deviceNameController,
              style: const TextStyle(color: Colors.white),
              decoration: _inputDecoration('Device Name'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              Text(_error!, style: const TextStyle(color: Colors.redAccent, fontSize: 13)),
            ],
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: _isLoading ? null : _submitPairing,
                child: _isLoading
                    ? const CircularProgressIndicator(color: Colors.black)
                    : const Text(
                        'Pair Now',
                        style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 15),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  InputDecoration _inputDecoration(String label) {
    return InputDecoration(
      labelText: label,
      labelStyle: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13),
      filled: true,
      fillColor: const Color(0xFF1A1A1A),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Colors.white),
      ),
    );
  }
}
