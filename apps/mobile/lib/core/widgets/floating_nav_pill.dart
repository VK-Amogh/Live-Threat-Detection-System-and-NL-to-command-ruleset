import 'package:flutter/material.dart';
import '../theme/tokens.dart';
import 'glass_surface.dart';
import 'press_scale.dart';

class FloatingNavItem {
  final int index;
  final IconData icon;
  final IconData selectedIcon;
  final String label;

  const FloatingNavItem({
    required this.index,
    required this.icon,
    required this.selectedIcon,
    required this.label,
  });
}

/// FloatingNavPill strictly conforming to DESIGN.md §5.1
/// Centered floating glass pill with liquid selected highlight.
class FloatingNavPill extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onIndexChanged;
  final List<FloatingNavItem> items;

  const FloatingNavPill({
    super.key,
    required this.currentIndex,
    required this.onIndexChanged,
    required this.items,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: GlassSurface(
        height: AppSpacing.floatingBarHeight,
        padding: const EdgeInsets.all(AppSpacing.xs),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: items.map((item) {
            final isSelected = currentIndex == item.index;

            return PressScale(
              onTap: () => onIndexChanged(item.index),
              pressedScale: 0.90,
              child: AnimatedContainer(
                duration: AppMotion.shortDuration,
                curve: AppMotion.standardCurve,
                width: AppSpacing.floatingItemSize,
                height: AppSpacing.floatingItemSize,
                decoration: BoxDecoration(
                  color: isSelected ? AppColors.highlight : Colors.transparent,
                  borderRadius: BorderRadius.circular(AppRadii.pill),
                ),
                child: Center(
                  child: Icon(
                    isSelected ? item.selectedIcon : item.icon,
                    size: 22,
                    color: isSelected
                        ? AppColors.foreground
                        : AppColors.foregroundSecondary,
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }
}
