import 'package:flutter/material.dart';
import '../theme/tokens.dart';
import 'press_scale.dart';

/// AppCard conforming to DESIGN.md §3 & §5.2
/// Surface container (#1A1A1A), 16 dp radius, 1 dp divider border.
class AppCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final VoidCallback? onTap;
  final Border? border;

  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.lg),
    this.radius = AppRadii.lg,
    this.onTap,
    this.border,
  });

  @override
  Widget build(BuildContext context) {
    Widget card = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(radius),
        border: border ?? Border.all(color: AppColors.divider, width: 1.0),
      ),
      child: child,
    );

    if (onTap != null) {
      return PressScale(
        onTap: onTap,
        pressedScale: 0.98,
        child: card,
      );
    }

    return card;
  }
}
