import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:video_player/video_player.dart';
import '../auth_store.dart';
import '../theme/tokens.dart';
import 'app_capsule.dart';
import 'app_icon.dart';
import 'fade_scrim.dart';
import 'glass_surface.dart';
import 'press_scale.dart';

/// EvidenceMedia conforming to DESIGN.md §5.4 and strict 16:9 playback requirement.
class EvidenceMedia extends StatefulWidget {
  final String url;
  final bool video;
  final int offsetMs;
  final bool autoPlay;
  final BorderRadius? borderRadius;

  const EvidenceMedia({
    super.key,
    required this.url,
    this.video = false,
    this.offsetMs = 0,
    this.autoPlay = false,
    this.borderRadius,
  });

  @override
  State<EvidenceMedia> createState() => _EvidenceMediaState();
}

class _EvidenceMediaState extends State<EvidenceMedia> {
  VideoPlayerController? controller;
  String? fullUrl;
  Map<String, String> headers = {};
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void didUpdateWidget(covariant EvidenceMedia oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url ||
        oldWidget.video != widget.video ||
        oldWidget.offsetMs != widget.offsetMs) {
      controller?.removeListener(_onTick);
      controller?.dispose();
      controller = null;
      fullUrl = null;
      error = null;
      load();
    }
  }

  void _onTick() {
    if (mounted) setState(() {});
  }

  Future<void> load() async {
    try {
      final store = AuthStore();
      final base = await store.getApiBaseUrl();
      final token = await store.getDeviceToken();
      headers = {'Authorization': 'Bearer $token'};
      final resolved = Uri.parse(base).resolve(widget.url);
      if (resolved.origin != Uri.parse(base).origin) {
        throw const FormatException(
          'Media must be served by your SafeSpace server.',
        );
      }
      fullUrl = resolved.toString();
      if (widget.video) {
        final c = VideoPlayerController.networkUrl(
          resolved,
          httpHeaders: headers,
        );
        controller = c;
        await c.initialize();
        c.addListener(_onTick);
        if (widget.offsetMs > 0) {
          await c.seekTo(Duration(milliseconds: widget.offsetMs));
        }
        if (widget.autoPlay) {
          await c.play();
        }
      }
      if (mounted) setState(() {});
    } catch (_) {
      if (mounted) {
        setState(
          () => error = 'Evidence could not be loaded. Check your connection.',
        );
      }
    }
  }

  @override
  void dispose() {
    controller?.removeListener(_onTick);
    controller?.dispose();
    super.dispose();
  }

  String _fmtDuration(Duration d) {
    final totalSeconds = d.inSeconds.clamp(0, 359999);
    final mins = (totalSeconds ~/ 60).toString().padLeft(2, '0');
    final secs = (totalSeconds % 60).toString().padLeft(2, '0');
    return '$mins:$secs';
  }

  void _togglePlay(VideoPlayerController c) {
    HapticFeedback.selectionClick();
    setState(() {
      if (c.value.isPlaying) {
        c.pause();
      } else {
        if (c.value.position >= c.value.duration &&
            c.value.duration > Duration.zero) {
          c.seekTo(Duration.zero);
        }
        c.play();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final radius = widget.borderRadius ?? BorderRadius.circular(AppRadii.lg);

    Widget stageChild;
    if (error != null) {
      stageChild = Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const AppIcon(
                'alert-circle',
                size: 24,
                color: AppColors.foregroundSecondary,
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                error!,
                style: AppTypography.support,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    } else if (fullUrl == null ||
        (widget.video && controller?.value.isInitialized != true)) {
      stageChild = Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppColors.foreground,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text('Loading 16:9 media…', style: AppTypography.caption),
          ],
        ),
      );
    } else if (!widget.video) {
      stageChild = Stack(
        fit: StackFit.expand,
        children: [
          Image.network(
            fullUrl!,
            headers: headers,
            fit: BoxFit.contain,
            errorBuilder: (_, __, ___) => Center(
              child: Text('Image unavailable', style: AppTypography.support),
            ),
          ),
          const Positioned(
            top: AppSpacing.sm,
            right: AppSpacing.sm,
            child: AppCapsule(label: '16:9 Keyframe', svgAsset: 'camera-01'),
          ),
        ],
      );
    } else {
      final c = controller!;
      final playing = c.value.isPlaying;
      final pos = c.value.position;
      final dur = c.value.duration;

      stageChild = GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => _togglePlay(c),
        child: Stack(
          fit: StackFit.expand,
          children: [
            Center(
              child: AspectRatio(
                aspectRatio: 16 / 9,
                child: FittedBox(
                  fit: BoxFit.contain,
                  child: SizedBox(
                    width: c.value.size.width > 0 ? c.value.size.width : 16,
                    height: c.value.size.height > 0 ? c.value.size.height : 9,
                    child: VideoPlayer(c),
                  ),
                ),
              ),
            ),
            const Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: FadeScrim(height: 68, isTop: false),
            ),
            if (!playing)
              Center(
                child: PressScale(
                  onTap: () => _togglePlay(c),
                  pressedScale: 0.92,
                  child: GlassSurface(
                    width: 56,
                    height: 56,
                    borderRadius: BorderRadius.circular(AppRadii.pill),
                    child: const Center(
                      child: AppIcon(
                        'play-03',
                        size: 24,
                        color: AppColors.foreground,
                      ),
                    ),
                  ),
                ),
              ),
            Positioned(
              left: AppSpacing.sm,
              right: AppSpacing.sm,
              bottom: AppSpacing.sm + 6,
              child: Row(
                children: [
                  PressScale(
                    onTap: () => _togglePlay(c),
                    pressedScale: 0.94,
                    child: GlassSurface(
                      height: AppSpacing.capsuleHeight,
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.md,
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          AppIcon(
                            playing ? 'pause-03' : 'play-03',
                            size: 14,
                            color: AppColors.foreground,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            '${_fmtDuration(pos)} / ${_fmtDuration(dur)}',
                            style: AppTypography.caption.copyWith(
                              color: AppColors.foreground,
                              fontFeatures: const [FontFeature.tabularFigures()],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const Spacer(),
                  const AppCapsule(label: '16:9'),
                ],
              ),
            ),
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: SizedBox(
                height: 4,
                child: VideoProgressIndicator(
                  c,
                  allowScrubbing: true,
                  padding: EdgeInsets.zero,
                  colors: const VideoProgressColors(
                    playedColor: AppColors.foreground,
                    bufferedColor: AppColors.foregroundSecondary,
                    backgroundColor: AppColors.divider,
                  ),
                ),
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: radius,
        border: Border.all(color: AppColors.divider, width: 1.0),
      ),
      clipBehavior: Clip.antiAlias,
      child: AspectRatio(
        aspectRatio: 16 / 9,
        child: stageChild,
      ),
    );
  }
}
