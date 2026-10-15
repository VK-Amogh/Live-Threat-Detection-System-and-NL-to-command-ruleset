import 'dart:ui';
import 'package:flutter/material.dart';
import '../theme/tokens.dart';

/// Glass surface primitive strictly conforming to DESIGN.md §2.5
/// Applies Gaussian blur σ=24, glassFill tint, and 1 dp divider border.
class GlassSurface extends StatelessWidget {
  final Widget child;
  final BorderRadius borderRadius;
  final EdgeInsetsGeometry? padding;
  final double? width;
  final double? height;
  final BoxBorder? border;

  const GlassSurface({
    super.key,
    required this.child,
    this.borderRadius = const BorderRadius.all(Radius.circular(AppRadii.pill)),
    this.padding,
    this.width,
    this.height,
    this.border,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: borderRadius,
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
        child: Container(
          width: width,
          height: height,
          padding: padding,
          decoration: BoxDecoration(
            color: AppColors.glassFill,
            borderRadius: borderRadius,
            border: border ?? Border.all(color: AppColors.divider, width: 1.0),
          ),
          child: child,
        ),
      ),
    );
  }
}
