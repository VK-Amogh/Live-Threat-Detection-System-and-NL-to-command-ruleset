import 'package:flutter/material.dart';
import '../theme/tokens.dart';
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
  final bool expand;
  final bool isLoading;

  const AppButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.icon,
    this.expand = false,
    this.isLoading = false,
  });

  const AppButton.secondary({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
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
          if (icon != null) ...[
            Icon(icon, size: 20, color: textColor),
            const SizedBox(width: AppSpacing.sm),
          ],
          Text(
            label,
            style: AppTypography.button.copyWith(color: textColor),
          ),
        ],
      ],
    );

    return PressScale(
      onTap: isEnabled ? onPressed : null,
      pressedScale: 0.97,
      child: AnimatedContainer(
        duration: AppMotion.shortDuration,
        curve: AppMotion.standardCurve,
        height: AppSpacing.touchMin,
        constraints: BoxConstraints(minWidth: expand ? double.infinity : 120),
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl, vertical: AppSpacing.sm),
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
