import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/api_client.dart';
import 'package:safespace_mobile/core/auth_store.dart';
import 'package:safespace_mobile/core/net/route_manager.dart';
import 'package:safespace_mobile/core/theme/tokens.dart';
import 'package:safespace_mobile/core/widgets/app_card.dart';
import 'package:safespace_mobile/data/generated/models.dart';
import 'package:safespace_mobile/data/repositories/events_repository.dart';
import 'package:safespace_mobile/features/cameras/live_cameras_screen.dart';
import 'package:safespace_mobile/features/incidents/incidents_screen.dart';
import 'package:safespace_mobile/features/status/status_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

class FakeHttpClientAdapter implements HttpClientAdapter {
  final List<Map<String, dynamic>> mockCameras;
  final Map<String, dynamic>? mockSystem;

  FakeHttpClientAdapter({
    this.mockCameras = const [],
    this.mockSystem,
  });

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final path = options.path;
    if (path.endsWith('/cameras') || path.endsWith('/api/v1/cameras')) {
      return ResponseBody.fromString(
        jsonEncode(mockCameras),
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType]
        },
      );
    }
    if (path.contains('/system')) {
      return ResponseBody.fromString(
        jsonEncode(mockSystem ??
            {
              'mode': 'HOME',
              'counts': {
                'incidents': 12,
                'needs_review': 4,
                'confirmed': 8,
                'cameras_online': 2,
              },
            }),
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType]
        },
      );
    }
    return ResponseBody.fromString('{}', 200, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

class FakeApiClient extends ApiClient {
  FakeApiClient({
    List<Map<String, dynamic>> mockCameras = const [],
    Map<String, dynamic>? mockSystem,
  }) : super(AuthStore()) {
    dio.interceptors.clear();
    dio.httpClientAdapter = FakeHttpClientAdapter(
      mockCameras: mockCameras,
      mockSystem: mockSystem,
    );
    dio.options.connectTimeout = null;
    dio.options.receiveTimeout = null;
  }
}

class FakeEventsRepository extends EventsRepository {
  final List<EventOut> mockEvents;

  FakeEventsRepository(this.mockEvents) : super(FakeApiClient());

  @override
  Future<List<EventOut>> getEvents({int limit = 100}) async => mockEvents;
}

EventOut _buildTestEvent({
  required String id,
  required String categoryLabel,
  required String cameraName,
  Severity severity = Severity.CRITICAL,
  EventStatus status = EventStatus.NEEDS_REVIEW,
}) {
  return EventOut(
    id: id,
    camera: CameraRef(id: 'cam-$id', name: cameraName),
    category: CategoryRef(key: 'THREAT', label: categoryLabel),
    status: status,
    verifiedBy: VerifiedBy.NONE,
    aiDisagrees: false,
    severity: severity,
    yoloConfidence: 0.92,
    peakConfidence: 0.95,
    summary: 'Detected $categoryLabel on $cameraName with high confidence.',
    firstSeenAt: '2026-10-17T00:30:00Z',
    lastSeenAt: '2026-10-17T00:30:15Z',
    trackRefs: const [],
    media: [
      MediaItemOut(
        id: 'med-$id',
        kind: MediaKind.KEYFRAME,
        role: 'evidence_frame',
        url: '/api/v1/media/frame_$id.jpg',
        width: 1920,
        height: 1080,
        offsetMs: 250,
      ),
    ],
    changeSeq: 1,
    createdAt: '2026-10-17T00:30:00Z',
    updatedAt: '2026-10-17T00:30:15Z',
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('safespace/screen'),
      (call) async => null,
    );
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('safespace/device'),
      (call) async => {
        'battery_pct': 90,
        'charging': false,
        'temp_c': 31.0,
        'wifi_rssi': -60,
      },
    );
  });

  group('Large metric and video card geometry', () {
    testWidgets('System activity metrics have equal size', (tester) async {
      final authStore = AuthStore();
      final routeManager = RouteManager(authStore);
      await tester.pumpWidget(MaterialApp(
        home: StatusScreen(
          authStore: authStore,
          routes: routeManager,
          onUnpaired: () {},
          onSwitchMode: () {},
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 150));
      final labels = ['Events', 'Review', 'Confirmed', 'Cameras'];
      final cards = labels
          .map((label) => find
              .ancestor(of: find.text(label), matching: find.byType(AppCard))
              .first)
          .toList();
      final first = tester.getSize(cards.first);
      for (final card in cards.skip(1)) {
        final size = tester.getSize(card);
        expect(size.width, closeTo(first.width, 1));
        expect(size.height, closeTo(first.height, 1));
      }
    });

    testWidgets('Camera wall uses full-width video stages', (tester) async {
      final client = FakeApiClient(mockCameras: [
        {
          'id': 'cam-1',
          'name': 'Cam 1',
          'is_online': true,
          'source_type': 'PHONE'
        },
        {
          'id': 'cam-2',
          'name': 'Cam 2',
          'is_online': true,
          'source_type': 'RTSP'
        },
      ]);
      await tester.pumpWidget(MaterialApp(
        home: LiveCamerasScreen(apiClient: client),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 150));
      await tester.tap(find.byTooltip('All cameras wall'));
      await tester.pump();
      final firstStage = find.byType(AspectRatio).first;
      final first = tester.getSize(firstStage);
      expect(first.width / first.height, closeTo(16 / 9, 0.01));
      await tester.drag(find.byType(ListView).first, const Offset(0, -400));
      await tester.pump();
      expect(find.text('Cam 2'), findsWidgets);
      final second = tester.getSize(find.byType(AspectRatio).last);
      expect(second.width, closeTo(first.width, 1));
      expect(second.height, closeTo(first.height, 1));
    });
  });
  group('Alerts Screen Event Card Padding & Margins', () {
    testWidgets(
        'event cards maintain equal horizontal margins, equal widths, and uniform padding',
        (tester) async {
      await tester.binding.setSurfaceSize(const Size(800, 1400));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      final events = [
        _buildTestEvent(
          id: 'ev-1',
          categoryLabel: 'Intrusion Alert',
          cameraName: 'Gate East',
          severity: Severity.CRITICAL,
        ),
        _buildTestEvent(
          id: 'ev-2',
          categoryLabel: 'Weapon Detected',
          cameraName: 'Loading Dock',
          severity: Severity.CRITICAL,
        ),
      ];

      final repo = FakeEventsRepository(events);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: IncidentsScreen(eventsRepository: repo),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final eventCardFinder = [
        find
            .ancestor(
                of: find.text('Intrusion Alert'),
                matching: find.byType(AppCard))
            .first,
        find
            .ancestor(
                of: find.text('Weapon Detected'),
                matching: find.byType(AppCard))
            .first,
      ];

      final rects = <Rect>[];
      for (final cardFinder in eventCardFinder) {
        final cardWidget = tester.widget<AppCard>(cardFinder);
        final rect = tester.getRect(cardFinder);
        rects.add(rect);

        expect(cardWidget.padding, equals(const EdgeInsets.all(AppSpacing.md)));
      }

      // Verify all cards have equal width
      final firstWidth = rects[0].width;
      for (final r in rects) {
        expect(r.width, equals(firstWidth));
        // Verify equal horizontal left margin matches AppSpacing.lg (16dp)
        expect(r.left, equals(AppSpacing.lg));
      }
    });
  });
}
