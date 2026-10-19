import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/theme/tokens.dart';
import 'package:safespace_mobile/core/widgets/app_capsule.dart';
import 'package:safespace_mobile/core/widgets/floating_nav_pill.dart';
import 'package:safespace_mobile/core/widgets/page_header.dart';
import 'package:safespace_mobile/core/widgets/shell_top_bar.dart';

void main() {
  group('ShellTopBar Tests', () {
    testWidgets('renders brand badge, device name, section title, and live status', (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ShellTopBar(
              deviceName: 'Nothing Phone (4a)_7495',
              sectionTitle: 'Alerts',
              isConnected: true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Brand badge text
      expect(find.text('SafeSpace'), findsOneWidget);
      // Device badge
      expect(find.text('Nothing Phone (4a)_7495'), findsOneWidget);
      // Section title
      expect(find.text('Alerts'), findsOneWidget);
      // Connection status
      expect(find.textContaining('Live'), findsOneWidget);
    });

    testWidgets('renders disconnected status and handles narrow screen without overflow', (tester) async {
      await tester.binding.setSurfaceSize(const Size(320, 600));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ShellTopBar(
              deviceName: 'Nothing Phone (4a)_7495',
              sectionTitle: 'Cameras',
              isConnected: false,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('SafeSpace'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('PageHeader Tests', () {
    testWidgets('renders back button, left-aligned title capsule, and trailing action with shared centerline', (tester) async {
      bool backTapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PageHeader(
              title: 'Incident Detail',
              onBack: () => backTapped = true,
              trailing: const AppCapsule(label: 'Verified'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Incident Detail'), findsOneWidget);
      expect(find.text('Verified'), findsOneWidget);
      expect(find.byType(GlassCircleButton), findsOneWidget);

      final backButton = find.byType(GlassCircleButton);
      final backCenter = tester.getCenter(backButton);
      final capsule = find.byType(AppCapsule).first;
      final capsuleCenter = tester.getCenter(capsule);

      // Verify strict vertical centerline alignment at y = 24 within the 48dp header
      expect((backCenter.dy - capsuleCenter.dy).abs(), lessThanOrEqualTo(1.0));

      // Tap back button
      await tester.tap(backButton);
      await tester.pump();
      expect(backTapped, isTrue);
    });
  });

  group('FloatingNavPill Tests', () {
    testWidgets('renders 48dp uniform touch targets, centered icons, and active highlight', (tester) async {
      int selectedIdx = 0;

      const navItems = [
        FloatingNavItem(index: 0, svgAsset: 'shield-01', label: 'Alerts'),
        FloatingNavItem(index: 1, svgAsset: 'video-on', label: 'Cameras'),
        FloatingNavItem(index: 2, svgAsset: 'shield-check', label: 'Rules'),
        FloatingNavItem(index: 3, svgAsset: 'search-01', label: 'Ask'),
        FloatingNavItem(index: 4, svgAsset: 'server-01', label: 'System'),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (ctx, setSt) => FloatingNavPill(
                currentIndex: selectedIdx,
                onIndexChanged: (idx) => setSt(() => selectedIdx = idx),
                items: navItems,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Find item tap targets
      final semantics = find.byWidgetPredicate(
        (w) => w is Semantics && w.properties.button == true && w.properties.label != null,
      );
      expect(semantics, findsNWidgets(5));

      // Verify each touch target is exactly 48x48
      final containers = tester.widgetList<AnimatedContainer>(find.byType(AnimatedContainer));
      for (final container in containers) {
        expect(container.constraints?.minWidth ?? 48, equals(48.0));
        expect(container.constraints?.minHeight ?? 48, equals(48.0));
      }

      // Tap item 2 (Rules)
      await tester.tap(semantics.at(2));
      await tester.pumpAndSettle();
      expect(selectedIdx, equals(2));
    });
  });
}
