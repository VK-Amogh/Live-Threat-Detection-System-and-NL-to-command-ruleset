import 'package:flutter/material.dart';
import '../../data/generated/models.dart';
import '../../data/repositories/events_repository.dart';

class IncidentDetailScreen extends StatefulWidget {
  final EventOut event;
  final EventsRepository eventsRepository;

  const IncidentDetailScreen({
    super.key,
    required this.event,
    required this.eventsRepository,
  });

  @override
  State<IncidentDetailScreen> createState() => _IncidentDetailScreenState();
}

class _IncidentDetailScreenState extends State<IncidentDetailScreen> {
  late EventOut _currentEvent;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _currentEvent = widget.event;
  }

  Future<void> _handleDecision(HumanAction action) async {
    setState(() => _isSubmitting = true);
    try {
      final updated = action == HumanAction.CONFIRM
          ? await widget.eventsRepository.confirmEvent(_currentEvent.id)
          : await widget.eventsRepository.markFalsePositive(_currentEvent.id);

      setState(() {
        _currentEvent = updated;
        _isSubmitting = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              action == HumanAction.CONFIRM ? 'Incident Confirmed' : 'Marked as False Positive',
            ),
            backgroundColor: const Color(0xFF1A1A1A),
          ),
        );
      }
    } catch (e) {
      setState(() => _isSubmitting = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Action failed: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final media = _currentEvent.media;

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        iconTheme: const IconThemeData(color: Colors.white),
        title: Text(
          _currentEvent.category.label,
          style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Media Preview Container
            Container(
              height: 220,
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFF1A1A1A),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: media.isNotEmpty
                  ? ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Image.network(
                        media.first.url,
                        fit: BoxFit.cover,
                        errorBuilder: (ctx, err, stack) => const Center(
                          child: Icon(Icons.broken_image, color: Colors.white38, size: 48),
                        ),
                      ),
                    )
                  : const Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.videocam_outlined, color: Colors.white38, size: 48),
                          SizedBox(height: 8),
                          Text('Keyframe Processing', style: TextStyle(color: Colors.white38)),
                        ],
                      ),
                    ),
            ),
            const SizedBox(height: 20),

            // Metadata Card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF1A1A1A),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: Column(
                children: [
                  _infoRow('Status', _currentEvent.status.name),
                  const Divider(color: Colors.white10),
                  _infoRow('Severity', _currentEvent.severity.name),
                  const Divider(color: Colors.white10),
                  _infoRow('Camera', _currentEvent.camera.name),
                  const Divider(color: Colors.white10),
                  _infoRow('Peak Confidence', '${(_currentEvent.peakConfidence * 100).toStringAsFixed(1)}%'),
                  const Divider(color: Colors.white10),
                  _infoRow('First Seen', _currentEvent.firstSeenAt),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // Summary / Reasoning
            if (_currentEvent.summary != null) ...[
              const Text('VLM Assessment', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 16)),
              const SizedBox(height: 8),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFF1A1A1A),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white.withOpacity(0.08)),
                ),
                child: Text(
                  _currentEvent.summary!,
                  style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.4),
                ),
              ),
              const SizedBox(height: 24),
            ],

            // Verification Action Buttons
            if (_isSubmitting)
              const Center(child: CircularProgressIndicator(color: Colors.white))
            else
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: Colors.white24),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      onPressed: () => _handleDecision(HumanAction.MARK_FALSE_POSITIVE),
                      child: const Text('False Positive', style: TextStyle(color: Colors.white70)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFEF4444),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      onPressed: () => _handleDecision(HumanAction.CONFIRM),
                      child: const Text('Confirm Threat', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13)),
          Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500, fontSize: 13)),
        ],
      ),
    );
  }
}
