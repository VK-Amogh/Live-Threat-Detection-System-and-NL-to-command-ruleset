import 'package:flutter/material.dart';
import '../theme/tokens.dart';
import 'app_icon.dart';

/// EmptyState conforming to DESIGN.md §5.5
/// 96 dp surface circle, 40 dp Stratis SVG or Material icon, sectionHeading serif title, body description.
class EmptyState extends StatelessWidget {
  final IconData? icon;
  final String? svgAsset;
  final String title;
  final String? message;
  final String? subtitle;
  final Widget? action;

  const EmptyState({
    super.key,
    this.icon,
    this.svgAsset,
    required this.title,
    this.message,
    this.subtitle,
    this.action,
  });

  @override
  Widget build(BuildContext context) {
    final description = subtitle ?? message ?? '';
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 360),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 96,
                height: 96,
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.divider, width: 1.0),
                ),
                child: Center(
                  child: svgAsset != null
                      ? AppIcon(svgAsset!, size: 40, color: AppColors.foreground)
                      : Icon(
                          icon ?? Icons.inbox_outlined,
                          size: 40,
                          color: AppColors.foreground,
                        ),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                title,
                style: AppTypography.sectionHeading,
                textAlign: TextAlign.center,
              ),
              if (description.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  description,
                  style: AppTypography.body.copyWith(
                    color: AppColors.foregroundSecondary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
              if (action != null) ...[
                const SizedBox(height: AppSpacing.xl),
                action!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}
