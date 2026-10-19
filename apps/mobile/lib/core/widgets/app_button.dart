import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/tokens.dart';
import 'app_icon.dart';
import 'press_scale.dart';

enum AppButtonVariant { primary, secondary }

/// AppButton per DESIGN.md §5.2
/// Three-color rule: Primary is solid white fill with black text.
/// Secondary is dark-grey surface with white text and 1 dp divider border.
class AppButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final AppButtonVariant variant;
  final IconData? icon;
  final String? svgAsset;
  final bool expand;
  final bool isLoading;

  const AppButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.icon,
    this.svgAsset,
    this.expand = false,
    this.isLoading = false,
  });

  const AppButton.secondary({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.svgAsset,
    this.expand = false,
    this.isLoading = false,
  }) : variant = AppButtonVariant.secondary;

  @override
  Widget build(BuildContext context) {
    final isPrimary = variant == AppButtonVariant.primary;
    final isEnabled = onPressed != null && !isLoading;

    final bgColor = isPrimary
        ? (isEnabled ? AppColors.foreground : AppColors.surface)
        : AppColors.surface;

    final textColor = isPrimary
        ? (isEnabled ? AppColors.background : AppColors.foregroundDisabled)
        : (isEnabled ? AppColors.foreground : AppColors.foregroundDisabled);

    final border = isPrimary
        ? null
        : Border.all(color: AppColors.divider, width: 1.0);

    Widget content = Row(
      mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (isLoading)
          SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: textColor,
            ),
          )
        else ...[
          if (svgAsset != null) ...[
            AppIcon(svgAsset!, size: 18, color: textColor),
            const SizedBox(width: AppSpacing.sm),
          ] else if (icon != null) ...[
            Icon(icon, size: 18, color: textColor),
            const SizedBox(width: AppSpacing.sm),
          ],
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTypography.button.copyWith(color: textColor),
            ),
          ),
        ],
      ],
    );

    return PressScale(
      onTap: isEnabled
          ? () {
              HapticFeedback.selectionClick();
              onPressed!();
            }
          : null,
      pressedScale: 0.97,
      child: AnimatedContainer(
        duration: AppMotion.shortDuration,
        curve: AppMotion.standardCurve,
        height: AppSpacing.touchMin,
        constraints: BoxConstraints(minWidth: expand ? double.infinity : 108),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.sm,
        ),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(AppRadii.pill),
          border: border,
        ),
        child: Center(
          widthFactor: expand ? null : 1.0,
          child: content,
        ),
      ),
    );
  }
}
