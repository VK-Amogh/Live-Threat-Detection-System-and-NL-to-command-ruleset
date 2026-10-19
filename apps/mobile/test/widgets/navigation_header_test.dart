import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/theme/tokens.dart';
import 'package:safespace_mobile/core/widgets/app_capsule.dart';
import 'package:safespace_mobile/core/widgets/app_icon.dart';
import 'package:safespace_mobile/core/widgets/floating_nav_pill.dart';
import 'package:safespace_mobile/core/widgets/glass_surface.dart';
import 'package:safespace_mobile/core/widgets/top_shell_header.dart';

void main() {
  group('TopShellHeader Widget Tests', () {
    testWidgets(
        'renders brand badge (shield icon, SafeSpace text, device capsule)',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
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

      // Brand badge: shield icon
      final shieldIcon = find.byWidgetPredicate(
        (w) => w is AppIcon && w.name == 'shield-check',
      );
      expect(shieldIcon, findsOneWidget);

      // Brand title
      expect(find.text('SafeSpace'), findsOneWidget);

      // Device badge capsule
      expect(find.text('Nothing Phone (4a)'), findsOneWidget);
    });

    testWidgets('renders section label breadcrumb correctly', (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TopShellHeader(
              deviceName: 'Nothing Phone (4a)',
              sectionTitle: 'Cameras',
              isConnected: true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Section title
      expect(find.text('Cameras'), findsOneWidget);

      // Section title is wrapped in an AppCapsule
      final sectionCapsule = find.ancestor(
        of: find.text('Cameras'),
        matching: find.byType(AppCapsule),
      );
      expect(sectionCapsule, findsOneWidget);
    });

    testWidgets('renders live status dot and text when connected',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
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

      // Live status text ('Live' on mobile, or 'Live feed connected' on wide)
      expect(find.textContaining('Live'), findsOneWidget);

      // Pulsing green live status dot
      final liveDotFinder = find.byWidgetPredicate((w) {
        if (w is AnimatedContainer) {
          final dec = w.decoration;
          if (dec is BoxDecoration && dec.shape == BoxShape.circle) {
            return dec.color == const Color(0xFF4ADE80);
          }
        }
        return false;
      });
      expect(liveDotFinder, findsOneWidget);
    });

    testWidgets('renders full live status label on wide screen',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(600, 900));
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

      expect(find.text('Live feed connected'), findsOneWidget);
    });

    testWidgets('renders offline status dot and text when disconnected',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TopShellHeader(
              deviceName: 'Nothing Phone (4a)',
              sectionTitle: 'Rules',
              isConnected: false,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Disconnected status text ('Reconnecting…' / 'Offline')
      expect(
        find.byWidgetPredicate(
          (w) =>
              w is Text &&
              (w.data?.contains('Off') == true ||
                  w.data?.contains('Reconnecting') == true),
        ),
        findsOneWidget,
      );

      // Disabled status dot
      final offlineDotFinder = find.byWidgetPredicate((w) {
        if (w is AnimatedContainer) {
          final dec = w.decoration;
          if (dec is BoxDecoration && dec.shape == BoxShape.circle) {
            return dec.color == AppColors.foregroundDisabled;
          }
        }
        return false;
      });
      expect(offlineDotFinder, findsOneWidget);
    });

    testWidgets('invokes onTapStatus and onTapDevice callbacks',
        (tester) async {
      bool statusTapped = false;
      bool deviceTapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TopShellHeader(
              deviceName: 'Nothing Phone (4a)',
              sectionTitle: 'System',
              isConnected: true,
              onTapStatus: () => statusTapped = true,
              onTapDevice: () => deviceTapped = true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tap status
      await tester.tap(find.textContaining('Live'));
      await tester.pump();
      expect(statusTapped, isTrue);

      // Tap device
      await tester.tap(find.text('Nothing Phone (4a)'));
      await tester.pump();
      expect(deviceTapped, isTrue);
    });

    testWidgets('resilient on narrow mobile screen without overflow',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(320, 600));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TopShellHeader(
              deviceName: 'Nothing Phone (4a)_Long_Identifier',
              sectionTitle: 'Investigation',
              isConnected: true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('SafeSpace'), findsOneWidget);
    });
  });

  group('Fixed navigation row', () {
    testWidgets('fits a narrow phone and switches tabs', (tester) async {
      await tester.binding.setSurfaceSize(const Size(320, 600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      var current = 0;
      const items = [
        FloatingNavItem(index: 0, svgAsset: 'shield-01', label: 'History'),
        FloatingNavItem(index: 1, svgAsset: 'video-on', label: 'Cameras'),
        FloatingNavItem(index: 2, svgAsset: 'shield-check', label: 'Rules'),
        FloatingNavItem(index: 3, svgAsset: 'search-01', label: 'Ask'),
        FloatingNavItem(index: 4, svgAsset: 'server-01', label: 'System'),
      ];
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (_, update) => Align(
              alignment: Alignment.bottomCenter,
              child: SizedBox(
                width: 304,
                child: FloatingNavPill(
                  currentIndex: current,
                  onIndexChanged: (index) => update(() => current = index),
                  items: items,
                ),
              ),
            ),
          ),
        ),
      ));
      await tester.pump();
      expect(tester.takeException(), isNull);
      expect(find.text('History'), findsOneWidget);
      await tester.tap(find.text('Ask'));
      await tester.pump();
      expect(current, 3);
      expect(tester.takeException(), isNull);
    });
  });
}
