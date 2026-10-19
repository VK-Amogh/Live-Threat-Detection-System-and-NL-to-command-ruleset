import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:safespace_mobile/core/api_client.dart';
import 'package:safespace_mobile/core/auth_store.dart';
import 'package:safespace_mobile/core/net/route_manager.dart';
import 'package:safespace_mobile/core/widgets/evidence_media.dart';
import 'package:safespace_mobile/data/repositories/chat_repository.dart';
import 'package:safespace_mobile/features/chat/chat_screen.dart';
import 'package:safespace_mobile/features/status/status_screen.dart';

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
    dio.httpClientAdapter = FakeAdapter();
  }
}

class FakeChatRepository extends ChatRepository {
  FakeChatRepository() : super(FakeApiClient());

  @override
  Future<List<ChatConversation>> listConversations() async => [];

  @override
  Stream<ChatMessage> ask(String prompt, {String? conversationId}) {
    return Stream.value(ChatMessage(text: 'Test response', isUser: false));
  }
}

void main() {
  testWidgets('EvidenceMedia strictly enforces 16:9 aspect ratio',
      (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 320,
              child: EvidenceMedia(
                url: 'http://localhost/test.mp4',
                video: true,
              ),
            ),
          ),
        ),
      ),
    );

    final aspectFinder = find.descendant(
      of: find.byType(EvidenceMedia),
      matching: find.byType(AspectRatio),
    );
    expect(aspectFinder, findsWidgets);

    final aspectRatioWidget = tester.widget<AspectRatio>(aspectFinder.first);
    expect(aspectRatioWidget.aspectRatio, closeTo(16 / 9, 0.001));
  });

  testWidgets('ChatScreen renders a simple conversation and composer',
      (tester) async {
    final chatRepo = FakeChatRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ChatScreen(chatRepository: chatRepo),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('What would you like to know?'), findsOneWidget);
    expect(find.text('Summarize recent incident'), findsNothing);
    expect(find.byType(TextField), findsOneWidget);
  });

  testWidgets('StatusScreen renders large activity metrics', (tester) async {
    final authStore = AuthStore();
    final fakeApi = FakeApiClient();
    final routes = RouteManager(authStore, dio: fakeApi.dio);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StatusScreen(
            authStore: authStore,
            routes: routes,
            apiClient: fakeApi,
            onUnpaired: () {},
            onSwitchMode: () {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('System'), findsOneWidget);
    expect(find.text('Activity'), findsOneWidget);
    expect(find.text('Events'), findsOneWidget);
    expect(find.text('Review'), findsOneWidget);
  });
}
