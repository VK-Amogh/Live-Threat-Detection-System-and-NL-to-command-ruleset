import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/tokens.dart';
import 'app_capsule.dart';
import 'app_icon.dart';
import 'glass_surface.dart';
import 'press_scale.dart';

/// GlassCircleButton conforming to DESIGN.md §5.1
/// 48 dp (or 40 dp compact inside 48 dp hit target) circular glass action button.
class GlassCircleButton extends StatelessWidget {
  final String svgAsset;
  final VoidCallback? onTap;
  final String? tooltip;
  final bool compact;
  final bool active;
  final IconData? icon;

  const GlassCircleButton({
    super.key,
    required this.svgAsset,
    this.onTap,
    this.tooltip,
    this.compact = false,
    this.active = false,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final visualSize = compact ? AppSpacing.smallCircle : AppSpacing.touchMin;
    final iconColor =
        onTap == null ? AppColors.foregroundDisabled : AppColors.foreground;

    final button = PressScale(
      onTap: onTap == null
          ? null
          : () {
              HapticFeedback.selectionClick();
              onTap!();
            },
      pressedScale: 0.92,
      child: SizedBox(
        width: AppSpacing.touchMin,
        height: AppSpacing.touchMin,
        child: Center(
          child: GlassSurface(
            width: visualSize,
            height: visualSize,
            borderRadius: BorderRadius.circular(AppRadii.pill),
            border: Border.all(
              color: active ? AppColors.foreground : AppColors.divider,
              width: active ? 1.5 : 1.0,
            ),
            child: Center(
              child: icon != null
                  ? Icon(
                      icon,
                      size: compact ? 18 : 20,
                      color: iconColor,
                    )
                  : AppIcon(
                      svgAsset,
                      size: compact ? 18 : 20,
                      color: iconColor,
                    ),
            ),
          ),
        ),
      ),
    );

    if (tooltip != null && tooltip!.isNotEmpty) {
      return Semantics(
        label: tooltip,
        button: true,
        child: Tooltip(message: tooltip!, child: button),
      );
    }
    return button;
  }
}

/// PageHeader conforming strictly to DESIGN.md §4.4 & §5.1
/// [Back 40/48] · 6 · [Expanded: capsule, left aligned] · 6 · [trailing slot at right edge]
/// Shared 24dp vertical centerline ensures strict geometric alignment across all actions.
class PageHeader extends StatelessWidget {
  final String title;
  final VoidCallback? onBack;
  final Widget? trailing;
  final Widget? leading;
  final String? subtitle;

  const PageHeader({
    super.key,
    required this.title,
    this.onBack,
    this.trailing,
    this.leading,
    this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    final backButton = leading ??
        GlassCircleButton(
          svgAsset: 'arrow-left',
          compact: true,
          tooltip: 'Back',
          onTap: onBack ?? () => Navigator.of(context).maybePop(),
        );

    final headerRow = SizedBox(
      height: AppSpacing.touchMin,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Geometrically aligned Back button (48dp touch area, 40dp visual glass circle)
          backButton,
          const SizedBox(width: AppSpacing.floatingGap),

          // Centered/left capsule (32dp height, vertically centered on 24dp centerline)
          Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: AppCapsule(label: title),
            ),
          ),

          // Aligned trailing action (vertically centered on the same 24dp centerline)
          if (trailing != null) ...[
            const SizedBox(width: AppSpacing.floatingGap),
            SizedBox(
              height: AppSpacing.touchMin,
              child: Center(child: trailing!),
            ),
          ],
        ],
      ),
    );

    if (subtitle != null && subtitle!.isNotEmpty) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          headerRow,
          const SizedBox(height: AppSpacing.xs),
          Padding(
            padding: const EdgeInsets.only(left: AppSpacing.lg),
            child: Text(
              subtitle!,
              style: AppTypography.support,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      );
    }

    return headerRow;
  }
}
