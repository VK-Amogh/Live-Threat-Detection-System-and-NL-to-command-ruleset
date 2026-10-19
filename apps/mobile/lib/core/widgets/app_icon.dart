import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../theme/tokens.dart';

/// Renders Stratis linear SVG icons from `assets/icons/<name>.svg`
/// strictly tinted using DESIGN.md monochrome tokens.
class AppIcon extends StatelessWidget {
  final String name;
  final double size;
  final Color color;

  const AppIcon(
    this.name, {
    super.key,
    this.size = 22.0,
    this.color = AppColors.foreground,
  });

  @override
  Widget build(BuildContext context) {
    var normalized = name.trim();
    if (normalized.startsWith('/')) {
      normalized = normalized.substring(1);
    }
    while (normalized.startsWith('assets/icons/')) {
      normalized = normalized.substring('assets/icons/'.length);
    }
    if (normalized.endsWith('.svg')) {
      normalized = normalized.substring(0, normalized.length - 4);
    }
    final assetPath = 'assets/icons/$normalized.svg';

    return SvgPicture.asset(
      assetPath,
      width: size,
      height: size,
      colorFilter: ColorFilter.mode(color, BlendMode.srcIn),
      placeholderBuilder: (_) => SizedBox(width: size, height: size),
    );
  }
}
