import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/api_client.dart';
import 'package:safespace_mobile/core/auth_store.dart';
import 'package:safespace_mobile/core/widgets/app_card.dart';
import 'package:safespace_mobile/data/generated/models.dart';
import 'package:safespace_mobile/data/repositories/events_repository.dart';
import 'package:safespace_mobile/features/incidents/incidents_screen.dart';
import 'package:safespace_mobile/features/incidents/incident_detail_screen.dart';

class FakeAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromString('{}', 200, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

class FakeApiClient extends ApiClient {
  FakeApiClient() : super(AuthStore()) {
    dio.interceptors.clear();
    dio.httpClientAdapter = FakeAdapter();
    dio.options.connectTimeout = null;
    dio.options.receiveTimeout = null;
  }
}

class FakeEventsRepository extends EventsRepository {
  final List<EventOut> mockEvents;

  FakeEventsRepository(this.mockEvents) : super(FakeApiClient());

  @override
  Future<List<EventOut>> getEvents({int limit = 100}) async => mockEvents;

  @override
  Future<EventOut> confirmEvent(String eventId, {String? note}) async {
    return mockEvents.firstWhere((e) => e.id == eventId);
  }

  @override
  Future<EventOut> markFalsePositive(String eventId, {String? note}) async {
    return mockEvents.firstWhere((e) => e.id == eventId);
  }
}

EventOut createTestEvent({
  String id = 'ev-1',
  Severity severity = Severity.CRITICAL,
  EventStatus status = EventStatus.NEEDS_REVIEW,
}) {
  return EventOut(
    id: id,
    camera: CameraRef(id: 'cam-1', name: 'Driveway South'),
    category: CategoryRef(key: 'WEAPON', label: 'Weapon detected'),
    status: status,
    verifiedBy: VerifiedBy.NONE,
    aiDisagrees: false,
    severity: severity,
    yoloConfidence: 0.94,
    peakConfidence: 0.96,
    summary:
        'A person carrying a suspicious object was detected in driveway zone.',
    firstSeenAt: '2026-10-17T00:20:00Z',
    lastSeenAt: '2026-10-17T00:20:10Z',
    trackRefs: [],
    media: [
      MediaItemOut(
        id: 'med-1',
        kind: MediaKind.CLIP,
        role: 'evidence_clip',
        url: '/api/v1/media/clip1.mp4',
        width: 1920,
        height: 1080,
        offsetMs: 500,
      ),
    ],
    changeSeq: 1,
    createdAt: '2026-10-17T00:20:00Z',
    updatedAt: '2026-10-17T00:20:10Z',
  );
}

void main() {
  testWidgets('History renders two equal-sized summary cards', (tester) async {
    final event = createTestEvent();
    final repo = FakeEventsRepository([event]);

    await tester.pumpWidget(
      MaterialApp(
        home: IncidentsScreen(eventsRepository: repo),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));

    expect(find.text('History'), findsOneWidget);
    expect(find.text('Needs review'), findsOneWidget);
    expect(find.text('Events'), findsWidgets);

    final statCards =
        tester.widgetList<AppCard>(find.byType(AppCard)).take(2).toList();
    expect(statCards.length, 2);

    final awaitingCardRect = tester.getRect(find
        .ancestor(
          of: find.text('Needs review'),
          matching: find.byType(AppCard),
        )
        .first);

    final totalCardRect = tester.getRect(find
        .ancestor(
          of: find.text('Events').first,
          matching: find.byType(AppCard),
        )
        .first);

    expect(awaitingCardRect.width, closeTo(totalCardRect.width, 1.0));
    expect(awaitingCardRect.height, closeTo(totalCardRect.height, 1.0));
  });

  testWidgets(
      'IncidentDetailScreen renders 16:9 stage and equal-width action buttons at bottom',
      (tester) async {
    final event = createTestEvent();
    final repo = FakeEventsRepository([event]);

    await tester.pumpWidget(
      MaterialApp(
        home: IncidentDetailScreen(
          event: event,
          eventsRepository: repo,
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // Verify action buttons exist
    final falsePositiveBtn = find.text('False positive');
    final confirmThreatBtn = find.text('Confirm threat');

    expect(falsePositiveBtn, findsOneWidget);
    expect(confirmThreatBtn, findsOneWidget);

    // Verify both action buttons have equal widths
    final fpRect = tester.getRect(find
        .ancestor(
          of: falsePositiveBtn,
          matching: find.byType(GestureDetector),
        )
        .first);

    final ctRect = tester.getRect(find
        .ancestor(
          of: confirmThreatBtn,
          matching: find.byType(GestureDetector),
        )
        .first);

    expect(fpRect.width, closeTo(ctRect.width, 1.0));

    // Verify 16:9 AspectRatio widget is present for media
    final aspectRatios =
        tester.widgetList<AspectRatio>(find.byType(AspectRatio));
    final has16by9 =
        aspectRatios.any((ar) => (ar.aspectRatio - (16 / 9)).abs() < 0.01);
    expect(has16by9, isTrue);
  });
}
