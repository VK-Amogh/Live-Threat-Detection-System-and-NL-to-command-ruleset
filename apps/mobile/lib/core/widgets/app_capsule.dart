import 'package:flutter/material.dart';
import '../theme/tokens.dart';
import 'glass_surface.dart';

/// AppCapsule conforming to DESIGN.md §5.1
/// 32 dp glass label pill, padding-h 12, caption text in white.
class AppCapsule extends StatelessWidget {
  final String label;
  final IconData? icon;
  final bool inverted;

  const AppCapsule({
    super.key,
    required this.label,
    this.icon,
    this.inverted = false,
  });

  @override
  Widget build(BuildContext context) {
    if (inverted) {
      return Container(
        height: AppSpacing.capsuleHeight,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        decoration: BoxDecoration(
          color: AppColors.foreground,
          borderRadius: BorderRadius.circular(AppRadii.pill),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 14, color: AppColors.background),
              const SizedBox(width: AppSpacing.xs),
            ],
            Text(
              label,
              style: AppTypography.caption.copyWith(
                color: AppColors.background,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      );
    }

    return GlassSurface(
      height: AppSpacing.capsuleHeight,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: AppColors.foreground),
            const SizedBox(width: AppSpacing.xs),
          ],
          Text(
            label,
            style: AppTypography.caption.copyWith(color: AppColors.foreground),
          ),
        ],
      ),
    );
  }
}
