import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/tokens.dart';
import 'app_icon.dart';
import 'glass_surface.dart';
import 'press_scale.dart';

/// AppCapsule conforming to DESIGN.md §5.1
/// 32 dp glass label pill, padding-h 12, caption text in white.
class AppCapsule extends StatelessWidget {
  final String label;
  final IconData? icon;
  final String? svgAsset;
  final bool inverted;
  final VoidCallback? onTap;

  const AppCapsule({
    super.key,
    required this.label,
    this.icon,
    this.svgAsset,
    this.inverted = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final fg = inverted ? AppColors.background : AppColors.foreground;
    Widget pill;
    if (inverted) {
      pill = Container(
        height: AppSpacing.capsuleHeight,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        decoration: BoxDecoration(
          color: AppColors.foreground,
          borderRadius: BorderRadius.circular(AppRadii.pill),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (svgAsset != null) ...[
              AppIcon(svgAsset!, size: 14, color: fg),
              const SizedBox(width: AppSpacing.xs),
            ] else if (icon != null) ...[
              Icon(icon, size: 14, color: fg),
              const SizedBox(width: AppSpacing.xs),
            ],
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.caption.copyWith(
                  color: fg,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      );
    } else {
      pill = GlassSurface(
        height: AppSpacing.capsuleHeight,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (svgAsset != null) ...[
              AppIcon(svgAsset!, size: 14, color: fg),
              const SizedBox(width: AppSpacing.xs),
            ] else if (icon != null) ...[
              Icon(icon, size: 14, color: fg),
              const SizedBox(width: AppSpacing.xs),
            ],
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.caption.copyWith(color: fg),
              ),
            ),
          ],
        ),
      );
    }

    if (onTap != null) {
      return PressScale(
        onTap: () {
          HapticFeedback.selectionClick();
          onTap!();
        },
        pressedScale: 0.96,
        child: pill,
      );
    }
    return pill;
  }
}

/// AppChip conforming strictly to DESIGN.md §5.2
/// 36 dp pill inside 48 dp touch target, #363636 when selected, #1A1A1A when unselected,
/// 1 dp divider border, leading 14 dp check-01 icon when selected.
class AppChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback? onTap;
  final String? leadingSvg;
  final bool showCheckWhenSelected;

  const AppChip({
    super.key,
    required this.label,
    required this.selected,
    this.onTap,
    this.leadingSvg,
    this.showCheckWhenSelected = true,
  });

  @override
  Widget build(BuildContext context) {
    final String? iconName =
        (selected && showCheckWhenSelected) ? 'check-01' : leadingSvg;

    return PressScale(
      onTap: onTap == null
          ? null
          : () {
              HapticFeedback.selectionClick();
              onTap!();
            },
      pressedScale: 0.96,
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 40),
        child: Center(
          widthFactor: 1.0,
          child: AnimatedContainer(
            duration: AppMotion.shortDuration,
            curve: AppMotion.standardCurve,
            height: 36,
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            decoration: BoxDecoration(
              color: selected ? AppColors.selectedChip : AppColors.surface,
              borderRadius: BorderRadius.circular(AppRadii.pill),
              border: Border.all(
                color: selected ? AppColors.foreground : AppColors.divider,
                width: 1.0,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (iconName != null) ...[
                  AppIcon(
                    iconName,
                    size: 14,
                    color: selected
                        ? AppColors.foreground
                        : AppColors.foregroundSecondary,
                  ),
                  const SizedBox(width: 6),
                ],
                Text(
                  label,
                  style: AppTypography.tabLabel.copyWith(
                    color: selected
                        ? AppColors.foreground
                        : AppColors.foregroundSecondary,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
