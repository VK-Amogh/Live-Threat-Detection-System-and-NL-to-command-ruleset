import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'core/api_client.dart';
import 'core/auth_store.dart';
import 'core/config.dart';
import 'core/theme/tokens.dart';
import 'core/widgets/app_icon.dart';
import 'core/widgets/floating_nav_pill.dart';
import 'core/net/route_manager.dart';
import 'core/ws_client.dart';
import 'data/repositories/chat_repository.dart';
import 'data/repositories/events_repository.dart';
import 'data/repositories/rules_repository.dart';
import 'features/chat/chat_screen.dart';
import 'features/incidents/incidents_screen.dart';
import 'features/pairing/pairing_screen.dart';
import 'features/status/status_screen.dart';
import 'features/cameras/camera_station_screen.dart';
import 'features/cameras/live_cameras_screen.dart';
import 'features/rules/rules_screen.dart';
import 'services/link_service.dart';
import 'services/notification_service.dart';
import 'services/session_service.dart';

class SafeSpaceApp extends StatefulWidget {
  final AuthStore authStore;
  final ApiClient apiClient;
  final NotificationService notificationService;
  final RouteManager routes;
  final LinkService links;
  final SessionService session;

  const SafeSpaceApp({
    super.key,
    required this.authStore,
    required this.apiClient,
    required this.notificationService,
    required this.routes,
    required this.links,
    required this.session,
  });

  @override
  State<SafeSpaceApp> createState() => _SafeSpaceAppState();
}

class _SafeSpaceAppState extends State<SafeSpaceApp> {
  late final EventsRepository _eventsRepository;
  late final ChatRepository _chatRepository;
  late final RulesRepository _rulesRepository;
  WebSocketService? _wsService;

  bool _isPaired = false;
  bool _isLoading = true;
  int _currentIndex = 0;
  String? _mode;
  String? _rulesCameraId;

  @override
  void initState() {
    super.initState();
    widget.routes.addListener(_syncAlertService);
    _eventsRepository = EventsRepository(widget.apiClient);
    _chatRepository = ChatRepository(widget.apiClient);
    _rulesRepository = RulesRepository(widget.apiClient);
    _checkPairing();
  }

  Future<void> _checkPairing() async {
    var paired = false;
    String? savedMode;

    try {
      paired = await widget.authStore.isPaired();
      savedMode = (await SharedPreferences.getInstance())
          .getString(AppConfig.keyPhoneMode);
      if (paired) {
        // Find the laptop first (hotspot, remembered address, discovery), then ask whether our token is still good.
        // Only a 401 means "signed out"; an unreachable laptop must not log anyone out.
        try {
          await widget.routes.resolve().timeout(const Duration(seconds: 4));
        } catch (_) {}

        try {
          final scope = await widget.authStore.getScope();
          await widget.apiClient.dio.get(
            scope == 'camera' ? '/api/v1/devices/me' : '/api/v1/auth/me',
            options: Options(
              receiveTimeout: const Duration(seconds: 4),
              sendTimeout: const Duration(seconds: 4),
            ),
          );
        } on DioException catch (e) {
          if (e.response?.statusCode == 401) paired = false;
        } catch (_) {}
      }
    } catch (e, st) {
      debugPrint('[Init] _checkPairing error: $e\n$st');
    } finally {
      if (mounted) {
        setState(() {
          _isPaired = paired;
          _mode =
              savedMode == 'admin' || savedMode == 'camera' ? savedMode : null;
          _isLoading = false;
        });
        widget.routes.startMonitoring();
        if (paired) {
          _syncAlertService();
          widget.authStore.getScope().then((scope) {
            if (scope == 'admin') _startWebSocket();
          }).catchError((_) {});
        } else {
          widget.notificationService.stopAlertMonitor().catchError((_) {});
        }
      }
    }
  }

  void _startWebSocket() {
    _wsService?.disconnect();
    _wsService = WebSocketService(
      apiClient: widget.apiClient,
      authStore: widget.authStore,
      onEventReceived: (event, isUpdate) {
        debugPrint(
            '[Alert] ${event.id}: ${event.category.key}, update=$isUpdate');
        _eventsRepository.invalidate();
        // Android's foreground service owns notifications, including while this UI is closed.
      },
    );
    _wsService?.connect();
  }

  void _syncAlertService() {
    widget.notificationService
        .startAlertMonitor(widget.authStore, widget.routes)
        .catchError((error) => debugPrint('[Alert] Monitor failed: $error'));
  }

  Future<void> _onPaired() async {
    final savedMode = (await SharedPreferences.getInstance())
        .getString(AppConfig.keyPhoneMode);
    if (!mounted) return;
    setState(() {
      _isPaired = true;
      _mode = savedMode == 'admin' || savedMode == 'camera' ? savedMode : null;
    });
    if ((await widget.authStore.getScope()) == 'admin') _startWebSocket();
    _syncAlertService();
  }

  void _onUnpaired() {
    widget.notificationService.stopAlertMonitor().catchError((_) {});
    _wsService?.disconnect();
    _wsService = null;
    setState(() {
      _isPaired = false;
      _currentIndex = 0;
      _mode = null;
    });
  }

  Future<void> _setMode(String mode) async {
    await (await SharedPreferences.getInstance())
        .setString('safespace_phone_mode', mode);
    if (mounted) {
      setState(() {
        _mode = mode;
        _currentIndex = 0;
      });
    }
  }

  Future<void> _openRulesFor(String cameraId) async {
    await (await SharedPreferences.getInstance())
        .setString('safespace_phone_mode', 'admin');
    if (mounted) {
      setState(() {
        _mode = 'admin';
        _rulesCameraId = cameraId;
        _currentIndex = 2;
      });
    }
  }

  @override
  void dispose() {
    widget.routes.removeListener(_syncAlertService);
    _wsService?.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
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
      LiveCamerasScreen(
          apiClient: widget.apiClient, onCreateRules: _openRulesFor),
      RulesScreen(
          repository: _rulesRepository, initialCameraId: _rulesCameraId),
      ChatScreen(chatRepository: _chatRepository),
      StatusScreen(
        authStore: widget.authStore,
        routes: widget.routes,
        apiClient: widget.apiClient,
        notificationService: widget.notificationService,
        onUnpaired: _onUnpaired,
        onSwitchMode: () => _setMode('camera'),
      ),
    ];

    const navItems = [
      FloatingNavItem(
        index: 0,
        svgAsset: 'shield-01',
        icon: Icons.shield_outlined,
        selectedIcon: Icons.shield,
        label: 'History',
      ),
      FloatingNavItem(
        index: 1,
        svgAsset: 'video-on',
        icon: Icons.video_camera_back_outlined,
        selectedIcon: Icons.video_camera_back,
        label: 'Cameras',
      ),
      FloatingNavItem(
        index: 2,
        svgAsset: 'shield-check',
        icon: Icons.rule_outlined,
        selectedIcon: Icons.rule,
        label: 'Rules',
      ),
      FloatingNavItem(
        index: 3,
        svgAsset: 'search-01',
        icon: Icons.chat_bubble_outline_rounded,
        selectedIcon: Icons.chat_bubble_rounded,
        label: 'Ask',
      ),
      FloatingNavItem(
        index: 4,
        svgAsset: 'server-01',
        icon: Icons.tune_outlined,
        selectedIcon: Icons.tune_rounded,
        label: 'System',
      ),
    ];

    return MaterialApp(
      title: 'SafeSpace',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: AppColors.background,
        canvasColor: AppColors.surface,
        splashColor: AppColors.highlight,
        highlightColor: AppColors.highlight,
        dividerColor: AppColors.divider,
        colorScheme: const ColorScheme.dark(
          primary: AppColors.foreground,
          onPrimary: AppColors.background,
          secondary: AppColors.foreground,
          onSecondary: AppColors.background,
          surface: AppColors.surface,
          onSurface: AppColors.foreground,
        ),
        textSelectionTheme: const TextSelectionThemeData(
          cursorColor: AppColors.foreground,
          selectionColor: AppColors.highlight,
          selectionHandleColor: AppColors.foreground,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: AppColors.background,
          hintStyle: AppTypography.body.copyWith(
            color: AppColors.foregroundDisabled,
          ),
          labelStyle: AppTypography.caption.copyWith(
            color: AppColors.foregroundSecondary,
          ),
          contentPadding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.md,
          ),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppRadii.lg),
            borderSide: const BorderSide(color: AppColors.divider, width: 1.0),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppRadii.lg),
            borderSide: const BorderSide(color: AppColors.divider, width: 1.0),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppRadii.lg),
            borderSide: const BorderSide(
              color: AppColors.foreground,
              width: 1.5,
            ),
          ),
        ),
        bottomSheetTheme: const BottomSheetThemeData(
          backgroundColor: AppColors.surface,
          modalBackgroundColor: AppColors.surface,
          modalBarrierColor: AppColors.scrim,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(
              top: Radius.circular(AppRadii.dialog),
            ),
          ),
        ),
      ),
      home: !_isPaired
          ? PairingScreen(
              session: widget.session,
              routes: widget.routes,
              links: widget.links,
              onPaired: _onPaired,
            )
          : _mode == null
              ? Scaffold(
                  backgroundColor: AppColors.background,
                  body: SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.xl),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          const Spacer(),
                          Align(
                            alignment: Alignment.centerLeft,
                            child: AnimatedBuilder(
                              animation: widget.routes,
                              builder: (_, __) => Icon(
                                Icons.circle,
                                size: 14,
                                color: widget.routes.active?.ok == true
                                    ? const Color(0xFF38C878)
                                    : const Color(0xFFE65757),
                              ),
                            ),
                          ),
                          const SizedBox(height: AppSpacing.lg),
                          Text(
                            'Choose a mode',
                            style: AppTypography.screenTitle,
                          ),
                          const SizedBox(height: AppSpacing.xl),
                          _modeCard(
                            'grid-01',
                            'Monitor',
                            'Cameras, rules, history and Ask.',
                            () => _setMode('admin'),
                          ),
                          const SizedBox(height: AppSpacing.md),
                          _modeCard(
                            'video-on',
                            'Camera station',
                            'Use this phone as a camera.',
                            () => _setMode('camera'),
                          ),
                          const Spacer(),
                        ],
                      ),
                    ),
                  ),
                )
              : _mode == 'camera'
                  ? CameraStationScreen(
                      apiClient: widget.apiClient,
                      authStore: widget.authStore,
                      routes: widget.routes,
                      session: widget.session,
                      onSwitchMode: () => _setMode('admin'),
                      onCreateRules: _openRulesFor,
                    )
                  : Scaffold(
                      backgroundColor: AppColors.background,
                      body: SafeArea(
                        child: Column(
                          children: [
                            Expanded(
                              child: IndexedStack(
                                index: _currentIndex,
                                children: screens,
                              ),
                            ),
                            Container(
                              decoration: const BoxDecoration(
                                color: AppColors.background,
                                border: Border(
                                    top: BorderSide(color: AppColors.divider)),
                              ),
                              padding: const EdgeInsets.fromLTRB(8, 6, 8, 6),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: FloatingNavPill(
                                      currentIndex: _currentIndex,
                                      onIndexChanged: (idx) =>
                                          setState(() => _currentIndex = idx),
                                      items: navItems,
                                    ),
                                  ),
                                  AnimatedBuilder(
                                    animation: widget.routes,
                                    builder: (context, _) {
                                      final connected =
                                          widget.routes.active?.ok == true;
                                      return IconButton(
                                        tooltip: connected
                                            ? 'Connected'
                                            : 'Disconnected',
                                        onPressed: () =>
                                            setState(() => _currentIndex = 4),
                                        icon: Icon(
                                          Icons.circle,
                                          size: 12,
                                          color: connected
                                              ? const Color(0xFF38C878)
                                              : const Color(0xFFE65757),
                                        ),
                                      );
                                    },
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
    );
  }

  Widget _modeCard(
    String svgIcon,
    String title,
    String detail,
    VoidCallback onTap,
  ) =>
      GestureDetector(
        onTap: () {
          HapticFeedback.selectionClick();
          onTap();
        },
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.xl),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(AppRadii.card),
            border: Border.all(color: AppColors.divider),
          ),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: AppColors.highlight,
                  borderRadius: BorderRadius.circular(AppRadii.pill),
                  border: Border.all(color: AppColors.divider),
                ),
                child: Center(
                  child:
                      AppIcon(svgIcon, size: 22, color: AppColors.foreground),
                ),
              ),
              const SizedBox(width: AppSpacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: AppTypography.cardHeading),
                    const SizedBox(height: AppSpacing.xs),
                    Text(detail, style: AppTypography.support),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              const AppIcon(
                'chevron-right',
                size: 20,
                color: AppColors.foregroundSecondary,
              ),
            ],
          ),
        ),
      );
}
