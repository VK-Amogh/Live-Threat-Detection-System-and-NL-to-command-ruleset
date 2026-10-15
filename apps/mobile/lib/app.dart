import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'core/api_client.dart';
import 'core/auth_store.dart';
import 'core/theme/tokens.dart';
import 'core/widgets/fade_scrim.dart';
import 'core/widgets/floating_nav_pill.dart';
import 'core/ws_client.dart';
import 'data/generated/models.dart';
import 'data/repositories/chat_repository.dart';
import 'data/repositories/events_repository.dart';
import 'features/chat/chat_screen.dart';
import 'features/incidents/incidents_screen.dart';
import 'features/pairing/pairing_screen.dart';
import 'features/status/status_screen.dart';
import 'services/notification_service.dart';

class SafeSpaceApp extends StatefulWidget {
  final AuthStore authStore;
  final ApiClient apiClient;
  final NotificationService notificationService;

  const SafeSpaceApp({
    super.key,
    required this.authStore,
    required this.apiClient,
    required this.notificationService,
  });

  @override
  State<SafeSpaceApp> createState() => _SafeSpaceAppState();
}

class _SafeSpaceAppState extends State<SafeSpaceApp> {
  late final EventsRepository _eventsRepository;
  late final ChatRepository _chatRepository;
  WebSocketService? _wsService;

  bool _isPaired = false;
  bool _isLoading = true;
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _eventsRepository = EventsRepository(widget.apiClient);
    _chatRepository = ChatRepository(widget.apiClient);
    _checkPairing();
  }

  Future<void> _checkPairing() async {
    final paired = await widget.authStore.isPaired();
    setState(() {
      _isPaired = paired;
      _isLoading = false;
    });

    if (paired) {
      _startWebSocket();
    }
  }

  void _startWebSocket() {
    _wsService?.disconnect();
    _wsService = WebSocketService(
      apiClient: widget.apiClient,
      authStore: widget.authStore,
      onEventReceived: (event, isUpdate) {
        if (!isUpdate &&
            (event.severity == Severity.HIGH || event.severity == Severity.CRITICAL)) {
          widget.notificationService.showThreatAlert(event);
        }
      },
    );
    _wsService?.connect();
  }

  void _onPaired() {
    setState(() {
      _isPaired = true;
    });
    _startWebSocket();
  }

  void _onUnpaired() {
    _wsService?.disconnect();
    _wsService = null;
    setState(() {
      _isPaired = false;
      _currentIndex = 0;
    });
  }

  @override
  void dispose() {
    _wsService?.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Edge-to-edge transparent system bars with light icons
    SystemChrome.setSystemUIOverlayStyle(
      const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.light,
        systemNavigationBarColor: Colors.transparent,
        systemNavigationBarIconBrightness: Brightness.light,
      ),
    );

    if (_isLoading) {
      return const MaterialApp(
        debugShowCheckedModeBanner: false,
        home: Scaffold(
          backgroundColor: AppColors.background,
          body: Center(
            child: CircularProgressIndicator(
              color: AppColors.foreground,
              strokeWidth: 2,
            ),
          ),
        ),
      );
    }

    final screens = [
      IncidentsScreen(eventsRepository: _eventsRepository),
      ChatScreen(chatRepository: _chatRepository),
      StatusScreen(authStore: widget.authStore, onUnpaired: _onUnpaired),
    ];

    const navItems = [
      FloatingNavItem(
        index: 0,
        icon: Icons.shield_outlined,
        selectedIcon: Icons.shield,
        label: 'Alerts',
      ),
      FloatingNavItem(
        index: 1,
        icon: Icons.chat_bubble_outline_rounded,
        selectedIcon: Icons.chat_bubble_rounded,
        label: 'Intelligence',
      ),
      FloatingNavItem(
        index: 2,
        icon: Icons.tune_outlined,
        selectedIcon: Icons.tune_rounded,
        label: 'Telemetry',
      ),
    ];

    return MaterialApp(
      title: 'SafeSpace Alert',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: AppColors.background,
        colorScheme: const ColorScheme.dark(
          primary: AppColors.foreground,
          surface: AppColors.surface,
          background: AppColors.background,
        ),
      ),
      home: !_isPaired
          ? PairingScreen(
              authStore: widget.authStore,
              apiClient: widget.apiClient,
              onPaired: _onPaired,
            )
          : Scaffold(
              backgroundColor: AppColors.background,
              body: Stack(
                fit: StackFit.expand,
                children: [
                  // Page View
                  IndexedStack(
                    index: _currentIndex,
                    children: screens,
                  ),

                  // Bottom dissolve scrim
                  const Positioned(
                    bottom: 0,
                    left: 0,
                    right: 0,
                    child: FadeScrim(height: 104),
                  ),

                  // Floating Navigation Pill
                  Positioned(
                    bottom: AppSpacing.md,
                    left: 0,
                    right: 0,
                    child: FloatingNavPill(
                      currentIndex: _currentIndex,
                      onIndexChanged: (idx) => setState(() => _currentIndex = idx),
                      items: navItems,
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
