import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/tokens.dart';
import 'app_capsule.dart';
import 'app_icon.dart';
import 'glass_surface.dart';

/// TopShellHeader directly mirroring the web dashboard shell header (DESIGN.md §13.7)
/// Features:
/// 1. Clean brand badge: Shield-check icon + "SafeSpace" + device badge capsule.
/// 2. Section label breadcrumb showing current section title (e.g. Alerts, Cameras, Rules, Ask, System) in AppCapsule.
/// 3. Subtle live status indicator dot (white/live pulsing dot with "Live feed connected" or latency indicator).
/// 4. Glass backdrop using GlassSurface / AppColors.glassFill with subtle bottom divider.
class TopShellHeader extends StatelessWidget {
  final String deviceName;
  final String sectionTitle;
  final bool isConnected;
  final String? connectionLabel;
  final VoidCallback? onTapStatus;
  final VoidCallback? onTapDevice;
  final Widget? trailing;

  const TopShellHeader({
    super.key,
    this.deviceName = 'Nothing Phone (4a)',
    required this.sectionTitle,
    this.isConnected = true,
    this.connectionLabel,
    this.onTapStatus,
    this.onTapDevice,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 420;
        final isVeryNarrow = constraints.maxWidth < 360;

        final statusText = connectionLabel ??
            (isConnected
                ? (isCompact ? 'Live' : 'Live feed connected')
                : (isCompact ? 'Offline' : 'Reconnecting…'));

        return GlassSurface(
          height: AppSpacing.floatingBarHeight,
          borderRadius: BorderRadius.zero,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.xs,
          ),
          border: const Border(
            bottom: BorderSide(
              color: AppColors.divider,
              width: 1.0,
            ),
          ),
          child: Row(
            children: [
              // ── 1. Left: Brand Badge & Section Breadcrumb ───────────
              Expanded(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const AppIcon(
                        'shield-check',
                        size: 20,
                        color: AppColors.foreground,
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      Text(
                        'SafeSpace',
                        style: AppTypography.cardTitle.copyWith(
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.2,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      AppCapsule(
                        label: deviceName,
                        onTap: onTapDevice,
                      ),
                      if (!isVeryNarrow) ...[
                        const SizedBox(width: AppSpacing.xs),
                        AppCapsule(label: sectionTitle),
                      ],
                    ],
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.xs),

              // ── 2. Right: Subtle Live Status Indicator ───────────────
              GestureDetector(
                onTap: onTapStatus == null
                    ? null
                    : () {
                        HapticFeedback.selectionClick();
                        onTapStatus!();
                      },
                behavior: HitTestBehavior.opaque,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    AnimatedContainer(
                      duration: AppMotion.shortDuration,
                      curve: AppMotion.standardCurve,
                      width: 7,
                      height: 7,
                      constraints: const BoxConstraints(
                        minWidth: 7,
                        minHeight: 7,
                        maxWidth: 7,
                        maxHeight: 7,
                      ),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isConnected
                            ? const Color(0xFF4ADE80)
                            : AppColors.foregroundDisabled,
                        boxShadow: isConnected
                            ? const [
                                BoxShadow(
                                  color: Color(0x664ADE80),
                                  blurRadius: 4,
                                  spreadRadius: 1,
                                ),
                              ]
                            : null,
                      ),
                    ),
                    const SizedBox(width: 5),
                    Text(
                      statusText,
                      style: AppTypography.caption.copyWith(
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                        color: isConnected
                            ? AppColors.foregroundSecondary
                            : AppColors.foregroundDisabled,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                  ],
                ),
              ),

              if (trailing != null) ...[
                const SizedBox(width: AppSpacing.sm),
                trailing!,
              ],
            ],
          ),
        );
      },
    );
  }
}
