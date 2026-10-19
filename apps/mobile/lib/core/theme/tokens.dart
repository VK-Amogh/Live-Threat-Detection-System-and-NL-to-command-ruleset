import 'package:flutter/material.dart';


/// Design tokens strictly conforming to DESIGN.md
abstract final class AppColors {
  /// Pure black for all page backgrounds and viewer letterboxes
  static const Color background = Color(0xFF000000);

  /// Pure white for all primary text, primary button fill, and active icons
  static const Color foreground = Color(0xFFFFFFFF);

  /// Dark grey for cards, buttons, dialogs, and surface containers
  static const Color surface = Color(0xFF1A1A1A);

  /// White 80% alpha for secondary text drawn over media
  static const Color foregroundOnPhoto = Color(0xCCFFFFFF);

  /// White 60% alpha for secondary text, hints, counts, inactive nav icons
  static const Color foregroundSecondary = Color(0x99FFFFFF);

  /// White 38% alpha for disabled controls and text
  static const Color foregroundDisabled = Color(0x61FFFFFF);

  /// White 10% alpha for 1 dp hairline borders, scrub tracks, and dividers
  static const Color divider = Color(0x1AFFFFFF);

  /// White 12% alpha for pressed highlights and active nav pill highlight
  static const Color highlight = Color(0x1FFFFFFF);

  /// 70% opacity dark grey for blurred glass surface fill
  static const Color glassFill = Color(0xB31A1A1A);

  /// 60% opacity black for modal sheets and background scrims
  static const Color scrim = Color(0x99000000);

  /// Fill for selected filter chips
  static const Color selectedChip = Color(0xFF363636);
}

abstract final class AppSpacing {
  static const double xs = 4.0;
  static const double sm = 8.0;
  static const double md = 12.0;
  static const double lg = 16.0;
  static const double xl = 24.0;
  static const double xxl = 32.0;

  static const double touchMin = 48.0;
  static const double smallCircle = 40.0;
  static const double capsuleHeight = 32.0;
  static const double floatingBarHeight = 56.0;
  static const double floatingItemSize = 48.0;
  static const double floatingMarginH = 12.0;
  static const double floatingMarginV = 8.0;
  static const double floatingGap = 6.0;
  static const double floatingContentGap = 16.0;
}

abstract final class AppRadii {
  static const double xs = 4.0;
  static const double sm = 8.0;
  static const double md = 12.0;
  static const double lg = 16.0;
  static const double card = 20.0;
  static const double dialog = 28.0;
  static const double pill = 999.0;
}

abstract final class AppMotion {
  static const Duration instant = Duration(milliseconds: 90);
  static const Duration shortDuration = Duration(milliseconds: 180);
  static const Duration standard = Duration(milliseconds: 280);
  static const Duration longDuration = Duration(milliseconds: 420);
  static const Duration morph = Duration(milliseconds: 480);

  static const Curve standardCurve = Cubic(0.2, 0.0, 0.0, 1.0);
  static const Curve decel = Cubic(0.05, 0.7, 0.1, 1.0);
  static const Curve accel = Cubic(0.3, 0.0, 0.8, 0.15);
}

abstract final class AppTypography {
  /// Large editorial section titles (Photos, Incidents...) that scroll away
  static TextStyle get screenTitle => const TextStyle(fontFamily: 'AppSerif',
        fontSize: 42,
        height: 48 / 42,
        fontWeight: FontWeight.w400,
        letterSpacing: 0.5,
        color: AppColors.foreground,
      );

  /// Section headings, sheet titles, empty-state titles
  static TextStyle get sectionHeading => const TextStyle(fontFamily: 'AppSerif',
        fontSize: 28,
        height: 34 / 28,
        fontWeight: FontWeight.w400,
        letterSpacing: 0.4,
        color: AppColors.foreground,
      );

  /// Titles over cards, dialog titles
  static TextStyle get cardHeading => const TextStyle(fontFamily: 'AppSerif',
        fontSize: 24,
        height: 30 / 24,
        fontWeight: FontWeight.w400,
        letterSpacing: 0.3,
        color: AppColors.foreground,
      );

  /// Day headers, subsection titles
  static TextStyle get heading3 => const TextStyle(fontFamily: 'AppSerif',
        fontSize: 20,
        height: 26 / 20,
        fontWeight: FontWeight.w400,
        letterSpacing: 0.3,
        color: AppColors.foreground,
      );

  /// Card names, list item titles
  static TextStyle get cardTitle => const TextStyle(fontFamily: 'Inter',
        fontSize: 15,
        height: 20 / 15,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.1,
        color: AppColors.foreground,
      );

  /// Paragraphs, menu rows, input text
  static TextStyle get body => const TextStyle(fontFamily: 'Inter',
        fontSize: 14,
        height: 20 / 14,
        fontWeight: FontWeight.w400,
        letterSpacing: 0.2,
        color: AppColors.foreground,
      );

  /// Subtitles, counts, tabular figures
  static TextStyle get support => const TextStyle(fontFamily: 'Inter',
        fontSize: 13,
        height: 18 / 13,
        fontWeight: FontWeight.w400,
        letterSpacing: 0.2,
        color: AppColors.foregroundSecondary,
        fontFeatures: [FontFeature.tabularFigures()],
      );

  /// Dates, sizes, capsule text
  static TextStyle get caption => const TextStyle(fontFamily: 'Inter',
        fontSize: 12,
        height: 16 / 12,
        fontWeight: FontWeight.w500,
        letterSpacing: 0.3,
        color: AppColors.foregroundSecondary,
        fontFeatures: [FontFeature.tabularFigures()],
      );

  /// Chip labels
  static TextStyle get tabLabel => const TextStyle(fontFamily: 'Inter',
        fontSize: 12,
        height: 16 / 12,
        fontWeight: FontWeight.w500,
        letterSpacing: 0.4,
        color: AppColors.foreground,
      );

  /// Button labels
  static TextStyle get button => const TextStyle(fontFamily: 'Inter',
        fontSize: 14,
        height: 20 / 14,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.1,
        color: AppColors.foreground,
      );
}


