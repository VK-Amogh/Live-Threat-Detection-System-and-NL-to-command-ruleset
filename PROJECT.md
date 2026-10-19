# Project: SafeSpace Flutter Mobile UI/UX Redesign

## Architecture
- **Framework**: Flutter (Dart) targeting Mobile (Nothing Phone 4a and standard Android/iOS).
- **Root Directory**: `c:\HackHive\LTDC\apps\mobile`
- **Reference Web Dashboard**: `c:\HackHive\LTDC\apps\dashboard`
- **Design Authority**: `c:\HackHive\LTDC\DESIGN.md` (Strict 3-color dark palette `#000000`, `#FFFFFF`, `#1A1A1A`; `AppSerif` editorial titles; `Inter` functional sans; 20dp card radii; 48dp minimum touch target).
- **State Management & Routing**: `flutter_riverpod`, `go_router`.
- **Core Primitives**: `lib/core/widgets/` (`AppCard`, `AppButton`, `AppDialog`, `EvidenceMedia`, `FloatingNavPill`, `TopShellHeader`, `GlassSurface`).
- **Features**: `lib/features/` (`incidents`, `cameras`, `status`, `chat`, `rules`, `analyze`).

## Feature Inventory
Every feature from the Survey phase appears here with its assigned milestone:
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Theme & Card Radius Token Alignment | Ensure AppCard defaults to 20dp (`AppRadii.card`) and fix asset prefix in AppIcon | M1 | Survey (Explorer 1 & 2) |
| 2 | Unified Top Shell Header | Brand badge (shield icon + SafeSpace + device capsule), section label, live status dot | M1 | Requirement R1 |
| 3 | Refined Floating Nav Pill | Equal 48dp icon spacing, understated active highlight, remove dynamic text expansion | M1 | Requirement R1 |
| 4 | System Screen 2×2 Telemetry Grid | Arrange 4 key telemetry metrics in equal-sized 2×2 grid with tabular figures | M2 | Requirement R2 |
| 5 | Cameras Screen Stage Card Symmetry | Equal aspect ratio, uniform padding, and equal bounding boxes in single & multi-wall | M2 | Requirement R2 |
| 6 | Alerts Screen Card Padding & Margins | Equal horizontal margins (16dp), uniform card padding (16dp), aligned metadata | M2 | Requirement R2 |
| 7 | Centered Camera Station Controls | Center Torch, Flip lens, Snapshot, Stealth in glass pill with equal-width buttons | M3 | Requirement R3 |
| 8 | Centered Recording Action Controls | Geometrically aligned primary button & balanced secondary action button grid | M3 | Requirement R3 |
| 9 | Balanced Modal Dialogs & Review Bars | Equal-width buttons (`Expanded`) with matching 48dp touch baselines | M3 | Requirement R3 |
| 10 | Centered Ask Suggested Prompt Pills | Balanced prompt pills with centered typography and fixed height | M4 | Requirement R4 |
| 11 | Streamlined Ask Conversation Stream | Clean whitespace between messages, uncluttered conversational bubble layout | M4 | Requirement R4 |
| 12 | Prominent 16:9 Cited Video Evidence | Standalone 16:9 evidence card with citation badge, play overlay, and scrubber | M4 | Requirements R4 & R5 |
| 13 | Strict 16:9 Aspect Ratio on EvidenceMedia | Enforce 16:9 container with `BoxFit.cover` clipping on all video & image playback | M5 | Requirement R5 |
| 14 | Strict 16:9 on Viewfinders & Scrubbers | Enforce 16:9 on live broadcast viewfinders, reception stages, timeline snapshots | M5 | Requirement R5 |
| 15 | Static Analysis & Comprehensive Test Verification | Verify `flutter analyze` has 0 errors/warnings and all unit/widget tests pass | M6 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Shell Navigation & Design Tokens (R1) | `tokens.dart`, `app_card.dart`, `app_icon.dart`, `top_shell_header.dart`, `floating_nav_pill.dart`, `app.dart` | none | IN_PROGRESS |
| M2 | Equal-Sized Cards & Geometrical Symmetry (R2) | `status_screen.dart`, `live_cameras_screen.dart`, `incidents_screen.dart` | M1 | PLANNED |
| M3 | Centered & Geometrically Aligned Controls (R3) | `camera_station_screen.dart`, `incident_detail_screen.dart`, `app_dialog.dart` | M1 | PLANNED |
| M4 | Streamlined Ask / Investigation Screen (R4) | `chat_screen.dart`, suggested prompt pills, conversation stream, 16:9 evidence | M1 | PLANNED |
| M5 | Strict 16:9 Aspect Ratio on Video & Media (R5) | `evidence_media.dart`, `camera_station_screen.dart`, `live_cameras_screen.dart` | M1 | PLANNED |
| M6 | Final Verification & Test Hardening | `flutter analyze` 0 warnings/errors, 100% test pass in `apps/mobile` | M1-M5 | PLANNED |

## Code Layout
- `apps/mobile/lib/core/theme/tokens.dart`: Colors, spacing, radii, motion, typography tokens.
- `apps/mobile/lib/core/widgets/top_shell_header.dart`: Unified top bar with brand badge, section title, and status dot.
- `apps/mobile/lib/core/widgets/floating_nav_pill.dart`: Balanced icon navigation pill.
- `apps/mobile/lib/core/widgets/app_card.dart`: Equal-sized card primitive with 20dp border radius.
- `apps/mobile/lib/core/widgets/app_icon.dart`: Icon resolver supporting both asset paths and bare names.
- `apps/mobile/lib/core/widgets/evidence_media.dart`: Strict 16:9 media player and keyframe preview.
- `apps/mobile/lib/app.dart`: Application shell combining header, screens, and nav pill.
- `apps/mobile/lib/features/status/status_screen.dart`: Telemetry and system health 2×2 grid.
- `apps/mobile/lib/features/cameras/live_cameras_screen.dart`: Cameras live wall and stage cards.
- `apps/mobile/lib/features/cameras/camera_station_screen.dart`: Centered CCTV controls and recording grid.
- `apps/mobile/lib/features/incidents/incidents_screen.dart`: Symmetrical alert cards and feed.
- `apps/mobile/lib/features/incidents/incident_detail_screen.dart`: Incident review and equal-width action bar.
- `apps/mobile/lib/features/chat/chat_screen.dart`: Centered prompt pills, stream whitespace, 16:9 cited evidence.
- `apps/mobile/test/widgets/`: Comprehensive geometric widget tests.

## Interface Contracts
### TopShellHeader ↔ App Shell
- Displays `AppIcon('shield-check', size: 20)` + `Text('SafeSpace')` + `AppCapsule(label: 'Nothing Phone (4a)')`.
- Displays current section breadcrumb: `Text(sectionTitle)`.
- Displays live connection status: pulsing white dot + `Text('Live feed connected')`.

### FloatingNavPill
- Height: 56.0 dp (`AppSpacing.floatingBarHeight`).
- Item touch targets: 48.0 × 48.0 dp (`AppSpacing.floatingItemSize`).
- Active state: Subtle background highlight disc (`AppColors.highlight`) with active icon in `AppColors.foreground`. No dynamic text expansion.

### System Screen Telemetry Grid
- 2×2 grid (`GridView.count(crossAxisCount: 2, mainAxisSpacing: 12, crossAxisSpacing: 12, childAspectRatio: 1.25)`).
- 4 primary metrics: Awaiting Review (`needs_review`), Recorded Incidents (`incidents`), Cameras Online (`cameras_online`), Enrolled Devices (`devices_enrolled`).
- Equal card height, uniform padding (`AppSpacing.lg`), tabular figure typography.

### Camera Station Centered Controls
- Overlay controls: Centered horizontal glass pill `Center(child: GlassSurface(height: 48, ...))` containing equal-sized action buttons for Torch, Flip lens, Snapshot, and Stealth.
- Recording controls: Centered grid with 48dp primary action button and equal-width (50% / 50%) secondary button pairs.

### EvidenceMedia
- Container strictly wraps media in `AspectRatio(aspectRatio: 16 / 9)`.
- Video and images use `BoxFit.cover` with `Clip.hardEdge` to prevent letterbox/pillarbox distortion.
