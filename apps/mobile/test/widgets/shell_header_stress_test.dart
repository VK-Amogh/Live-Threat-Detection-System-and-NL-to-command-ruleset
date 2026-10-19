import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:safespace_mobile/core/widgets/top_shell_header.dart';
import 'package:safespace_mobile/core/widgets/floating_nav_pill.dart';
import 'package:safespace_mobile/core/widgets/app_icon.dart';
import 'package:safespace_mobile/core/widgets/glass_surface.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const navItems = [
    FloatingNavItem(index: 0, svgAsset: 'shield-01', label: 'Alerts'),
    FloatingNavItem(index: 1, svgAsset: 'video-on', label: 'Cameras'),
    FloatingNavItem(index: 2, svgAsset: 'shield-check', label: 'Rules'),
    FloatingNavItem(index: 3, svgAsset: 'search-01', label: 'Ask'),
    FloatingNavItem(index: 4, svgAsset: 'server-01', label: 'System'),
  ];

  group('Requirement 1: Edge Case Narrow Viewport (320dp)', () {
    testWidgets('TopShellHeader does not overflow at 320dp viewport',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(320, 600));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TopShellHeader(
              deviceName: 'Nothing Phone (4a)',
              sectionTitle: 'Alerts',
              isConnected: true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull,
          reason: 'Must not overflow at 320dp');
      expect(find.text('SafeSpace'), findsOneWidget);
      expect(find.text('Live'), findsOneWidget);
    });

    testWidgets('navigation fits a 320dp viewport', (tester) async {
      await tester.binding.setSurfaceSize(const Size(320, 600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Align(
            alignment: Alignment.bottomCenter,
            child: SizedBox(
              width: 304,
              child: FloatingNavPill(
                currentIndex: 0,
                onIndexChanged: (_) {},
                items: navItems,
              ),
            ),
          ),
        ),
      ));
      await tester.pump();
      expect(tester.takeException(), isNull);
      expect(find.text('Cameras'), findsOneWidget);
    });
  });

  group('Requirement 2: Fixed navigation sizing', () {
    testWidgets('all tabs have equal width', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 300,
            child: FloatingNavPill(
              currentIndex: 2,
              onIndexChanged: (_) {},
              items: navItems,
            ),
          ),
        ),
      ));
      await tester.pump();
      final taps = find.descendant(
        of: find.byType(FloatingNavPill),
        matching: find.byType(InkWell),
      );
      expect(taps, findsNWidgets(5));
      final widths = tester.widgetList<InkWell>(taps).toList();
      final firstWidth = tester.getSize(find.byWidget(widths.first)).width;
      for (final tap in widths.skip(1)) {
        expect(tester.getSize(find.byWidget(tap)).width, firstWidth);
      }
      expect(tester.takeException(), isNull);
    });
  });
  group('Requirement 3: AppIcon Path and Prefix Resolution', () {
    testWidgets(
        'AppIcon resolves bare names, filenames, and asset paths without prefix doubling',
        (tester) async {
      final testCases = <String, String>{
        'shield-check': 'assets/icons/shield-check.svg',
        'shield-check.svg': 'assets/icons/shield-check.svg',
        '/shield-check': 'assets/icons/shield-check.svg',
        '/shield-check.svg': 'assets/icons/shield-check.svg',
        'assets/icons/shield-check': 'assets/icons/shield-check.svg',
        'assets/icons/shield-check.svg': 'assets/icons/shield-check.svg',
        '/assets/icons/shield-check.svg': 'assets/icons/shield-check.svg',
        'assets/icons/assets/icons/shield-check.svg':
            'assets/icons/shield-check.svg',
        '  shield-check  ': 'assets/icons/shield-check.svg',
        '  assets/icons/shield-check.svg  ': 'assets/icons/shield-check.svg',
      };

      for (final entry in testCases.entries) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Center(
                child: AppIcon(entry.key),
              ),
            ),
          ),
        );
        await tester.pump();

        final svgFinder = find.byType(SvgPicture);
        expect(svgFinder, findsOneWidget);

        final svgWidget = tester.widget<SvgPicture>(svgFinder);
        final bytesLoader = svgWidget.bytesLoader;
        expect(bytesLoader, isA<SvgAssetLoader>());
        final assetLoader = bytesLoader as SvgAssetLoader;
        expect(assetLoader.assetName, equals(entry.value),
            reason:
                'Input "${entry.key}" resolved to "${assetLoader.assetName}" instead of "${entry.value}"');
      }
    });
  });

  group('Requirement 4: TopShellHeader Viewport Adaptability', () {
    testWidgets(
        'TopShellHeader on standard mobile viewports (360dp, 375dp, 390dp, 412dp) must not overflow',
        (tester) async {
      final mobileWidths = [360.0, 375.0, 390.0, 412.0];
      final overflows = <double, String>{};

      for (final w in mobileWidths) {
        await tester.binding.setSurfaceSize(Size(w, 800));

        FlutterErrorDetails? errorDetails;
        final originalOnError = FlutterError.onError;
        FlutterError.onError = (details) => errorDetails = details;

        try {
          await tester.pumpWidget(
            MaterialApp(
              key: ValueKey('mobile_screen_$w'),
              home: const Scaffold(
                body: TopShellHeader(
                  deviceName: 'Nothing Phone (4a)',
                  sectionTitle: 'Cameras',
                  isConnected: true,
                ),
              ),
            ),
          );
          await tester.pump();
        } finally {
          FlutterError.onError = originalOnError;
        }

        if (errorDetails != null) {
          overflows[w] = errorDetails!.exception.toString();
        }
      }
      await tester.binding.setSurfaceSize(null);

      expect(overflows, isEmpty,
          reason:
              'TopShellHeader produces RenderFlex overflow on standard mobile viewports (360dp to 412dp): $overflows');
    });
  });
}
