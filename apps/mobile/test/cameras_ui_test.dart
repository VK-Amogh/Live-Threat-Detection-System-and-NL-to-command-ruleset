import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/api_client.dart';
import 'package:safespace_mobile/core/auth_store.dart';
import 'package:safespace_mobile/core/net/route_manager.dart';
import 'package:safespace_mobile/features/cameras/camera_station_screen.dart';
import 'package:safespace_mobile/features/cameras/live_cameras_screen.dart';
import 'package:safespace_mobile/services/session_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

class FakeCamerasAdapter implements HttpClientAdapter {
  final List<Map<String, dynamic>> mockCameras;

  FakeCamerasAdapter(this.mockCameras);

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (options.path.endsWith('/cameras') ||
        options.path.endsWith('/api/v1/cameras')) {
      return ResponseBody.fromString(
        jsonEncode(mockCameras),
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    if (options.path.contains('/system/mode')) {
      return ResponseBody.fromString(
        jsonEncode({'mode': 'HOME'}),
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
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

class FakeCamerasApiClient extends ApiClient {
  FakeCamerasApiClient(List<Map<String, dynamic>> mockCameras)
      : super(AuthStore()) {
    dio.interceptors.clear();
    dio.httpClientAdapter = FakeCamerasAdapter(mockCameras);
    dio.options.connectTimeout = null;
    dio.options.receiveTimeout = null;
  }
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
        'battery_pct': 85,
        'charging': false,
        'temp_c': 32.0,
        'wifi_rssi': -55,
      },
    );
  });

  final mockCamerasList = [
    {
      'id': 'cam-front',
      'name': 'Front Porch',
      'is_online': true,
      'source_type': 'PHONE',
    },
    {
      'id': 'cam-back',
      'name': 'Backyard Gate',
      'is_online': true,
      'source_type': 'RTSP',
    },
  ];

  testWidgets('LiveCamerasScreen renders video and separate camera metrics',
      (tester) async {
    final client = FakeCamerasApiClient(mockCamerasList);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LiveCamerasScreen(apiClient: client),
        ),
      ),
    );

    // Allow async _load to complete
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // Verify 16:9 AspectRatio widgets exist for live stage
    final aspectRatios =
        tester.widgetList<AspectRatio>(find.byType(AspectRatio));
    expect(aspectRatios, isNotEmpty);
    for (final ar in aspectRatios) {
      expect(ar.aspectRatio, closeTo(16 / 9, 0.001));
    }

    expect(find.text('Cameras'), findsWidgets);
    expect(find.text('Live'), findsOneWidget);
    expect(find.text('Front Porch'), findsWidgets);
    expect(find.text('16:9 Live Wall'), findsNothing);
  });

  testWidgets(
      'LiveCamerasScreen multi-camera wall view has equal-sized balanced tiles',
      (tester) async {
    final client = FakeCamerasApiClient(mockCamerasList);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LiveCamerasScreen(apiClient: client),
        ),
      ),
    );

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // Toggle wall view by tapping the wall grid button in header
    final gridBtn = find.byTooltip('All cameras wall');
    expect(gridBtn, findsOneWidget);
    await tester.tap(gridBtn);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    final firstTile = find.byType(AspectRatio).first;
    final firstBox = tester.getSize(firstTile);
    expect(tester.widget<AspectRatio>(firstTile).aspectRatio,
        closeTo(16 / 9, 0.001));

    await tester.drag(find.byType(ListView).first, const Offset(0, -400));
    await tester.pump();
    expect(find.text('Backyard Gate'), findsWidgets);
    final secondTile = find.byType(AspectRatio).last;
    final secondBox = tester.getSize(secondTile);
    expect(tester.widget<AspectRatio>(secondTile).aspectRatio,
        closeTo(16 / 9, 0.001));
    expect(firstBox.width, closeTo(secondBox.width, 2.0));
    expect(firstBox.height, closeTo(secondBox.height, 2.0));
  });

  testWidgets(
      'CameraStationScreen renders 16:9 broadcast viewfinder and evenly aligned header controls',
      (tester) async {
    final authStore = AuthStore();
    final client = FakeCamerasApiClient(mockCamerasList);
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
    await tester.pump(const Duration(milliseconds: 100));

    // Check strict 16:9 AspectRatio on the broadcast viewfinder
    final aspectRatios =
        tester.widgetList<AspectRatio>(find.byType(AspectRatio));
    expect(aspectRatios, isNotEmpty);
    expect(aspectRatios.first.aspectRatio, closeTo(16 / 9, 0.001));

    expect(find.text('Camera station'), findsOneWidget);
    expect(find.text('Stream'), findsOneWidget);
    expect(find.byTooltip('Exit to control center'), findsNothing);
  });
}
