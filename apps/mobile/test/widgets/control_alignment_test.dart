import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/api_client.dart';
import 'package:safespace_mobile/core/auth_store.dart';
import 'package:safespace_mobile/core/net/route_manager.dart';
import 'package:safespace_mobile/core/widgets/app_button.dart';
import 'package:safespace_mobile/core/widgets/app_dialog.dart';
import 'package:safespace_mobile/data/generated/models.dart';
import 'package:safespace_mobile/data/repositories/events_repository.dart';
import 'package:safespace_mobile/features/cameras/camera_station_screen.dart';
import 'package:safespace_mobile/features/cameras/live_cameras_screen.dart';
import 'package:safespace_mobile/features/incidents/incident_detail_screen.dart';
import 'package:safespace_mobile/services/session_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

class FakeHttpClientAdapter implements HttpClientAdapter {
  final List<Map<String, dynamic>> mockCameras;

  FakeHttpClientAdapter({this.mockCameras = const []});

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
    return ResponseBody.fromString('{}', 200, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

class FakeApiClient extends ApiClient {
  FakeApiClient({List<Map<String, dynamic>> mockCameras = const []})
      : super(AuthStore()) {
    dio.interceptors.clear();
    dio.httpClientAdapter = FakeHttpClientAdapter(mockCameras: mockCameras);
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
    summary: 'Detected $categoryLabel on $cameraName.',
    firstSeenAt: '2026-10-17T00:30:00Z',
    lastSeenAt: '2026-10-17T00:30:15Z',
    trackRefs: const [],
    media: [
      MediaItemOut(
        id: 'med-$id',
        kind: MediaKind.CLIP,
        role: 'evidence_clip',
        url: '/api/v1/media/clip_$id.mp4',
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

  group('Camera controls below video', () {
    testWidgets('LiveCamerasScreen keeps Snapshot below the video stage',
        (tester) async {
      final mockCameras = [
        {
          'id': 'cam-1',
          'name': 'Cam 1',
          'is_online': true,
          'source_type': 'PHONE',
        },
      ];
      final client = FakeApiClient(mockCameras: mockCameras);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: LiveCamerasScreen(apiClient: client),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 150));

      final video = tester.getRect(find.byType(AspectRatio).first);
      final action = tester.getRect(find.text('Snapshot'));
      expect(action.top, greaterThanOrEqualTo(video.bottom));
    });

    testWidgets(
        'CameraStationScreen recording action button pairs render equal widths on matching baselines',
        (tester) async {
      final authStore = AuthStore();
      final client = FakeApiClient();
      final routeManager = RouteManager(authStore);
      final session = SessionService(client, authStore, routeManager);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: CameraStationScreen(
              apiClient: client,
              authStore: authStore,
              routes: routeManager,
              session: session,
              onSwitchMode: () {},
              onCreateRules: (_) {},
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 150));

      // Find the secondary action button pairs below viewfinder
      final saveSnapshotBtn = find.widgetWithText(AppButton, 'Save snapshot');
      final stealthScreenBtn = find.widgetWithText(AppButton, 'Stealth screen');
      expect(saveSnapshotBtn, findsOneWidget);
      expect(stealthScreenBtn, findsOneWidget);

      final snapshotRect = tester.getRect(saveSnapshotBtn);
      final stealthRect = tester.getRect(stealthScreenBtn);

      // Verify pair 1: equal width and identical vertical baseline
      expect(snapshotRect.width, equals(stealthRect.width));
      expect(snapshotRect.top, equals(stealthRect.top));
      expect(snapshotRect.height, equals(stealthRect.height));

      // Find pair 2: Flip lens and All cameras
      final flipLensBtn = find.widgetWithText(AppButton, 'Flip lens');
      final allCamerasBtn = find.widgetWithText(AppButton, 'All cameras');
      expect(flipLensBtn, findsOneWidget);
      expect(allCamerasBtn, findsOneWidget);

      final flipRect = tester.getRect(flipLensBtn);
      final allCamRect = tester.getRect(allCamerasBtn);

      // Verify pair 2: equal width and identical vertical baseline
      expect(flipRect.width, equals(allCamRect.width));
      expect(flipRect.top, equals(allCamRect.top));
      expect(flipRect.height, equals(allCamRect.height));
    });
  });

  group('Modal Dialogs & Review Action Bars Alignment', () {
    testWidgets(
        'showAppConfirmDialog renders equal-width buttons on matching vertical baseline',
        (tester) async {
      bool? dialogResult;

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (ctx) => Scaffold(
              body: Center(
                child: ElevatedButton(
                  onPressed: () async {
                    dialogResult = await showAppConfirmDialog(
                      ctx,
                      title: 'Confirm threat?',
                      body:
                          'This will verify the incident as an active threat.',
                      confirmLabel: 'Confirm threat',
                      cancelLabel: 'Cancel',
                    );
                  },
                  child: const Text('Open Dialog'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Open the confirmation dialog
      await tester.tap(find.text('Open Dialog'));
      await tester.pumpAndSettle();

      // Find dialog action buttons
      final cancelBtn = find.widgetWithText(AppButton, 'Cancel');
      final confirmBtn = find.widgetWithText(AppButton, 'Confirm threat');
      expect(cancelBtn, findsOneWidget);
      expect(confirmBtn, findsOneWidget);

      final cancelRect = tester.getRect(cancelBtn);
      final confirmRect = tester.getRect(confirmBtn);

      // Assert strictly equal button widths
      expect(cancelRect.width, equals(confirmRect.width));

      // Assert identical vertical baseline and height
      expect(cancelRect.top, equals(confirmRect.top));
      expect(cancelRect.height, equals(confirmRect.height));

      // Tap confirm and verify proper dismissal
      await tester.tap(confirmBtn);
      await tester.pumpAndSettle();

      expect(dialogResult, isTrue);
    });

    testWidgets(
        'IncidentDetailScreen review action bar renders equal-width buttons on matching vertical baseline',
        (tester) async {
      final event = _buildTestEvent(
        id: 'ev-detail-1',
        categoryLabel: 'Intrusion Alert',
        cameraName: 'Gate East',
        status: EventStatus.NEEDS_REVIEW,
      );
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
      await tester.pump(const Duration(milliseconds: 150));

      // Find bottom review action buttons
      final falsePositiveBtn = find.widgetWithText(AppButton, 'False positive');
      final confirmThreatBtn = find.widgetWithText(AppButton, 'Confirm threat');
      expect(falsePositiveBtn, findsOneWidget);
      expect(confirmThreatBtn, findsOneWidget);

      final fpRect = tester.getRect(falsePositiveBtn);
      final ctRect = tester.getRect(confirmThreatBtn);

      // Assert strictly equal button widths (50% / 50% split)
      expect(fpRect.width, equals(ctRect.width));

      // Assert identical vertical baseline and height
      expect(fpRect.top, equals(ctRect.top));
      expect(fpRect.height, equals(ctRect.height));
    });
  });
}
