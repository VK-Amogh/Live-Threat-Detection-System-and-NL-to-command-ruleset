import 'package:flutter/material.dart';
import '../theme/tokens.dart';
import 'app_capsule.dart';
import 'glass_surface.dart';
import 'press_scale.dart';

/// PageHeader conforming to DESIGN.md §4.4 & §5.1
/// [Back 40/48] · 6 · [Expanded: capsule, left aligned] · [trailing slot at right edge]
class PageHeader extends StatelessWidget {
  final String title;
  final VoidCallback? onBack;
  final Widget? trailing;

  const PageHeader({
    super.key,
    required this.title,
    this.onBack,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: AppSpacing.touchMin,
      child: Row(
        children: [
          PressScale(
            onTap: onBack ?? () => Navigator.of(context).maybePop(),
            pressedScale: 0.94,
            child: SizedBox(
              width: AppSpacing.touchMin,
              height: AppSpacing.touchMin,
              child: Center(
                child: GlassSurface(
                  width: AppSpacing.smallCircle,
                  height: AppSpacing.smallCircle,
                  borderRadius: BorderRadius.circular(AppRadii.pill),
                  child: const Center(
                    child: Icon(
                      Icons.arrow_back_rounded,
                      size: 20,
                      color: AppColors.foreground,
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.floatingGap),
          Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: AppCapsule(label: title),
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}
