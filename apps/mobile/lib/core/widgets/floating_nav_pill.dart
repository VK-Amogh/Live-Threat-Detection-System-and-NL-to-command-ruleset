import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/tokens.dart';
import 'app_icon.dart';

class FloatingNavItem {
  final int index;
  final IconData? icon;
  final IconData? selectedIcon;
  final String? svgAsset;
  final String label;

  const FloatingNavItem({
    required this.index,
    this.icon,
    this.selectedIcon,
    this.svgAsset,
    required this.label,
  });
}

/// Fixed navigation; page content ends above this row.
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
  Widget build(BuildContext context) => Row(
        children: [
          for (final item in items)
            Expanded(
              child: Semantics(
                label: item.label,
                button: true,
                selected: currentIndex == item.index,
                child: InkWell(
                  borderRadius: BorderRadius.circular(AppRadii.md),
                  onTap: () {
                    if (currentIndex != item.index) {
                      HapticFeedback.selectionClick();
                      onIndexChanged(item.index);
                    }
                  },
                  child: SizedBox(
                    height: 58,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        item.svgAsset != null
                            ? AppIcon(item.svgAsset!,
                                size: 22,
                                color: currentIndex == item.index
                                    ? AppColors.foreground
                                    : AppColors.foregroundSecondary)
                            : Icon(
                                currentIndex == item.index
                                    ? (item.selectedIcon ?? item.icon)
                                    : item.icon,
                                size: 22,
                                color: currentIndex == item.index
                                    ? AppColors.foreground
                                    : AppColors.foregroundSecondary,
                              ),
                        const SizedBox(height: 3),
                        Text(
                          item.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTypography.caption.copyWith(
                            fontSize: 10,
                            color: currentIndex == item.index
                                ? AppColors.foreground
                                : AppColors.foregroundSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      );
}
