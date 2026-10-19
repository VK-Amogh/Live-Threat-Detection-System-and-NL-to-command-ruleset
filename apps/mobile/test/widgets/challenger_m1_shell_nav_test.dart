import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/theme/tokens.dart';
import 'package:safespace_mobile/core/widgets/app_card.dart';
import 'package:safespace_mobile/core/widgets/app_capsule.dart';
import 'package:safespace_mobile/core/widgets/app_icon.dart';
import 'package:safespace_mobile/core/widgets/floating_nav_pill.dart';
import 'package:safespace_mobile/core/widgets/glass_surface.dart';
import 'package:safespace_mobile/core/widgets/press_scale.dart';
import 'package:safespace_mobile/core/widgets/top_shell_header.dart';

void main() {
  group('TopShellHeader Adversarial Challenge Tests', () {
    testWidgets(
        'TopShellHeader: Connected state styling (pulsing green dot & glowing shadow, live label)',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      bool statusTapped = false;
      bool deviceTapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TopShellHeader(
              deviceName: 'Nothing Phone (4a)',
              sectionTitle: 'Alerts',
              isConnected: true,
              onTapStatus: () => statusTapped = true,
              onTapDevice: () => deviceTapped = true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // 1. Verify GlassSurface container properties
      final glassFinder = find
          .descendant(
            of: find.byType(TopShellHeader),
            matching: find.byType(GlassSurface),
          )
          .first;
      expect(glassFinder, findsOneWidget);
      final glassWidget = tester.widget<GlassSurface>(glassFinder);
      expect(glassWidget.height, equals(AppSpacing.floatingBarHeight));
      expect(glassWidget.borderRadius, equals(BorderRadius.zero));

      // 2. Brand badge checks
      final shieldIcon = find.byWidgetPredicate(
        (w) =>
            w is AppIcon &&
            w.name == 'shield-check' &&
            w.size == 20 &&
            w.color == AppColors.foreground,
      );
      expect(shieldIcon, findsOneWidget);
      expect(find.text('SafeSpace'), findsOneWidget);

      final deviceCapsule = find.byWidgetPredicate(
        (w) => w is AppCapsule && w.label == 'Nothing Phone (4a)',
      );
      expect(deviceCapsule, findsOneWidget);

      // 3. Section Title Capsule
      final sectionCapsule = find.byWidgetPredicate(
        (w) => w is AppCapsule && w.label == 'Alerts',
      );
      expect(sectionCapsule, findsOneWidget);

      // 4. Live indicator dot - green Color(0xFF4ADE80) with glowing BoxShadow
      final liveDotFinder = find.byWidgetPredicate((w) {
        if (w is AnimatedContainer) {
          final dec = w.decoration;
          if (dec is BoxDecoration && dec.shape == BoxShape.circle) {
            final isGreen = dec.color == const Color(0xFF4ADE80);
            final hasGlow = dec.boxShadow != null &&
                dec.boxShadow!.isNotEmpty &&
                dec.boxShadow!.first.color == const Color(0x664ADE80) &&
                dec.boxShadow!.first.blurRadius == 4 &&
                dec.boxShadow!.first.spreadRadius == 1;
            return isGreen &&
                hasGlow &&
                w.constraints?.minWidth == 7 &&
                w.constraints?.minHeight == 7;
          }
        }
        return false;
      });
      expect(liveDotFinder, findsOneWidget,
          reason:
              'Connected indicator dot must be pulsing green 7x7 with glowing shadow');

      // 5. Status text and text color
      final statusTextFinder = find.byWidgetPredicate(
        (w) =>
            w is Text && (w.data == 'Live' || w.data == 'Live feed connected'),
      );
      expect(statusTextFinder, findsOneWidget);
      final textWidget = tester.widget<Text>(statusTextFinder);
      expect(textWidget.style?.color, equals(AppColors.foregroundSecondary));

      // 6. Callback tests
      await tester.tap(statusTextFinder);
      await tester.pump();
      expect(statusTapped, isTrue);

      await tester.tap(deviceCapsule);
      await tester.pump();
      expect(deviceTapped, isTrue);
    });

    testWidgets(
        'TopShellHeader: Disconnected state styling (disabled dot, no shadow, Reconnecting…)',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TopShellHeader(
              deviceName: 'Nothing Phone (4a)',
              sectionTitle: 'Cameras',
              isConnected: false,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // 1. Disconnected dot - Color is AppColors.foregroundDisabled, BoxShadow is strictly null
      final disconnectedDotFinder = find.byWidgetPredicate((w) {
        if (w is AnimatedContainer) {
          final dec = w.decoration;
          if (dec is BoxDecoration && dec.shape == BoxShape.circle) {
            final isDisabledColor = dec.color == AppColors.foregroundDisabled;
            final hasNoGlow = dec.boxShadow == null;
            return isDisabledColor && hasNoGlow;
          }
        }
        return false;
      });
      expect(disconnectedDotFinder, findsOneWidget,
          reason:
              'Disconnected indicator dot must be disabled color with no glow shadow');

      // 2. Disconnected status text
      final reconnectingTextFinder = find.byWidgetPredicate(
        (w) => w is Text && (w.data == 'Offline' || w.data == 'Reconnecting…'),
      );
      expect(reconnectingTextFinder, findsOneWidget);
      final textWidget = tester.widget<Text>(reconnectingTextFinder);
      expect(textWidget.style?.color, equals(AppColors.foregroundDisabled));
    });

    testWidgets(
        'TopShellHeader: Custom connectionLabel override functions properly',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TopShellHeader(
              sectionTitle: 'Rules',
              isConnected: true,
              connectionLabel: 'Latency: 42ms',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Latency: 42ms'), findsOneWidget);
      expect(find.text('Live feed connected'), findsNothing);
    });

    testWidgets(
        'TopShellHeader: Narrow screen (<360dp) compact text and breadcrumb hiding',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(320, 600));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TopShellHeader(
              deviceName: 'Device',
              sectionTitle: 'System',
              isConnected: true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // In narrow mode (<360dp), section title capsule is hidden to eliminate RenderFlex overflow
      expect(find.text('System'), findsNothing);
      // Status text compacts to 'Live'
      expect(find.text('Live'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets(
        'TopShellHeader: Dynamic state transition (Connected -> Disconnected -> Connected)',
        (tester) async {
      bool isConn = true;

      await tester.pumpWidget(
        StatefulBuilder(
          builder: (context, setState) {
            return MaterialApp(
              home: Scaffold(
                body: Column(
                  children: [
                    TopShellHeader(
                      sectionTitle: 'Alerts',
                      isConnected: isConn,
                    ),
                    ElevatedButton(
                      onPressed: () => setState(() => isConn = !isConn),
                      child: const Text('Toggle'),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      );
      await tester.pumpAndSettle();

      // State 1: Connected
      expect(find.text('Live feed connected'), findsOneWidget);

      // Toggle to Disconnected
      await tester.tap(find.text('Toggle'));
      await tester.pumpAndSettle();

      // State 2: Disconnected
      expect(find.text('Reconnecting…'), findsOneWidget);
      expect(find.text('Live feed connected'), findsNothing);

      // Toggle back to Connected
      await tester.tap(find.text('Toggle'));
      await tester.pumpAndSettle();

      // State 3: Connected again
      expect(find.text('Live feed connected'), findsOneWidget);
      expect(find.text('Reconnecting…'), findsNothing);
    });
  });

  group('AppCard Adversarial Challenge Tests', () {
    testWidgets('AppCard: Default radius is strictly 20dp (AppRadii.card)',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AppCard(
              child: Text('Card Content'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final containerFinder = find
          .ancestor(
            of: find.text('Card Content'),
            matching: find.byType(Container),
          )
          .first;

      final containerWidget = tester.widget<Container>(containerFinder);
      final decoration = containerWidget.decoration as BoxDecoration;

      // 1. Default borderRadius must be circular with AppRadii.card (20.0)
      expect(decoration.borderRadius,
          equals(BorderRadius.circular(AppRadii.card)));
      expect(AppRadii.card, equals(20.0));

      // 2. Default surface color
      expect(decoration.color, equals(AppColors.surface));

      // 3. Default border
      expect(decoration.border,
          equals(Border.all(color: AppColors.divider, width: 1.0)));

      // 4. Default padding is AppSpacing.lg (16.0)
      expect(
          containerWidget.padding, equals(const EdgeInsets.all(AppSpacing.lg)));
    });

    testWidgets('AppCard: radius parameter overrides default radius',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AppCard(
              radius: 12.0,
              child: Text('Custom Radius Card'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final containerFinder = find
          .ancestor(
            of: find.text('Custom Radius Card'),
            matching: find.byType(Container),
          )
          .first;

      final decoration = (tester.widget<Container>(containerFinder).decoration
          as BoxDecoration);
      expect(decoration.borderRadius, equals(BorderRadius.circular(12.0)));
    });

    testWidgets(
        'AppCard: borderRadius geometry parameter overrides radius and default completely',
        (tester) async {
      const customBorderRadius = BorderRadius.only(
        topLeft: Radius.circular(32.0),
        bottomRight: Radius.circular(32.0),
      );

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AppCard(
              radius: 10.0, // Should be ignored when borderRadius is supplied
              borderRadius: customBorderRadius,
              child: Text('Asymmetrical Card'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final containerFinder = find
          .ancestor(
            of: find.text('Asymmetrical Card'),
            matching: find.byType(Container),
          )
          .first;

      final decoration = (tester.widget<Container>(containerFinder).decoration
          as BoxDecoration);
      expect(decoration.borderRadius, equals(customBorderRadius));
    });

    testWidgets('AppCard: borderRadius: BorderRadius.zero produces sharp edges',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AppCard(
              borderRadius: BorderRadius.zero,
              child: Text('Zero Radius Card'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final containerFinder = find
          .ancestor(
            of: find.text('Zero Radius Card'),
            matching: find.byType(Container),
          )
          .first;

      final decoration = (tester.widget<Container>(containerFinder).decoration
          as BoxDecoration);
      expect(decoration.borderRadius, equals(BorderRadius.zero));
    });

    testWidgets('AppCard: onTap wraps card in PressScale and handles touch',
        (tester) async {
      bool tapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppCard(
              onTap: () => tapped = true,
              child: const Text('Tappable Card'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byType(PressScale), findsOneWidget);
      final pressScale = tester.widget<PressScale>(find.byType(PressScale));
      expect(pressScale.pressedScale, equals(0.98));

      await tester.tap(find.text('Tappable Card'));
      await tester.pump();
      expect(tapped, isTrue);
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
