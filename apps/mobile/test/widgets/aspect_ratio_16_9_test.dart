import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/api_client.dart';
import 'package:safespace_mobile/core/auth_store.dart';
import 'package:safespace_mobile/core/net/route_manager.dart';
import 'package:safespace_mobile/core/widgets/app_capsule.dart';
import 'package:safespace_mobile/core/widgets/evidence_media.dart';
import 'package:safespace_mobile/data/generated/models.dart';
import 'package:safespace_mobile/data/repositories/events_repository.dart';
import 'package:safespace_mobile/features/cameras/camera_station_screen.dart';
import 'package:safespace_mobile/features/cameras/live_cameras_screen.dart';
import 'package:safespace_mobile/features/incidents/incident_detail_screen.dart';
import 'package:safespace_mobile/features/incidents/incidents_screen.dart';
import 'package:safespace_mobile/services/session_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

class FakeHttpClientAdapter implements HttpClientAdapter {
  final List<Map<String, dynamic>> mockCameras;
  final List<Map<String, dynamic>> mockEvents;

  FakeHttpClientAdapter({
    this.mockCameras = const [],
    this.mockEvents = const [],
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
    if (path.endsWith('/events') || path.endsWith('/api/v1/events')) {
      return ResponseBody.fromString(
        jsonEncode(mockEvents),
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
    List<Map<String, dynamic>> mockEvents = const [],
  }) : super(AuthStore()) {
    dio.interceptors.clear();
    dio.httpClientAdapter = FakeHttpClientAdapter(
      mockCameras: mockCameras,
      mockEvents: mockEvents,
    );
    dio.options.connectTimeout = null;
    dio.options.receiveTimeout = null;
  }
}

class FakeEventsRepository extends EventsRepository {
  final List<EventOut> mockEvents;

  FakeEventsRepository(this.mockEvents)
      : super(FakeApiClient(
            mockEvents: mockEvents.map((e) => e.toJson()).toList()));

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
  List<MediaItemOut>? media,
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
    media: media ??
        [
          MediaItemOut(
            id: 'med-1',
            kind: MediaKind.KEYFRAME,
            role: 'evidence_keyframe',
            url: '/api/v1/media/photo1.jpg',
            width: 1920,
            height: 1080,
            offsetMs: 0,
          ),
        ],
    changeSeq: 1,
    createdAt: '2026-10-17T00:20:00Z',
    updatedAt: '2026-10-17T00:20:10Z',
  );
}

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'),
      (methodCall) async => '.',
    );
  });

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({'device_token': 'test_token'});
    SharedPreferences.setMockInitialValues({
      'api_base_url': 'http://127.0.0.1:8000',
      'device_id': 'dev_phone_1',
    });
  });

  const expected16by9 = 16.0 / 9.0;

  group('Suite 4: 16:9 Aspect Ratio & Container Geometry Tests', () {
    testWidgets(
      'EvidenceMedia keyframe strictly enforces 16:9 aspect ratio across multiple widths',
      (tester) async {
        const testWidths = [320.0, 390.0, 480.0, 640.0];

        for (final width in testWidths) {
          await tester.pumpWidget(
            MaterialApp(
              theme: ThemeData.dark(),
              home: Scaffold(
                body: Center(
                  child: SizedBox(
                    width: width,
                    child: const EvidenceMedia(
                      url: '/api/v1/media/evidence_keyframe.jpg',
                      video: false,
                    ),
                  ),
                ),
              ),
            ),
          );
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 50));

          // 1. EvidenceMedia widget size check (accounting for 1px container border on all sides)
          final evidenceFinder = find.byType(EvidenceMedia);
          expect(evidenceFinder, findsOneWidget);
          final mediaSize = tester.getSize(evidenceFinder);

          final expectedOuterHeight = ((width - 2.0) * (9.0 / 16.0)) + 2.0;
          expect(mediaSize.width, closeTo(width, 0.5));
          expect(mediaSize.height, closeTo(expectedOuterHeight, 0.5));
          expect(
              mediaSize.width / mediaSize.height, closeTo(expected16by9, 0.02));

          // 2. Inner AspectRatio widget check (strictly 16:9)
          final arFinder = find
              .descendant(
                of: evidenceFinder,
                matching: find.byType(AspectRatio),
              )
              .first;
          final arWidget = tester.widget<AspectRatio>(arFinder);
          expect(arWidget.aspectRatio, closeTo(expected16by9, 1e-4));

          final innerStageSize = tester.getSize(arFinder);
          expect(innerStageSize.width / innerStageSize.height,
              closeTo(expected16by9, 1e-4));

          // 3. 16:9 Keyframe capsule check
          expect(find.text('16:9 Keyframe'), findsOneWidget);
        }
      },
    );

    testWidgets(
      'EvidenceMedia video mode strictly enforces 16:9 aspect ratio and renders 16:9 badge',
      (tester) async {
        const containerWidth = 360.0;
        const expectedOuterHeight =
            ((containerWidth - 2.0) * (9.0 / 16.0)) + 2.0;

        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.dark(),
            home: const Scaffold(
              body: Center(
                child: SizedBox(
                  width: containerWidth,
                  child: EvidenceMedia(
                    url: '/api/v1/media/clip1.mp4',
                    video: true,
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pump();

        final evidenceFinder = find.byType(EvidenceMedia);
        expect(evidenceFinder, findsOneWidget);
        final mediaSize = tester.getSize(evidenceFinder);

        expect(mediaSize.width, closeTo(containerWidth, 0.5));
        expect(mediaSize.height, closeTo(expectedOuterHeight, 0.5));
        expect(
            mediaSize.width / mediaSize.height, closeTo(expected16by9, 0.02));

        final arFinder = find
            .descendant(
              of: evidenceFinder,
              matching: find.byType(AspectRatio),
            )
            .first;
        final arWidget = tester.widget<AspectRatio>(arFinder);
        expect(arWidget.aspectRatio, closeTo(expected16by9, 1e-4));

        final innerStageSize = tester.getSize(arFinder);
        expect(innerStageSize.width / innerStageSize.height,
            closeTo(expected16by9, 1e-4));
      },
    );

    testWidgets(
      'EvidenceMedia strictly maintains 16:9 aspect ratio even in error / failure state',
      (tester) async {
        const containerWidth = 384.0;
        const expectedOuterHeight =
            ((containerWidth - 2.0) * (9.0 / 16.0)) + 2.0;

        // Foreign origin triggers security origin check failure FormatException
        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.dark(),
            home: const Scaffold(
              body: Center(
                child: SizedBox(
                  width: containerWidth,
                  child: EvidenceMedia(
                    url: 'http://malicious-external-host.com/clip.mp4',
                    video: false,
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 50));

        // Verify error text is displayed
        expect(
          find.text('Evidence could not be loaded. Check your connection.'),
          findsOneWidget,
        );

        // Verify that container STILL preserves 16:9 geometry
        final evidenceFinder = find.byType(EvidenceMedia);
        final mediaSize = tester.getSize(evidenceFinder);

        expect(mediaSize.width, closeTo(containerWidth, 0.5));
        expect(mediaSize.height, closeTo(expectedOuterHeight, 0.5));
        expect(
            mediaSize.width / mediaSize.height, closeTo(expected16by9, 0.02));

        final arFinder = find
            .descendant(
              of: evidenceFinder,
              matching: find.byType(AspectRatio),
            )
            .first;
        final arWidget = tester.widget<AspectRatio>(arFinder);
        expect(arWidget.aspectRatio, closeTo(expected16by9, 1e-4));

        final innerStageSize = tester.getSize(arFinder);
        expect(innerStageSize.width / innerStageSize.height,
            closeTo(expected16by9, 1e-4));
      },
    );

    testWidgets(
      'LiveCamerasScreen keeps the video stage at 16:9 without a capsule overlay',
      (tester) async {
        tester.view.physicalSize = const Size(800, 1400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        final mockCameras = [
          {
            'id': 'cam-focus-1',
            'name': 'Front Entrance HD',
            'is_online': true,
            'source_type': 'PHONE',
          },
        ];
        final client = FakeApiClient(mockCameras: mockCameras);

        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.dark(),
            home: Scaffold(
              body: LiveCamerasScreen(apiClient: client),
            ),
          ),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // Locate the camera feed stage's AspectRatio container
        final feedFinder = find.byType(LiveCameraFeedWidget);
        expect(feedFinder, findsOneWidget);

        final stageAspectRatioFinder = find.ancestor(
          of: feedFinder,
          matching: find.byType(AspectRatio),
        );
        expect(stageAspectRatioFinder, findsOneWidget);

        final arWidget = tester.widget<AspectRatio>(stageAspectRatioFinder);
        expect(arWidget.aspectRatio, closeTo(expected16by9, 1e-4));

        // Verify bounding box dimensions ratio
        final stageRect = tester.getRect(stageAspectRatioFinder);
        expect(
            stageRect.width / stageRect.height, closeTo(expected16by9, 1e-4));

        expect(find.widgetWithText(AppCapsule, '16:9'), findsNothing);
      },
    );

    testWidgets(
      'LiveCamerasScreen wall keeps large 16:9 video stages',
      (tester) async {
        tester.view.physicalSize = const Size(1200, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        final mockCameras = [
          {
            'id': 'cam-grid-1',
            'name': 'Gate South',
            'is_online': true,
            'source_type': 'RTSP',
          },
          {
            'id': 'cam-grid-2',
            'name': 'Perimeter West',
            'is_online': true,
            'source_type': 'RTSP',
          },
        ];
        final client = FakeApiClient(mockCameras: mockCameras);

        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.dark(),
            home: Scaffold(
              body: LiveCamerasScreen(apiClient: client),
            ),
          ),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 150));

        // Switch to wall view
        final wallBtn = find.byTooltip('All cameras wall');
        expect(wallBtn, findsOneWidget);
        await tester.tap(wallBtn);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.byType(GridView), findsNothing);
        final aspect = find.byType(AspectRatio).first;
        expect(tester.widget<AspectRatio>(aspect).aspectRatio,
            closeTo(expected16by9, 1e-4));
        await tester.drag(find.byType(ListView).first, const Offset(0, -500));
        await tester.pump();
        expect(find.text('Perimeter West'), findsWidgets);
        final nextAspect = find.byType(AspectRatio).last;
        expect(tester.widget<AspectRatio>(nextAspect).aspectRatio,
            closeTo(expected16by9, 1e-4));
      },
    );

    testWidgets(
      'CameraStationScreen live broadcast viewfinder container strictly enforces 16:9 aspect ratio',
      (tester) async {
        tester.view.physicalSize = const Size(800, 1400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        final authStore = AuthStore();
        final client = FakeApiClient();
        final routeManager = RouteManager(authStore);
        final session = SessionService(client, authStore, routeManager);

        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.dark(),
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
        await tester.pump(const Duration(milliseconds: 100));

        final viewfinderArFinder = find.byType(AspectRatio).first;
        expect(viewfinderArFinder, findsOneWidget);

        final arWidget = tester.widget<AspectRatio>(viewfinderArFinder);
        expect(arWidget.aspectRatio, closeTo(expected16by9, 1e-4));

        final viewfinderRect = tester.getRect(viewfinderArFinder);
        expect(viewfinderRect.width / viewfinderRect.height,
            closeTo(expected16by9, 1e-4));
      },
    );

    testWidgets(
      'IncidentDetailScreen evidence stage strictly enforces 16:9 aspect ratio with and without media',
      (tester) async {
        tester.view.physicalSize = const Size(800, 1400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        // 1. With media: verifies 16:9 EvidenceMedia stage
        final eventWithMedia = createTestEvent(
          id: 'ev-media-1',
          media: [
            MediaItemOut(
              id: 'med-photo-1',
              kind: MediaKind.KEYFRAME,
              role: 'evidence_keyframe',
              url: '/api/v1/media/test_keyframe.jpg',
              width: 1920,
              height: 1080,
            ),
          ],
        );
        final repoWithMedia = FakeEventsRepository([eventWithMedia]);

        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.dark(),
            home: IncidentDetailScreen(
              event: eventWithMedia,
              eventsRepository: repoWithMedia,
            ),
          ),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        final evidenceFinder = find.byType(EvidenceMedia);
        expect(evidenceFinder, findsOneWidget);
        final mediaSize = tester.getSize(evidenceFinder);
        expect(
            mediaSize.width / mediaSize.height, closeTo(expected16by9, 0.02));

        final innerAr = tester.widget<AspectRatio>(
          find
              .descendant(
                of: evidenceFinder,
                matching: find.byType(AspectRatio),
              )
              .first,
        );
        expect(innerAr.aspectRatio, closeTo(expected16by9, 1e-4));

        // 2. Without media fallback: verifies 16:9 AspectRatio container
        final eventWithoutMedia = createTestEvent(
          id: 'ev-nomedia-1',
          media: [],
        );
        final repoWithoutMedia = FakeEventsRepository([eventWithoutMedia]);

        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.dark(),
            home: IncidentDetailScreen(
              event: eventWithoutMedia,
              eventsRepository: repoWithoutMedia,
            ),
          ),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        final fallbackArList =
            tester.widgetList<AspectRatio>(find.byType(AspectRatio));
        final fallback16by9 = fallbackArList.where(
          (ar) => (ar.aspectRatio - expected16by9).abs() < 1e-4,
        );
        expect(fallback16by9, isNotEmpty);
      },
    );

    testWidgets(
      'History shows the latest video in a 16:9 card',
      (tester) async {
        tester.view.physicalSize = const Size(800, 1400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        final eventWithClip = createTestEvent(
          id: 'ev-clip-1',
          media: [
            MediaItemOut(
              id: 'med-clip-1',
              kind: MediaKind.CLIP,
              role: 'evidence_clip',
              url: '/api/v1/media/incident_clip.mp4',
              width: 1920,
              height: 1080,
              offsetMs: 250,
            ),
          ],
        );
        final repo = FakeEventsRepository([eventWithClip]);

        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.dark(),
            home: Scaffold(
              body: IncidentsScreen(eventsRepository: repo),
            ),
          ),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.text('Latest video'), findsOneWidget);
        final playerEvidenceFinder = find.byType(EvidenceMedia);
        expect(playerEvidenceFinder, findsOneWidget);

        final playerSize = tester.getSize(playerEvidenceFinder);
        expect(
            playerSize.width / playerSize.height, closeTo(expected16by9, 0.02));

        final playerAr = tester.widget<AspectRatio>(find
            .descendant(
              of: playerEvidenceFinder,
              matching: find.byType(AspectRatio),
            )
            .first);
        expect(playerAr.aspectRatio, closeTo(expected16by9, 1e-4));
      },
    );
  });
}
