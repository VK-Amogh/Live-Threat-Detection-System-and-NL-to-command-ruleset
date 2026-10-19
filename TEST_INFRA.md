# E2E Test Infra: SafeSpace Flutter Mobile Redesign

## Test Philosophy
- Requirement-driven, opaque-box geometric and layout verification.
- Enforces Acceptance Criteria:
  1. `flutter analyze` runs in `apps/mobile` with 0 errors and 0 warnings.
  2. `flutter test` passes all test suites.
  3. Grid cards across Cameras, Alerts, and System screens maintain equal heights and proportional bounding boxes.
  4. Action buttons and control bars are centered or geometrically aligned across all screens.
  5. No visual crowding, cramped micro-boxes, or inconsistent container paddings exist.
  6. All live stream containers, recorded clips, and evidence media render in a strict 16:9 aspect ratio.

## Test Architecture
- Test runner: `flutter test` in `c:\HackHive\LTDC\apps\mobile`.
- Static analysis: `flutter analyze` in `c:\HackHive\LTDC\apps\mobile`.
- Test Suites:
  - `test/network_core_test.dart`: Core networking, cryptography, TLS pin, HMAC proofs, SSF1 framing, 16:9 dimension cropping math.
  - `test/widgets/card_geometry_test.dart`: 2×2 telemetry grid equal card heights and widths; camera stage card bounding boxes.
  - `test/widgets/control_alignment_test.dart`: Centered floating overlay controls; equal-width dialog and review action buttons on matching baseline.
  - `test/widgets/aspect_ratio_16_9_test.dart`: Strict 16:9 AspectRatio and container dimensions on `EvidenceMedia` and viewfinders.
  - `test/widgets/navigation_header_test.dart`: Brand badge, section label, status dot, and floating pill active states.

## Coverage Thresholds
- Tier 1: Feature Coverage (Header, Nav Pill, 2x2 Grid, Stage Cards, Centered Controls, Prompt Pills, 16:9 Media).
- Tier 2: Boundary & Corner Cases (Narrow mobile viewports, dynamic font scaling, offline cameras, empty telemetry).
- Tier 3: Cross-Feature Combinations (Navigating between screens while maintaining header/pill alignment and 16:9 stages).
- Tier 4: Real-World Scenarios (Incident review flow, CCTV camera station streaming, Ask conversation with 16:9 video playback).
