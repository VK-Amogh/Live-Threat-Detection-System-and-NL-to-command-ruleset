import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/theme/tokens.dart';
import 'package:safespace_mobile/core/widgets/app_button.dart';
import 'package:safespace_mobile/core/widgets/glass_surface.dart';
import 'package:safespace_mobile/data/generated/models.dart';

void main() {
  test('EventOut model deserialization test', () {
    const rawJson = '''{
      "id": "0b6f7c1e-5d0a-4c3e-9d57-2d8a6c1f9a10",
      "camera": {"id": "c2d1b0a4", "name": "Webcam 1"},
      "category": {"key": "WEAPON_DETECTED", "label": "Weapon detected"},
      "status": "NEEDS_REVIEW",
      "status_reason": "vlm_uncertain",
      "verified_by": "NONE",
      "ai_disagrees": false,
      "severity": "HIGH",
      "yolo_confidence": 0.82,
      "peak_confidence": 0.91,
      "summary": "Weapon visible",
      "first_seen_at": "2026-10-15T10:21:02.912Z",
      "last_seen_at": "2026-10-15T10:21:04.512Z",
      "media_offset_ms": null,
      "track_refs": [{"track_id": 12, "class": "knife"}],
      "media": [],
      "change_seq": 1043,
      "created_at": "2026-10-15T10:21:04.600Z",
      "updated_at": "2026-10-15T10:21:13.140Z"
    }''';

    final data = jsonDecode(rawJson) as Map<String, dynamic>;
    final event = EventOut.fromJson(data);

    expect(event.id, '0b6f7c1e-5d0a-4c3e-9d57-2d8a6c1f9a10');
    expect(event.severity, Severity.HIGH);
    expect(event.status, EventStatus.NEEDS_REVIEW);
    expect(event.trackRefs.length, 1);
    expect(event.trackRefs.first.className, 'knife');
  });

  testWidgets('GlassSurface and AppButton render conforming to DESIGN.md tokens',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GlassSurface(
            child: AppButton(
              label: 'Test Button',
              onPressed: () {},
            ),
          ),
        ),
      ),
    );

    expect(find.text('Test Button'), findsOneWidget);
    expect(find.byType(GlassSurface), findsOneWidget);
    expect(find.byType(AppButton), findsOneWidget);
    expect(AppColors.background, const Color(0xFF000000));
    expect(AppColors.surface, const Color(0xFF1A1A1A));
    expect(AppColors.foreground, const Color(0xFFFFFFFF));
  });
}
