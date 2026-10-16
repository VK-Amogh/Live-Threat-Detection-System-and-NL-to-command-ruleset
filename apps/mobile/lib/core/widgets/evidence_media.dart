import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import '../auth_store.dart';
import '../theme/tokens.dart';

class EvidenceMedia extends StatefulWidget {
  final String url;
  final bool video;
  final int offsetMs;
  const EvidenceMedia({super.key, required this.url, this.video = false, this.offsetMs = 0});
  @override
  State<EvidenceMedia> createState() => _EvidenceMediaState();
}
class _EvidenceMediaState extends State<EvidenceMedia> {
  VideoPlayerController? controller;
  String? fullUrl;
  Map<String,String> headers = {};
  String? error;
  @override
  void initState() { super.initState(); load(); }
  @override
  void didUpdateWidget(covariant EvidenceMedia oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url || oldWidget.video != widget.video || oldWidget.offsetMs != widget.offsetMs) {
      controller?.dispose();
      controller = null;
      fullUrl = null;
      error = null;
      load();
    }
  }
  Future<void> load() async {
    try {
      final store = AuthStore(); final base = await store.getApiBaseUrl(); final token = await store.getDeviceToken();
      headers = {'Authorization': 'Bearer $token'};
      final resolved = Uri.parse(base).resolve(widget.url);
      if (resolved.origin != Uri.parse(base).origin) throw const FormatException('Media must be served by your SafeSpace server.');
      fullUrl = resolved.toString();
      if (widget.video) {
        final c = VideoPlayerController.networkUrl(resolved, httpHeaders: headers);
        controller = c;
        await c.initialize();
        await c.seekTo(Duration(milliseconds: widget.offsetMs));
      }
      if (mounted) setState(() {});
    } catch (_) { if (mounted) setState(() => error = 'Evidence could not be loaded. Check your connection.'); }
  }
  @override
  void dispose() { controller?.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    if (error != null) return Padding(padding: const EdgeInsets.all(AppSpacing.lg), child: Text(error!, style: AppTypography.support));
    if (fullUrl == null || (widget.video && controller?.value.isInitialized != true)) return const SizedBox(height: 200, child: Center(child: Text('Loading evidence…')));
    if (!widget.video) return Image.network(fullUrl!, headers: headers, fit: BoxFit.contain, errorBuilder: (_, __, ___) => const Text('Image unavailable'));
    final c = controller!;
    return Column(mainAxisSize: MainAxisSize.min, children: [
      AspectRatio(aspectRatio: c.value.aspectRatio, child: VideoPlayer(c)),
      VideoProgressIndicator(c, allowScrubbing: true, colors: const VideoProgressColors(playedColor: AppColors.foreground, bufferedColor: AppColors.foregroundSecondary, backgroundColor: AppColors.surface)),
      TextButton(onPressed: () { setState(() { c.value.isPlaying ? c.pause() : c.play(); }); }, child: Text(c.value.isPlaying ? 'Pause recording' : 'Play recording', style: AppTypography.body)),
    ]);
  }
}
