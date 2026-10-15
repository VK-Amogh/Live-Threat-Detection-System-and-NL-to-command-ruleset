import 'package:flutter/material.dart';
import 'core/api_client.dart';
import 'core/auth_store.dart';
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
        if (!isUpdate && (event.severity == Severity.HIGH || event.severity == Severity.CRITICAL)) {
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
    if (_isLoading) {
      return const MaterialApp(
        debugShowCheckedModeBanner: false,
        home: Scaffold(
          backgroundColor: Colors.black,
          body: Center(child: CircularProgressIndicator(color: Colors.white)),
        ),
      );
    }

    return MaterialApp(
      title: 'SafeSpace Alert',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: Colors.black,
        colorScheme: const ColorScheme.dark(
          primary: Colors.white,
          surface: Color(0xFF1A1A1A),
        ),
      ),
      home: !_isPaired
          ? PairingScreen(
              authStore: widget.authStore,
              apiClient: widget.apiClient,
              onPaired: _onPaired,
            )
          : Scaffold(
              body: IndexedStack(
                index: _currentIndex,
                children: [
                  IncidentsScreen(eventsRepository: _eventsRepository),
                  ChatScreen(chatRepository: _chatRepository),
                  StatusScreen(authStore: widget.authStore, onUnpaired: _onUnpaired),
                ],
              ),
              bottomNavigationBar: Container(
                color: Colors.black,
                padding: const EdgeInsets.only(bottom: 12, top: 8),
                child: Center(
                  child: Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFF1A1A1A),
                      borderRadius: BorderRadius.circular(30),
                      border: Border.all(color: Colors.white.withOpacity(0.08)),
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        _navItem(0, Icons.shield_outlined, Icons.shield, 'Alerts'),
                        const SizedBox(width: 8),
                        _navItem(1, Icons.chat_bubble_outline, Icons.chat_bubble, 'Search'),
                        const SizedBox(width: 8),
                        _navItem(2, Icons.tune_outlined, Icons.tune, 'Status'),
                      ],
                    ),
                  ),
                ),
              ),
            ),
    );
  }

  Widget _navItem(int index, IconData unselectedIcon, IconData selectedIcon, String label) {
    final isSelected = _currentIndex == index;
    return GestureDetector(
      onTap: () => setState(() => _currentIndex = index),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? Colors.white.withOpacity(0.12) : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isSelected ? selectedIcon : unselectedIcon,
              color: isSelected ? Colors.white : Colors.white54,
              size: 20,
            ),
            if (isSelected) ...[
              const SizedBox(width: 6),
              Text(
                label,
                style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
