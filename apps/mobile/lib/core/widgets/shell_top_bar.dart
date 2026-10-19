import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/tokens.dart';
import 'app_capsule.dart';
import 'app_icon.dart';

/// ShellTopBar directly mirroring the web dashboard shell header (DESIGN.md §13.7)
/// Features:
/// 1. Clean brand badge: Shield-check icon + "SafeSpace" + device badge capsule.
/// 2. Section title capsule indicating current module.
/// 3. Subtle connection status indicator (online pulse dot + status label).
class ShellTopBar extends StatelessWidget {
  final String deviceName;
  final String sectionTitle;
  final bool isConnected;
  final String? connectionLabel;
  final VoidCallback? onTapStatus;
  final VoidCallback? onTapDevice;
  final Widget? trailing;

  const ShellTopBar({
    super.key,
    required this.deviceName,
    required this.sectionTitle,
    required this.isConnected,
    this.connectionLabel,
    this.onTapStatus,
    this.onTapDevice,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 420;
        final isVeryNarrow = constraints.maxWidth < 360;

        final statusText = connectionLabel ??
            (isConnected
                ? (isCompact ? 'Live' : 'Live feed connected')
                : (isCompact ? 'Offline' : 'Reconnecting…'));

        return Container(
          decoration: const BoxDecoration(
            color: AppColors.background,
            border: Border(
              bottom: BorderSide(color: AppColors.divider, width: 1.0),
            ),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.sm,
          ),
          child: SizedBox(
            height: AppSpacing.capsuleHeight + 8, // ~40dp content row
            child: Row(
              children: [
                // ── 1. Clean Brand Badge ──────────────────────────────
                const AppIcon(
                  'shield-check',
                  size: 20,
                  color: AppColors.foreground,
                ),
                const SizedBox(width: AppSpacing.xs),
                Text(
                  'SafeSpace',
                  style: AppTypography.cardTitle.copyWith(
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.2,
                  ),
                ),
                const SizedBox(width: AppSpacing.xs),

                // Device Badge Capsule
                Flexible(
                  child: GestureDetector(
                    onTap: onTapDevice == null
                        ? null
                        : () {
                            HapticFeedback.selectionClick();
                            onTapDevice!();
                          },
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: BorderRadius.circular(AppRadii.pill),
                        border: Border.all(
                          color: AppColors.divider,
                          width: 1.0,
                        ),
                      ),
                      child: Text(
                        deviceName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.caption.copyWith(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w500,
                          color: AppColors.foregroundSecondary,
                        ),
                      ),
                    ),
                  ),
                ),

                const SizedBox(width: AppSpacing.xs),

                // ── 2. Section Title Capsule ──────────────────────────
                if (!isVeryNarrow) ...[
                  AppCapsule(label: sectionTitle),
                  const SizedBox(width: AppSpacing.xs),
                ],

                const Spacer(),

                // ── 3. Subtle Connection Status ───────────────────────
                GestureDetector(
                  onTap: onTapStatus == null
                      ? null
                      : () {
                          HapticFeedback.selectionClick();
                          onTapStatus!();
                        },
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      AnimatedContainer(
                        duration: AppMotion.shortDuration,
                        curve: AppMotion.standardCurve,
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: isConnected
                              ? const Color(0xFF4ADE80)
                              : AppColors.foregroundDisabled,
                          boxShadow: isConnected
                              ? const [
                                  BoxShadow(
                                    color: Color(0x664ADE80),
                                    blurRadius: 4,
                                    spreadRadius: 1,
                                  ),
                                ]
                              : null,
                        ),
                      ),
                      const SizedBox(width: 5),
                      Text(
                        statusText,
                        style: AppTypography.caption.copyWith(
                          fontSize: 11,
                          fontWeight: FontWeight.w500,
                          color: isConnected
                              ? AppColors.foregroundSecondary
                              : AppColors.foregroundDisabled,
                        ),
                      ),
                    ],
                  ),
                ),

                if (trailing != null) ...[
                  const SizedBox(width: AppSpacing.sm),
                  trailing!,
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}
