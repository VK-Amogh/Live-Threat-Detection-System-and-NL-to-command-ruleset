import 'dart:async';
import 'package:camera/camera.dart';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/api_client.dart';
import '../../core/theme/tokens.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/evidence_media.dart';
import '../../data/repositories/events_repository.dart';
import '../incidents/incident_detail_screen.dart';

class AnalyzeScreen extends StatefulWidget {
  final ApiClient apiClient;
  final EventsRepository eventsRepository;
  const AnalyzeScreen({super.key, required this.apiClient, required this.eventsRepository});
  @override
  State<AnalyzeScreen> createState() => _AnalyzeScreenState();
}
class _AnalyzeScreenState extends State<AnalyzeScreen> with WidgetsBindingObserver {
  List<Map<String,dynamic>> sources = [];
  Map<String,dynamic>? selected;
  String? error;
  bool busy = false, live = false;
  CameraController? camera;
  Timer? poll;
  @override
  void initState() { super.initState(); WidgetsBinding.instance.addObserver(this); load(); poll = Timer.periodic(const Duration(seconds: 4), (_) => load()); }
  @override
  void dispose() { WidgetsBinding.instance.removeObserver(this); live = false; poll?.cancel(); camera?.dispose(); super.dispose(); }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) { if (state != AppLifecycleState.resumed && live) stopLive(); }
  Future<void> load() async {
    try { final response = await widget.apiClient.dio.get('/api/v1/sources'); if (!mounted) return; setState(() { sources = (response.data as List).map((s) => Map<String,dynamic>.from(s)).toList(); if (selected != null) { for (final s in sources) { if (s['id'] == selected!['id']) selected = s; } } }); } catch (_) { if (mounted) setState(() => error = 'Source history is unavailable. Check your server connection.'); }
  }
  Future<void> upload(String path, String name) async {
    if (mounted) setState(() { busy = true; error = null; });
    try {
      final data = FormData.fromMap({'file': await MultipartFile.fromFile(path, filename: name)});
      final response = await widget.apiClient.dio.post('/api/v1/sources', data: data, options: Options(contentType: 'multipart/form-data', sendTimeout: const Duration(minutes: 5)));
      if (mounted) setState(() => selected = Map<String,dynamic>.from(response.data));
      await load(); widget.eventsRepository.invalidate();
    } catch (e) { if (mounted) setState(() => error = 'Upload failed: ${e is DioException ? e.response?.data ?? e.message : e}'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> pick() async {
    final result = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ['jpg','jpeg','png','webp','mp4','webm','mov','avi','mkv']);
    if (result?.files.single.path != null) await upload(result!.files.single.path!, result.files.single.name);
  }
  Future<void> photo() async {
    final file = await ImagePicker().pickImage(source: ImageSource.camera, maxWidth: 1920, imageQuality: 90);
    if (file != null) await upload(file.path, file.name);
  }
  Future<void> startLive() async {
    try {
      final cameras = await availableCameras(); if (cameras.isEmpty) throw StateError('No camera is available');
      camera = CameraController(cameras.firstWhere((c) => c.lensDirection == CameraLensDirection.back, orElse: () => cameras.first), ResolutionPreset.medium, enableAudio: false);
      await camera!.initialize(); if (!mounted) return;
      setState(() { live = true; error = null; });
      while (live && mounted) {
        final c = camera!;
        await c.startVideoRecording();
        await Future<void>.delayed(const Duration(seconds: 5));
        if (!mounted || camera != c || !c.value.isInitialized) break;
        if (c.value.isRecordingVideo) {
          final file = await c.stopVideoRecording();
          await upload(file.path, 'Mobile-${DateTime.now().millisecondsSinceEpoch}.mp4');
        }
      }
    } catch (e) { if (mounted) setState(() { live = false; error = 'Camera unavailable: $e'; }); }
  }
  void stopLive() { setState(() => live = false); }
  @override
  Widget build(BuildContext context) => SafeArea(child: ListView(padding: const EdgeInsets.all(AppSpacing.lg), children: [
    Text('See what’s happening.', style: AppTypography.screenTitle), const SizedBox(height: AppSpacing.sm), Text('Uploads and live recordings use the same detector on your PC.', style: AppTypography.support), const SizedBox(height: AppSpacing.xl),
    Wrap(spacing: AppSpacing.md, runSpacing: AppSpacing.md, children: [AppButton(label: 'Upload media', onPressed: busy || live ? null : pick), AppButton.secondary(label: 'Take photo', onPressed: busy || live ? null : photo), AppButton.secondary(label: live ? 'Stop camera' : 'Live camera', onPressed: busy && !live ? null : () { live ? stopLive() : startLive(); })]),
    const SizedBox(height: AppSpacing.lg), if (live && camera?.value.isInitialized == true) AspectRatio(aspectRatio: camera!.value.aspectRatio, child: CameraPreview(camera!)),
    if (live) Text('Sending 5-second clips to your server. Recording pauses between uploads to keep the queue bounded.', style: AppTypography.caption),
    if (busy) Padding(padding: const EdgeInsets.all(AppSpacing.lg), child: Text('Uploading to your PC…', style: AppTypography.body)),
    if (error != null) Text(error!, style: AppTypography.body),
    if (selected != null) ...[const SizedBox(height: AppSpacing.xl), AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(selected!['filename'], style: AppTypography.cardHeading), Text(selected!['status'].toString().toLowerCase(), style: AppTypography.support),
      if (selected!['error'] != null) Text(selected!['error'], style: AppTypography.body),
      if (selected!['result'] != null) ...[const SizedBox(height: AppSpacing.md), Text((selected!['event_ids'] as List).isEmpty ? 'No supported threat detected.' : 'Detection needs review.', style: AppTypography.cardTitle), Text('${selected!['frames_analyzed']} frames · ${selected!['result']['inference_ms']} ms last inference', style: AppTypography.caption), if (selected!['media_url'] != null) EvidenceMedia(key: ValueKey(selected!['media_url']), url: selected!['media_url'], video: selected!['kind'] == 'video'), for (final id in selected!['event_ids']) TextButton(onPressed: () async { final event = await widget.eventsRepository.getEvent(id); if (context.mounted) Navigator.push(context, MaterialPageRoute(builder: (_) => IncidentDetailScreen(event: event, eventsRepository: widget.eventsRepository))); }, child: const Text('Review incident')), Text('No detection is not a guarantee of safety. Coverage is listed in System.', style: AppTypography.caption)],
    ]))],
    const SizedBox(height: AppSpacing.xl), Text('Source history', style: AppTypography.sectionHeading), if (sources.isEmpty) Text('No sources have been uploaded.', style: AppTypography.support),
    for (final s in sources) ListTile(contentPadding: EdgeInsets.zero, title: Text(s['filename'], style: AppTypography.cardTitle, maxLines: 1, overflow: TextOverflow.ellipsis), subtitle: Text('${s['status']} · ${(s['event_ids'] as List).length} incidents', style: AppTypography.caption), onTap: () => setState(() => selected = s)),
    const SizedBox(height: 104),
  ]));
}
