import 'package:flutter/material.dart';
import '../theme/tokens.dart';

/// FadeScrim per DESIGN.md §2.1 and §5.1
/// A non-linear black to transparent dissolve scrim positioned behind floating bars.
class FadeScrim extends StatelessWidget {
  final double height;
  final bool isTop;
  final double strength;

  const FadeScrim({
    super.key,
    required this.height,
    this.isTop = false,
    this.strength = 0.94,
  });

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Container(
        height: height,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: isTop ? Alignment.topCenter : Alignment.bottomCenter,
            end: isTop ? Alignment.bottomCenter : Alignment.topCenter,
            colors: [
              AppColors.background.withOpacity(strength),
              AppColors.background.withOpacity(strength * 0.75),
              AppColors.background.withOpacity(strength * 0.4),
              AppColors.background.withOpacity(0.0),
            ],
            stops: const [0.0, 0.4, 0.75, 1.0],
          ),
        ),
      ),
    );
  }
}
