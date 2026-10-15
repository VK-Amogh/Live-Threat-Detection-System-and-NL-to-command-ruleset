# PicSpace Design Language — `DESIGN.md` (mobile app + web dashboard)

> **One file, two surfaces.** Drop it into any project (Flutter, native, React Native, or a web dashboard) and an agent can build UI with the exact PicSpace look, micro-animations and interactions — **without access to the PicSpace codebase**. **Part A (§1–§12)** is the **mobile app**, extracted from the shipped Android app and checked against its source on 2026-10-15. **Part B (§13)** is the **web dashboard**, designed here as a derived extension of the mobile system (same tokens, same chrome, same physics) so both feel like one product.

| | |
|---|---|
| Version | 1.0 · 2026-10-15 |
| Platform | neutral. Token and component names are canonical; ports keep them (`--ps-*` in CSS, camelCase elsewhere) |
| Units | **1 dp = 1 CSS px = 1 pt**. Never rescale for desktop; sizes and 48-px targets stay |
| Tags | **[BUILT]** shipped in the mobile app · **[DERIVED]** the web dashboard / pointer extension specified in §13 (not shipped, but decided here) · **[PROPOSED]** something an agent adds that this file lacks — flag it for approval · **[GAP]** known hole |
| Not in this file | any product's features, data or back end. §7 only shows *how to compose* |

### How to use it

1. Put this file at the repo root as `DESIGN.md`.
2. Build in this order: **tokens** (§2, Appendix A / E / §13.2) → **primitives** (§5) → **motion** (§6, Appendix D) → **layout shell** (§4) → your screens.
3. Give the agent this instruction:

```text
Read DESIGN.md completely before writing UI. Use only its tokens and components; do not invent colours,
sizes, durations, curves or icons. Implement every state (loading, empty, error, disabled, selected) and the
reduced-motion path for every animation. Follow §0.1 and §15.2 exactly. When something you need is not in
DESIGN.md, say so and propose it, marked [PROPOSED] — do not silently improvise. Finish with the §15.1 checklist.
```

4. **Fidelity rule**: a value in this file beats your taste and beats a library default. If a library's spring/ripple/shadow differs, override it. "Close enough" is a defect.

## 0. Contract for agents

### 0.1 The ten things you must not get wrong

1. **Three colours only**: black `#000000`, white `#FFFFFF`, dark grey `#1A1A1A`, plus opacity variants of those three. No accent hue, no coloured icon, no gradient except black→transparent fades. Error and destructive states are shown with **words and an icon**, never a colour.
2. **Dark only.** One theme. System bars transparent, light icons, edge-to-edge.
3. **Headings are the upright serif (`AppSerif`)**, never italic, never bold, never below 18 sp. Everything else is Inter.
4. **One icon family only** (Stratis family, stroke 1.5 on a 24 grid, selected variant 2.1). No raw paths, no Material icons, no second family.
5. **Chrome is floating glass**: pills that hug their content, centred, icon-only, 48 dp targets, content scrolling underneath and dissolving into the edge.
6. **A bar morphs, it is never replaced.** One lower bar, one top bar, one header, one capsule, one back button, one tile selection mark. A new screen composes these; it does not draw its own pill, circle, capsule or back button.
7. **Menus are non-modal** (the shared menu component): a tap outside closes the menu *and* reaches what is under the finger; a menu closes itself after 6 s untouched. Sheets and confirmation dialogs stay modal.
8. **Real data only.** No mock data, dead buttons, stub screens. A control that does not work yet is not rendered. Fakes live only in `test/`.
9. **Analysis is invisible.** Never show "scanning", progress counters or banners for faces/places/scenes/Smart-search indexing. Results appear as they are found. Failures are typed and readable in Diagnostics.
10. **Tokens, not literals.** Colours, sizes, durations and curves come from `design_system`. A new value is a new token (or a documented literal in §3), not a local constant.
### 0.2 Precedence

This file is the source of truth for look, motion and interaction. If a host project already has conflicting styles, **do not blend**: either replace them with these tokens or tell the owner what conflicts. If a library default disagrees with a value here, the value here wins.

## 1. Identity and principles

The PicSpace language is **quiet, black and content-first**:

- **Three colours.** Black, white, and a dark grey that is never pure black. The user's own content (photos, video) is the only colour on screen.
- **Thin and small.** Hairline icons, 56-px bars, 48/40-px circles, 32-px capsules. Big or bold chrome is wrong.
- **Editorial.** Large upright serif titles over a plain content area; Inter for everything functional.
- **Physical.** A press feels like a press (scale on pointer-down); bars stretch like liquid; sheets, menus and dialogs settle on springs; larger things (pages, viewers) move on curves and never bounce.
- **Honest.** One sentence instead of a spinner; typed, actionable errors; privacy said plainly ("Nothing is uploaded.").
- **Real.** No mock data, no dead controls, no fake progress.

### 1.1 Design rules that shape every screen

| # | Rule |
|---|---|
| 1 | Content fills the screen edge to edge and **scrolls under** the bars; scroll views take their padding from `MediaQuery.padding`, which the shell enlarges |
| 2 | Headings sit directly above their content; spacing is multiples of 4 dp; screen margin 16; section → section 24; heading → content 12 |
| 3 | Text never overlaps: one-line labels ellipsize; counts/badges sit in their own chip; file names use middle-ellipsis |
| 4 | Every state is designed: loading (static dark-grey skeleton), empty (icon + title + one sentence), error (typed message + action), permission (explain + action) |
| 5 | Nothing is built "just for looks": no placeholder lists, no fake counts |
| 6 | The first frame already has the layout: skeleton rows / placeholder sections occupy their real space so nothing jumps |
| 7 | A page's name is visible in its top bar from the first frame; it never waits for a scroll |
| 8 | Animation is subtle: 90–480 ms, standard curves, reduced-motion respected |

---

## 2. Tokens

Tokens use canonical camelCase names. Flutter: `abstract final class`es (Appendix E). CSS: `--ps-*` variables (§13.2). Machine-readable: Appendix A.

### 2.1 Colour — `AppColors`

| Token | Hex / alpha | CSS (8-digit RRGGBBAA) | Use |
|---|---|---|---|
| `background` | `#000000` | `#000000` | every page background; photo letterbox; viewer |
| `foreground` | `#FFFFFF` | `#ffffff` | all text and icons; primary button fill; selected disc |
| `surface` | `#1A1A1A` | `#1a1a1a` | buttons, cards, boxes, chips, sheets, menus, dialogs, skeleton tiles, tile placeholder |
| `foregroundOnPhoto` | white 80 % (`0xCC`) | `#ffffffcc` | secondary text drawn **over photos** (dates on cards) |
| `foregroundSecondary` | white 60 % (`0x99`) | `#ffffff99` | secondary text and icons, hints, counts, unselected nav icons |
| `foregroundDisabled` | white 38 % (`0x61`) | `#ffffff61` | disabled text/icons, inactive slideshow segments |
| `divider` | white 10 % (`0x1A`) | `#ffffff1a` | 1 dp borders and dividers, scrub-track |
| `highlight` | white 12 % (`0x1F`) | `#ffffff1f` | pressed/selected state; nav-pill highlight; ripple; selected action |
| `glassFill` | `#1A1A1A` at 70 % (`0xB3`) | `#1a1a1ab3` | tint over the blurred backdrop of every glass surface; small badges on photos |
| `scrim` | black 60 % (`0x99`) | `#00000099` | modal sheet barrier; dim under the month label; fades under photo text |

**Derived colour literals in use** (reuse them; do not invent others):

| Where | Value |
|---|---|
| Selected chip fill | `highlight` over `surface` ≈ `#363636` |
| Tile skeleton | `surface` with white at alpha `0.12 × pulse` over it (pulse 0→1, 1.1 s, one ticker shared by every skeleton row; one painter per row) |
| Shimmer sweep | white at 5 % alpha, 60 %-wide band, 1.4 s linear loop |
| Video line track / played | white 24 % / white 100 % |
| Unselected select-mark | fill black 28 %, ring white 92 %, 1.6 dp |
| Selected select-mark | white disc, check drawn in `background` |
| Slideshow segment inactive / active | `foregroundDisabled` 4×4 / `foreground` 14×4 |
| Photo-text shadow `onPhotoShadow` | black 35 %, offset (0, 1), blur 2 |
| Scrub handle shadow | `scrim`, blur 8, spread 0.5 |
| Scrubber thumb shadow | `scrim`, blur 6 |
| `FadeScrim` alpha at position t∈[0,1] | `0.94 × strength × (1 − t)^2.2`, 13 stops, colour `background` |
| High-contrast mode | glass becomes opaque `surface` (no blur) |

The Material `ColorScheme`  maps primary/secondary/error → `foreground`, onPrimary → `background`, surface → `background`, surfaceContainer* → `surface`, outline → `divider`. There is **no** error colour.

### 2.2 Typography — `AppFonts`, `AppTypography`

Two families, both **bundled** (never fetched): **`AppSerif`** (headings; one weight, 400; the file is Arapey Regular until the licensed **Scotch Deck Light** is supplied — see §12.1) and **Inter** variable (weights from the `wght` axis).

| Token | Family | Size / line | Weight | Letter-spacing | Use |
|---|---|---|---|---|---|
| `display` | AppSerif | 40 / 48 | 400 | −0.5 | the big month label while dragging the timeline handle; onboarding-scale headings |
| `screenTitle` | AppSerif | 42 / 48 | 400 | +0.5 | the large section title (Photos, Cleanup…) that scrolls away |
| `storyTitle` | AppSerif | 38 / 46 | 400 | +0.4 | title card at the start of a memory |
| `sectionHeading` | AppSerif | 28 / 34 | 400 | +0.4 | "Memories", "People", "My albums", sheet titles, empty-state titles |
| `cardHeading` | AppSerif | 24 / 30 | 400 | +0.3 | titles over photo cards, dialog titles |
| `heading3` | AppSerif | 20 / 26 | 400 | +0.3 | day headers in the grid ("Today", "Mon, 9 Mar") |
| `cardTitle` | Inter | 15 / 20 | 600 | +0.1 | card names, utility rows |
| `body` | Inter | 14 / 20 | 400 | +0.2 | paragraphs, menu rows, input text |
| `label` | Inter | 14 / 20 | 500 | +0.2 | the top bar's "5 selected", names under circles |
| `support` | Inter | 13 / 18 | 400 | +0.2 | supporting text, counts, captions under headings |
| `caption` | Inter | 12 / 16 | 400 | +0.3 | dates, sizes, capsule text (at w500) |
| `tabLabel` | Inter | 12 / 16 | 500 | +0.4 | chip labels |
| `button` | Inter | 14 / 20 | 600 | +0.1 | button labels, "See all" |
| `micro` | Inter | 9 / 10 | 700 | — | **[GAP] unused** (was the "10" in skip-10-s icons, now removed) |

Rules:
- Serif is thin → **never smaller than 18 sp**; over photos add `onPhotoShadow` and use white (or `foregroundOnPhoto` for the second line).
- The serif ships one weight: **never ask for bold or italic**; no synthetic styles.
- Counts and times use **tabular figures** (`FontFeature.tabularFigures`): card counts, Smart-search rows, video time bubble.
- Chrome text (capsule, chips, buttons, menus) is Inter. A heading style must never resolve to Inter and a body style never to the serif.
- Text scales with the system; layouts must not overflow at **1.0, 1.3 and 2.0**. Use `minHeight`, never fixed heights for text. `CollectionCard.heightFor` multiplies the label row by the text scaler.
- Material `TextTheme` mapping: `displayMedium`=display, `headlineMedium`=screenTitle, `titleLarge`=sectionHeading, `titleMedium`=cardTitle, `bodyMedium`=body, `bodySmall`=caption, `labelMedium`=tabLabel, `labelLarge`=button.

### 2.3 Spacing and sizes — `AppSpacing`, `FloatingMetrics`

| Token | dp | Use |
|---|---|---|
| `xs` / `sm` / `md` / `lg` / `xl` / `xxl` | 4 / 8 / 12 / 16 / 24 / 32 | the spacing scale (unit 4) |
| `touchMin` | 48 | minimum tappable size (visual may be smaller; the hit area is padded to 48) |
| `smallCircle` | 40 | header circle (back, header ⋮), glyph 20 |
| `capsuleHeight` | 32 | the glass capsule label |
| `photoGutter` | 2 | gap between photo tiles |
| `floatingMarginH` | 12 | pill distance from the screen's left/right edge |
| `floatingMarginV` | 8 | pill distance from the system inset (top and bottom) |
| `floatingGap` | 6 | gap between a bar and its companion circle |
| `floatingBarHeight` | 56 | height of a floating bar |
| `floatingItemSize` | 48 | one icon item (and its highlight) inside a pill |
| `floatingPillPadding` | 4 | pill edge → first/last item |
| `floatingItemGap` | 4 | between items in a pill |
| `floatingContentGap` | 16 | extra clearance between last content row and a bar |
| `screenTitleHeight` | 56 | row of the large section title |
| `fadeExtra` | 32 | how far a top/bottom fade reaches past its bar |

`FloatingMetrics.forWidth(w)`: bar **56** always; bar icon **22** (≥ 340 dp wide) or **20** (narrower); every circle beside a bar **48** (`circle`); item side = bar − 8 = **48**. A pill that cannot fit at 48 per item **scrolls sideways** and keeps the selected item visible.

Screen margin for content: **16** (`lg`). Card-grid gutter: **12** (`md`). Photo-grid gutter: **2**.

### 2.4 Radii — `AppRadii`

| Token | dp | Use |
|---|---|---|
| `sm` | 8 | inner corners of small previews; selected-tile inset corner (8×t); video bubble preview |
| `md` | 12 | menus, snackbars, filmstrip thumbnail, bubble, chip-row boxes |
| `lg` | 16 | cards (`AppCard`), cover frames, text fields in dialogs, ghost cards, Explore cards |
| `lg + 4` = **20** *(literal)* | 20 | the card radius of `CollectionCard`, On this day, teasers, the problem card |
| `dialog` | 28 | dialogs, sheet top corners |
| `pill` | 999 | pills, circles, buttons, chips, badges, handle |
| `thumb` | 4 | **[GAP] unused**; photo tiles are square |

### 2.5 Glass — `AppGlass`, `GlassSurface`

`blurSigma = 24` (Gaussian σ). A glass surface is: clip to its radius (default pill) → `BackdropFilter.grouped(blur σ24)` → fill `glassFill` (#1A1A1A @70 %) → **1 dp `divider` border**. All glass surfaces on a screen share one backdrop via a single `BackdropGroup` at the top of the screen (shell, pushed page, viewer, player). High-contrast mode: no blur, opaque `surface`. Glass is **chrome only**: bars, circles, capsules, badges. It is never put over scrolling content as a full-screen filter.

### 2.6 Icons — `AppIcons`, `AppIcon`

One family: **Stratis UI** (24×24 grid, strokes). Generated from `ICONS/` by ; **never edit  by hand** — change `TOKENS` in the script and re-run. A new icon is chosen by looking at a rendered sheet, not by name.

- Stroke **1.5**; selected (`…Filled` token) **2.1**; round caps and joins; colour is the icon's `color` (default `foreground`).
- Sizes: default 24 · in bars 22 (20 on < 340 dp) · header circle 20 · menu row 20 · button 20 · chip check/close 18 · capsule leading 16 · badge 14 · filmstrip video mark 12 · empty-state 40 (inside a 96 dp `surface` circle) · placeholder in a card 26–32 · select-mark check = 0.66 × mark.
- Selected state = swap to the `…Filled` token (heavier stroke), not a colour change.
- Full token list: Appendix C.

### 2.7 Motion — `AppMotion`, `AppSprings`

**Durations**

| Token | ms | Use |
|---|---|---|
| `instant` | 90 | press feedback, thumbnail fade-in, toggles |
| `short` | 180 | menus' fades, chips, circle swap, banner fade, chrome fade, nav indicator scroll-into-view |
| `standard` | 280 | pages, sheets, tab slide, scroll-to-top, zoom, bar title slide |
| `long` | 420 | hero/page transitions (viewer open, memory open), memory slide cross-fade |
| `morph` | 480 | a surface changing shape (pill → search field) |
| `menuIdleClose` | 6 000 | an untouched floating menu closes itself |
| `story` | 4 000 | one memory slide |
| `storyTitle` | 2 500 | memory title card |

**Curves**

| Token | Definition | Use |
|---|---|---|
| `standardCurve` | `Cubic(0.2, 0, 0, 1)` | default: resizes, slides, zoom |
| `decel` | `Cubic(0.05, 0.7, 0.1, 1)` | things entering |
| `accel` | `Cubic(0.3, 0, 0.8, 0.15)` | things leaving |
| `linear` | linear | progress bars, Ken Burns, shimmer |

**Springs** (`SpringDescription(mass: 1, stiffness: k, damping: c)`; ζ = c / 2√k). Settle time uses Flutter's default tolerance (distance 0.001, velocity 0.01).

| Token | k | c | ζ | Overshoot | Settles in | Allowed for |
|---|---|---|---|---|---|---|
| `settle` | 400 | 40 | 1.00 | 0 % | ≈ 496 ms | nav highlight, sheets, zoom release, viewer spring-back, close-drag release |
| `soft` | 380 | 27.3 | 0.70 | ≈ 4.6 % | ≈ 580 ms | dialogs, chips' check, **press release**, list inserts |
| `pop` | 500 | 27.7 | 0.62 | ≈ 8.4 % | ≈ 516 ms | like heart, selection check/mark, FAB, bar slot pop-in, person cover pop-in, success check |
| `menu` | 600 | 39.2 | 0.80 | ≈ 1.5 % | ≈ 392 ms | popup menus |

**Bounce allow-list** — only these may overshoot: like heart, selection check/mark, FAB, bar-slot (✕/⋮) pop-in, menu (1.5 %), dialog (4.6 %), person cover pop-in, success check. **Everything else uses `settle` or a curve.** No bounce on scrolling, page slides, bars, sheets.

**Reduced motion** (`MediaQuery.disableAnimations`): `context.motion(d)` → 0; `context.motionOrFade(d)` → 100 ms fade; an `AnimatedSize` gets **1 ms, never 0** (a zero-length size animation re-dirties layout). No springs, no Ken Burns, no slideshow advance, no shimmer, no pinch layer (grid takes the nearest columns), hero → cross-fade, dialog/menu → fade only.

### 2.8 Haptics — `AppHaptics`

The platform applies the user's touch-feedback setting; never check it yourself.

| Call | Fires on |
|---|---|
| `selection` | select toggle; sub-tab change; month changes while dragging the handle; each whole grid level while pinching; filmstrip photo passing the middle; video line every tenth and on tap; album layout toggle; play/pause |
| `light` | like; search circle; scrubber/video-line finger down; mute toggle |
| `medium` | long-press that starts selection; grabbing the timeline handle; long-press on a person bubble or the On this day card |

No haptic on scroll.

---

## 3. Constants that live as literals (reuse these exactly)

These are not tokens but are repeated across the app. Reuse them; if you need a third copy, promote it to a token in `design_system` first.

| Thing | Value |
|---|---|
| `CollectionCard` | radius 20; cover frame radius 16; card padding (`inset`) 6; label row 44 (× text scale); cover area `(side − 12) × 0.92`; border 1 dp `divider`; fill `surface` |
| `AppCard` | radius 16; padding 16; 1 dp `divider`; fill `surface` |
| Explore card (photo + title) | radius 16; bottom `FadeScrim` 90; text inset 12; title `cardHeading` (places, trips) or `cardTitle` (categories); subtitle `caption` on-photo |
| Horizontal card row | card width **148**; gap 12; padding-h 16 |
| Places grid | 2 columns, gap 12, aspect 1.25, first 4 cities then "See all" |
| Trips row | card 240 × 160 |
| Scenes grid | 2 columns, gap 12, `mainAxisExtent = CollectionCard.heightFor` |
| Albums grid | 2 / 3 / 4 columns for width < 600 / < 840 / ≥ 840; gap 12 across, 16 down |
| Album list row | 68 dp cover (radius 16), name `cardTitle`, count `support`, chevron 20 |
| Utility row | min-height 56, radius 16, 1 dp border, icon · title · count · chevron |
| Tile selection mark | 22–30 dp (≈ 20 % of the tile), inset 0.3 × size from the corner; selected tile insets to 92 % with 8 dp corners |
| Tile badges | glass pill radius 999, padding 4×2, icon 14, `caption`; video badge bottom-left 6 dp, heart bottom-right 6 dp, corner text top-right 6 dp |
| Tile press | 0.98 |
| Day header | padding L16 T12 R8, row height 48, `heading3`; group toggle = 48 dp icon button |
| Filmstrip | strip height 52; active thumb 52, others 44 (lerp by distance from centre); radius 12, inner clip 10; 2 dp white outline fading with distance |
| Timeline handle | resting **56 × 12** white pill, 8 dp from the right edge; held → **48 circle** with a 20 dp `sort` icon in black, 12 dp margin; touch zone 64 × 72 |
| Video line | touch 32 dp high; line 2 dp (4 held); thumb 12 (held); end padding 8; seeks at most every 80 ms; time bubble 112 wide |
| Scrubber (generic) | touch 48; track 4 (6 held); thumb 14 (24 held) |
| People bubble | diameter 68–108 by photo count; gap 12; alternate vertical offset ±12 (alignment ±0.5); row height 132; name overlay on the bottom 34 % if named and ≥ 60 |
| Person header face | 176 dp circle |
| FaceAvatar | circle, `surface` fill, 1 dp `divider`, person icon 45 % when no face |
| On this day card | height = width × 0.78; radius 20; bottom scrim 150; label inset 16; segments 4 high |
| Empty state | 96 dp `surface` circle, icon 40, max-width 360, padding 24 |
| Dialog | max-width 360, radius 28, padding 24, 24 dp from screen edges |
| Sheet | top radius 28, handle 32 × 4 (`divider`), padding L/R 24, top 12, bottom 24 |
| Menu | min-width 200, max-width 280, radius 12, vertical padding 8, row min-height 48, horizontal padding 16, icon 20 + 12 gap |
| Snackbar | floating, radius 12, 16 dp side margins, sits above the bar: bottom inset + 56 + 16 + 8; 4 s (6 s with an action) |
| FAB (extended) | min 56 × 56, stadium, `surface`, icon + label; label collapses after 24 dp of scroll |
| Chips | stadium, min-height 40, padding-h 12, 1 dp border; selected = `#363636` fill + 18 dp check |
| Buttons | stadium, min-height 48, padding 24 × 8; min-width 120 (0 when `expand`); icon 20 + 8 gap |
| Text input (dialog) | fill `background`, radius 16, border 1 dp `divider`, focus 1.5 dp white, hint `foregroundSecondary`, **no counter**, error text secondary |
| Thumbnail fade-in | 90 ms (`instant`) when the picture arrives |
| Image fade-in (covers) | 180 ms (`short`) |
| Skeleton shimmer | 1.4 s linear, white 5 % |

---

## 4. Layout system

### 4.1 Window classes and widths

`< 600` compact · `600–839` medium · `≥ 840` expanded (used by Albums columns; Material window classes). The reference app is phone-first; design and test at **320, 360 and 411 dp** wide and text scale 1.0 / 1.3 / 2.0 — no overflow, no clipped text.

### 4.2 System chrome **[BUILT]**

`SystemUiMode.edgeToEdge`; status bar and navigation bar transparent; both icon brightness **light**; `systemNavigationBarContrastEnforced: false`. Theme `ThemeMode.dark` only. Page transitions (`SharedAxisTransitionsBuilder`) on every platform.

### 4.3 The shell

Let `top` = status-bar inset, `bottom` = gesture-bar inset, `bar` = 56, `edge` = 8.

```
headerBottom = top + edge + 56 (title row) + bar + edge          = top + 128
footerTop    = bottom + edge + bar + edge                         = bottom + 72
content gets MediaQuery.padding.top    = headerBottom
content gets MediaQuery.padding.bottom = footerTop + 16 (floatingContentGap)
top fade     = FadeScrim(top,    height = headerBottom + 32)
bottom fade  = FadeScrim(bottom, height = footerTop + 32)
```

Stack order (bottom → top): **page content** (the `StatefulNavigationShell`) → top fade → bottom fade → **large title** → **top bar** → **lower bar**.

| Layer | Position | Behaviour |
|---|---|---|
| Large title | `top + 8`, left/right 12; text starts at x = 16 | `screenTitle`, white; moves up exactly as far as the page scrolls (`translateY(−offset)`) and fades `1 − offset/56`; touches pass through; text swaps with `RollingText` |
| Top bar (`MorphingBar`) | `top + 8 + 56`, left/right 12 | rises with the title by `min(offset, 56)`, then **docks** at `top + 8` and floats; holds the 5-section pill (centred) + a 48 dp search circle when the tab has a search scope |
| Lower bar (`PhotosLowerBar`) | `bottom + 8`, centred | the active section's sub-tab pill; in Photos also a ⋮ 48 circle on its right; morphs to selection actions (✕ circle opens on its left) and to the viewer's actions |
| Both bars | — | slide out of the screen (top up, bottom down; fades on the last part) while the timeline handle is held; scrims fade; hidden bars take no touches |

Sections cross-fade (`FadeIndexedStack`: 180 ms `standardCurve`); every section keeps its state; hidden sections are laid out but not painted/hit-tested and their tickers are off. Within a section the sub-tabs are the pages of a `SubTabPager` (swipe) — see §8.1.

### 4.4 Pushed page — `LibraryPage`

Used for albums, folders, years, types, places, trips, scene categories, a person, Recently deleted, Smart-search/Explore-search results.

```
barBottom    = top + 8 + 48                          (header row is a 48 dp touch row, not a 56 bar)
titleBlock   = 36                                    (subtitle line: count / date range)
headerBottom = barBottom + 36
footer       = bottom + (bar below ? 8 + 56 + 8 : 16)
```

- Header = `PageHeader`: back circle **40** (48 touch) · gap 6 · capsule **32** with the page name · (optional) ⋮ **40** at the **right edge of the screen** (never next to the title).
- Under the header, a one-line `support` subtitle in `foregroundSecondary`, 16 dp from the edge, scrolls up and fades with the page (`1 − offset/48`).
- While selecting, the capsule reads "N selected" (or "Select photos" in a picker) and the page's name moves to the subtitle line; the layout height is constant so the grid never shifts.
- A page that shows its name in big type itself (a person) passes `titleAppearsAfter`: the capsule is invisible until that many dp are scrolled, then fades in over 60 dp.
- A page with many actions (a person) shows the common ones in its own **lower bar** (starts as a small pill and morphs open) and the rest in a ⋮ 48 circle beside it; its header is only the back button + capsule.
- The extended FAB (album "Add photos", trip "Play memory") sits bottom-right at 16 dp from the edges, pops in on `spring.pop`, hides while selecting.

### 4.5 The photo grid

- **Columns 1–8**, default **3**, remembered (`photos.gridColumns`). Tiles are **square**, `BoxFit.cover`, radius **0**, gutter **2**.
- Rows: day-header row (60 = 12 top padding + 48) then tile rows of `cell + 2`. Heights are known up front → the whole timeline length is laid out from the first frame; unloaded parts are skeleton rows of the right size, so the handle can go anywhere.
- Day headings: `Today`, `Yesterday`, `Mon, 9 Mar` (this year), `9 Mar 2024` (earlier). Handle bubble text: `Mar 2026`. Order: by date taken, newest first by default (sorts: Newest first · Oldest first · Largest first).
- Tile paint order: surface colour → average colour (`colors.bin`) → ThumbHash blur → sharp thumbnail (fade 90 ms; no fade during a fast fling) → highlight overlay if selected → badges → select mark.
- The grid never changes parent while pinching; layout changes above the viewport keep the on-screen photo in place.
- Pull-to-refresh uses `RefreshIndicator` coloured `foreground` on `surface`, `edgeOffset = top inset`.
- A filter-chip row (`FilterChipsRow`) sits under the top bar only when filters are active; each chip has an ✕ and removes its filter.

---

## 5. Component catalogue

Names are the canonical component names. On a new stack, create components with the same names, props and behaviour. **Reuse before you create.**

### 5.1 Chrome (the floating glass family)

| Component | Anatomy · sizes · states |
|---|---|
| **`GlassSurface`** | see §2.5. Default shape pill; takes any `BorderRadius`. |
| **`FloatingNavPill`** + `FloatingNavItem(id, icon, selectedIcon, label)` | Icon-only row, each item 48 dp (never below 48; the pill scrolls instead), padding 4, gap 4. Width = `n×48 + (n−1)×4 + 8` (5 sections = 264, 4 sub-tabs = 212, 6 = 316). The **selected item sits on a white-12 % pill highlight** that is *liquid* (§6.4). Unselected icon colour `foregroundSecondary`, selected `foreground`, colour follows the highlight continuously; the selected item uses the `…Filled` icon (stroke 2.1). Press 0.90. Tooltip + `Semantics(button, selected, label)`. `surface: false` when hosted inside a `FloatingBar`/`MorphingBar`. |
| **`FloatingBar`** | 56 dp high glass surface that hugs its content. `AnimatedSize` 300 ms `standardCurve`. Content is wrapped in `BarContentSwap` (§6.2). Content must **not** draw its own surface. |
| **`BarContentSwap`** | Swaps content in two beats keyed by `contentKey`. Same key → in-place update, no animation (a count 3→4). |
| **`AnimatedBarSlot`** | A slot beside a bar (✕, ⋮) that opens from width 0: width 300 ms `standardCurve`; content pops in on `spring.pop` scaling 0.4→1 with opacity `v/0.6`; leaves in 180 ms (`accel`). Gap 6 kept only while visible. |
| **`FloatingBarRow`** | `[AnimatedBarSlot leading] [FloatingBar] [AnimatedBarSlot trailing]`. Both slots are always in the tree so the bar keeps its identity. |
| **`GlassActionBar`** + `GlassAction(icon, label, onPressed, selected, burst, quickSwap)` | Icon actions at 48 dp, gap 4, padding 4. `selected` draws a white-12 % circle behind the icon (180 ms). `onPressed: null` → icon `foregroundDisabled`, no press. Icon swap = scale 0.5→1 + fade on `spring.pop`, or **`quickSwap`** 110 ms `decel` (play/pause, mute — buttons pressed again and again). `burst` plays the heart burst when `selected` turns on (§6.16). Press 0.90. Tooltip + `Semantics(button, toggled, enabled)`. |
| **`GlassCircleButton`** | Default **48** circle, icon 22, padding 8. `small: true` → **40** circle, icon 20, inside a 48 touch area (back, header ⋮). `.custom(iconWidget)` for an animated glyph. Icon change = 180 ms scale 0.6→1 + fade. Press 0.94. `compact` is a no-op kept for old call sites **[GAP]**. |
| **`AppCapsule`** | 32 dp glass label, padding-h 12, optional 16 dp leading icon + 4 gap, `caption` at w500 white, one line, ellipsis. Text change: old fades out, new fades in (180 ms) while the capsule stretches (180 ms `standardCurve`, left aligned). One capsule everywhere — never replaced. |
| **`AppBackButton`** | `GlassCircleButton(small)` with `AppIcons.back`, label "Back", pops the route. |
| **`PageHeader`** | `[Back 40/48] · 6 · [Expanded: capsule, left aligned] · [trailing slot, at the screen's right edge]`. `titleOpacity` (ValueListenable 0–1) lets the capsule fade in after a page's own big title scrolls away (`IgnorePointer` below 0.5). `showTrailing` slides the trailing circle in/out. |
| **`MorphingBar`** + `SearchCloseIcon` | The top bar: pill → search field on **one** surface (§6.5). The trailing circle keeps size 48 and its glyph morphs search ⇄ X (same 1.5 stroke). `pillWidth` lets the closed bar stretch to fit text ("5 selected" = text width + 48). With `circleBuilder == null` the circle slides away (180 ms `decel`). |
| **`GlassSearchBar`** (`bare: true` inside a morph) | Row: 16 pad · 24 search icon (secondary) · 8 · `TextField` (`body`, white, white cursor, hint `foregroundSecondary`, no border, dense) · clear button (`clearFilled`, 90 ms scale+fade) or a 16 dp spacer. Keyboard action = search. Standalone it is a 56 dp glass bar. |
| **`FadeScrim`** | Black→transparent fade, `IgnorePointer`. Alpha `0.94 × strength × (1−t)^2.2` on 13 stops (no visible band). Sits behind bars so content *dissolves* under them. Viewer uses `strength 0.7`, memory title area `0.8`. |

### 5.2 Controls

| Component | Anatomy · sizes · states |
|---|---|
| **`AppButton`** | Stadium pill. **`secondary`**: fill `surface`, 1 dp `divider` border, white `button` text. **`primary`**: white fill, black text, no border — "the one action a dialog or page is about"; the palette stays three colours, weight comes from inversion. Min height 48, padding 24×8, min width 120 (0 with `expand`). Optional 20 dp leading icon + 8 gap. Disabled → text `foregroundDisabled` on `surface` (primary falls back to the secondary look). Press 0.97. |
| **`AppCard`** | `surface`, radius 16, 1 dp `divider`, padding 16. |
| **`AppChip`** | Stadium, min-height 40, padding-h 12, 1 dp `divider`, label `tabLabel`. **Selected** = fill ≈ `#363636` **and** an 18 dp check that slides in (180 ms, `spring.soft`) — never colour alone. **Removable** (`onDeleted`) shows a trailing 18 dp ✕ in `foregroundSecondary`; semantics "label, tap to remove". Fill animates 140 ms. Press 0.96. |
| **`AppChoiceRow`** | Single-choice row, min-height 48, label `body`, trailing 20 dp check when chosen; semantics mutually exclusive group. |
| **`EmptyState`** | Centred in a `FadeRise`: 96 dp `surface` circle with a 40 dp icon · 16 · title `sectionHeading` (centred) · 8 · body `body` `foregroundSecondary` (centred) · 12-dp-spaced action buttons stacked. Max width 360, padding 24. Used for empty, error, permission, coming-soon. |
| **`AppMenuButton`** / `showAppMenu` / `AppMenuEntry(icon, label, onTap)` | See §6.10 and §8.5. Glass ⋮ circle (48, or `small` 40) that opens a non-modal anchored menu: `surface`, radius 12, 1 dp `divider`, rows min-height 48 (20 dp icon, 12 gap, `body` text), disabled row = `foregroundDisabled`. `AppMenuButton.lazy(entriesBuilder)` builds entries **when the menu opens** (never a stale list). |
| **`showAppDialog`** / `AppDialogFrame` / `showAppConfirmDialog` / `showAppTextDialog` | See §5.3. |
| **`showAppSheet`** | See §5.3. |
| **`showAppMessage`** | See §5.3. |

### 5.3 Overlays

**Dialog.** One frame for every confirmation and every "type a name" box. `AppDialogFrame`: `surface` card, radius 28, 1 dp `divider`, **max 360 wide** (24 dp from the screen edges on a narrow phone), padding 24. Order: title (`cardHeading`, white) → 8 → body (`body`, `foregroundSecondary`) → 16 → content (text field) → 24 → **one row of 1–2 equal-width buttons**, gap 12, the quiet one first (Cancel, `secondary`) and the one the dialog is about last (`primary`, `expand: true`). Centred, and it moves up with the keyboard (180 ms). Barrier = `scrim` (black 60 %), fades in ≈ 180 ms; barrier tap dismisses. Enter `spring.soft` scale 0.92→1 + fade over the first half; exit 120 ms. Never build your own `AlertDialog`/`Dialog`.
- `showAppConfirmDialog(title, body, confirmLabel, cancelLabel = 'Cancel') → Future<bool>`.
- `showAppTextDialog(title, confirmLabel, hint, initial, maxLength = 80, validator) → Future<String?>`: autofocus, `TextCapitalization.words`, the old name is **pre-selected**, no character counter, empty → "Enter a name.", submit on the keyboard's done key.

**Sheet.** `showAppSheet(builder)`: modal bottom sheet, scroll-controlled, safe-area aware, fill `surface`, **top radius 28**, barrier `scrim`; a 32×4 `divider` handle centred 12 dp from the top; 16 below it; content padded 24 left/right/bottom. Enters on `spring.settle`, leaves in 220 ms `accel`. Content swaps inside a sheet use `AnimatedSize` 280 ms + `AnimatedSwitcher` 180 ms (see the Smart search sheet). Sheet titles are `sectionHeading`; rows are 56 dp high with a 24 dp icon.

**Snackbar.** `showAppMessage(message, {actionLabel, onAction})`: floating, `surface`, radius 12, `body` text, swipe-away horizontally, above the lower bar. 4 s (6 s with an action). Slides in 180 ms `decel`. **One at a time** (the current one is hidden first). Success feedback goes here when nothing navigates ("Added 3 items to Liked"); failure feedback too ("Couldn't …" + Retry when safe).

**Menu.** §6.10 / §8.5.

**Tooltips.** Material tooltip: `surface` fill, radius 8, 12 sp white Inter. Every icon-only control has one **and** a `Semantics` label.

### 5.4 Motion primitives

| Primitive | Behaviour |
|---|---|
| **`PressScale`** | Scales the child down **on pointer-down** (not on tap) over 90 ms `standardCurve`; on release springs back on `spring.soft` from the current scale. A `Listener` — never enters the gesture arena, so child tap/long-press/scroll are unchanged. Moving > touch slop releases. Ignores events after dispose. Reduced motion: no scale. Values in §6.1. |
| **`FadeRise`** | Fades in while rising 8 dp (default), once, on first appearance: 180 ms `decel`; `delay` staggers. Only transform + opacity. Reduced motion: shown. Used by `EmptyState`, Explore sections, selection bar. |
| **`PopIn`** | Scale 0.7→1 on `spring.pop` + fade over the first 35 %; `delay` staggers (**max 8 items**; people grid uses 30 ms × index). First appearance only. Allow-listed (person cover). |
| **`SlideFade`** | Slides from an edge (default −0.6 × own height) while fading; 280 ms slide + 180 ms fade; takes no space animation. **Available, unused.** |
| **`RollingText`** | Value changes roll vertically: old text rises 12 dp and fades, new text arrives from 12 dp below; 180 ms (reverse when the number went down). Used for the large title and "N selected". |
| **`ShimmerSweep`** | One white-5 % band (60 % width) sweeping the whole skeleton every 1.4 s, linear; one painter on top, none per placeholder; stops with reduced motion. |
| **`DashedOutline`** | 1.5 dp dashed rounded outline (6 on, 5 off) in `foregroundSecondary` for "add something here" tiles. **Available, unused.** |

### 5.5 Scroll and chrome coordination

| Component | Role |
|---|---|
| `ScrollChromeController` / `ScrollChromeScope` / `ScrollChromeReporter(id)` | Shares the **offset of the active page** with the floating header so the title can scroll away and the pill can dock. Only depth-0, vertical notifications count. A `ValueNotifier` — the header animates from it per frame without rebuilding anything above its leaves. `scrollToTop(duration)` uses `easeOutCubic`. |
| `ChromeVisibilityController` / `ChromeVisibilityScope` / `ChromeSlide(to: up\|down\|fade, travel)` | Lets a page ask bars to leave. Holds are **counted** (two askers keep the bars away until both let go). `ChromeSlide`: leave 240 ms `easeInCubic`, return 320 ms `easeOutCubic`; bars also fade `1 − t²` over the last part; scrims fade `1 − t`; hidden = `IgnorePointer` past 50 %. No controller above → does nothing. |
| `SubTabPager(index, children, position, onIndexChanged, swipeEnabled)` | Horizontal `PageView` of a section's sub-tabs. Pages are kept alive (scroll position per tab). `position` mirrors the fractional page so the pill's highlight follows frame by frame. Swipe off while selecting or searching. |
| `PagerHandoff(threshold: 24)` | Wraps a horizontal carousel: after 24 dp of over-scroll at its end the drag is handed to the pager, so a swipe that started on a carousel can still change tab. |

### 5.6 Collection and media components (reference set from the photo app)

| Component | Anatomy |
|---|---|
| **`MediaTile`** | Square. Layers: `surface` → picture (`ThumbImage`) → highlight overlay (selected) → badges → `SelectMark` (selection mode only). Press 0.98. Selected: picture insets to 92 % with 8 dp corners (90 ms). Leaving the list (unliked/trashed): scale 0.9 + fade 0 over 180 ms `accel`. Broken picture: `brokenImage` icon in `foregroundSecondary`. Semantics: "Photo/Video, m:ss, 9 Mar 2026, liked, selected". |
| **`SelectMark`** | Empty ring (black 28 % fill, white 92 % ring 1.6) → white disc with a black check. Select: disc pops on `spring.pop` from 0.85→1 and a ring spreads to 1.7× fading out over 380 ms. Deselect: back to 0.85 in 90 ms, no overshoot. Size 22–30. |
| **`CollectionCard`** | The one card for Scenes, albums, smart albums, device folders, Browse by type, Years: framed cover (radius 16) on a `surface` card (radius 20, 1 dp border), name **left** (`cardTitle`, one line), count **right** (`support`, secondary, tabular; shrinks before it pushes the title; hidden when 0). No cover → icon 32 in `foregroundSecondary` on black. Optional top-left `badge` (the pin: 24 dp glass disc, `favoritesFilled` 14). Press 0.98. Cover fades in 180 ms. |
| **`SectionHeading`** + `HeadingCount` + `SeeAll` | Row: heading `sectionHeading` (ellipsis) · trailing (count `support` secondary, or `SeeAll` = text button, `button` style, white, 48×48 min). Trailing takes ≤ 40 % of the width. |
| **`ExploreCard`** | Photo card radius 16 with bottom `FadeScrim` 90, title + subtitle bottom-left (12 inset) with `onPhotoShadow`. Places/Trips: serif title. Press 0.98. |
| **`OnThisDaySlideshow`** | §6.18. |
| **`FastScrollThumb`** + **`MonthLabel`** | §6.14. |

### 5.7 Viewer components (reference set)

| Component | Anatomy |
|---|---|
| **`MediaViewer`** | Full-screen, over everything. Black backdrop whose alpha = `route × (1 − dragProgress)`. §6.15. |
| **`ZoomableImage`** | Three stacked pictures fading in over each other; pinch (min 1, max 6), double-tap 2.5×; deep-zoom tiles past 1.6×. |
| **`Filmstrip`** | §3. Moves **with** the pager every frame; thumbnail size/outline from distance to the middle. |
| **`VideoPage`**, **`VideoTimeline`**, **`VideoPlayback`** | One thin line, no panel. §6.17. |
| **`ViewerLowerBar`** | Hand-over of the shell's lower bar so the viewer *continues* it (§6.15). |
| **`showInfoSheet`** | "Details" sheet: title `sectionHeading`; rows label (`support`, secondary, 96 dp column) + value (`body`): Name · Date (`9 Mar 2026, 5:31 pm`) · Dimensions (`4000 × 3000`) · Duration (video) · Type · Size (`1.4 MB`) · Folder. |

---

## 6. Motion and interaction choreography

Every motion is a transform or opacity on a small subtree. Durations/curves/springs are the tokens in §2.7. **Reduced motion substitutes are in §6.20.**

### 6.1 Press
Pointer-down → scale to `pressedScale` over 90 ms `standardCurve` → pointer-up/cancel → spring back (`spring.soft`). Tap callbacks are unchanged.

| Scale | Elements |
|---|---|
| 0.90 | pill items, action-bar buttons |
| 0.92 | album layout toggle, "new album" circle |
| 0.94 | circle buttons, people bubbles |
| 0.96 | chips |
| 0.97 | buttons (default), utility rows, a person's name |
| 0.98 | photo tiles, collection cards, Explore cards, album rows |
| 0.985 | On this day card |

### 6.2 A bar changes its content (`BarContentSwap`)
1. Old content fades out and scales to 0.9 — **90 ms**, `accel`.
2. At 90 ms the new content is put in place **invisible**; the host bar starts resizing now (**300 ms**, `standardCurve`, no overshoot).
3. **70 ms** later the new content fades/scales in 0.9→1 — **200 ms**, `decel`.
4. While `v < 0.6` the content takes no touches. Same `contentKey` → no animation. A swap cancelled midway returns to full opacity.
Applies to: section pill ⇄ selection actions ⇄ viewer actions ⇄ other section's pill; the top bar's pill ⇄ "N selected".

### 6.3 A circle opens beside a bar (`AnimatedBarSlot`)
Width 0 → 48 (+6 gap) over 300 ms `standardCurve` while the glyph pops 0.4→1 on `spring.pop`; the bar and its neighbours **slide**, never jump. Closing: fade + shrink 180 ms `accel`. The ✕ opens **before** the lower bar changes (selection).

### 6.4 The liquid highlight (`FloatingNavPill`)
Between items the 48-dp highlight **stretches**: the edge in the direction of travel moves with `progress^0.7` (it races ahead), the trailing edge with `progress^1.4` (it lingers), then settles into a circle. With `position` (the sub-tab pager) it follows the swipe frame by frame, remembering direction; without it, it runs `spring.settle` from the current value to the new index. Icon colour interpolates secondary→white by nearness to the highlight. After a change the selected item is scrolled into view (180 ms `standardCurve`).

### 6.5 Search: the pill grows into the field (`MorphingBar`)
1. Tap the search circle (haptic `light`) → `open = true`. **480 ms**, `easeInOutCubic` on the progress (100 ms fade when reduced).
2. The glass surface's left edge travels to the left margin; the circle (size unchanged) slides to the right end and the surface's right edge follows it. **One surface, one blur — no second bar.**
3. The pill's icons fade out over the first **35 %** while drifting 8 dp left and are then taken out of paint/hit-test/semantics (state kept).
4. The field fades in from **45 %** to 100 %.
5. The circle's glyph morphs: the lens shrinks to the centre while the handle stretches into the first stroke of the X; the second stroke grows out of the middle from 30 %.
6. The keyboard is requested **260 ms** after opening (not before the bar has started to grow).
7. Closing runs backwards; the field is cleared and unfocused. Switching section or tab closes it. A tab with no search scope draws **no circle** (it slides away in 180 ms).

### 6.6 Title scrolls away, top bar docks
Let `d` = the active page's scroll offset. Title: `translateY(−d)`, opacity `1 − d/56`. Top bar: `translateY(−min(d, 56))` — it rises with the title, then stays at `top + 8`. Section switch changes the title with `RollingText`. Tapping the selected sub-tab again scrolls to top (280 ms `easeOutCubic`).

### 6.7 Holding the timeline handle hides the bars
While a finger is on the handle: title + top bar slide up, lower bar slides down (240 ms `easeInCubic`, fading over the last part), scrims fade, nothing under them takes a touch. On release/cancel/dispose they return (320 ms `easeOutCubic`). Several pages may ask at once; counted.

### 6.8 Page push/pop (`SharedAxisTransitionsBuilder`)
- Incoming page: `translateX +30 dp → 0`, **280 ms** `decel`, opacity = `incoming × (1 − outgoing)`.
- Page underneath: `translateX −30 dp × secondaryProgress`, fades out over the first **40 %** (`easeIn`); reverse uses the last 60 % (`easeOut`).
- **Blur** (page transitions only): horizontal Gaussian σ 2.2 at the start, linearly to 0 by **55 %** of the way in; skipped when σ ≤ 0.15; `sigmaY` ≈ 0. Costs ≈ 2 slow frames per open-and-close. `--dart-define=PICSPACE_NO_TRANSITION_BLUR=true` builds without it. **Never** add a blur over scrolling content.
- Pop reverses with `accel`.
- Memory player route: 420 ms fade (`Interval(0, 0.6)`). Viewer route: no wrapper (the viewer animates itself, §6.15).

### 6.9 Sections and tabs
- Section ⇄ section: cross-fade **180 ms** (`standardCurve`); others stay alive, tickers off.
- Sub-tab swipe: native `PageView` physics; the pill follows.
- Tap a **neighbouring** tab: `animateToPage` 280 ms `standardCurve`. Tap a **distant** tab: `jumpToPage`, then opacity 0.4→1 and `translateX ±24 → 0` over 280 ms — the tabs in between are never built.
- Search results ⇄ tab content: `AnimatedSwitcher` 180 ms (stack layout).
- Haptic `selection` on a tab change.

### 6.10 Menu (`showAppMenu`)
- **Placement**: below the anchor in the upper half of the screen, **above** it in the lower half (8 dp gap); aligned to the anchor's right edge if the anchor is in the right half, else left; clamped 16 dp from the sides and inside the safe area (top + 8, bottom − 8). Max width = screen − 32, max height = screen − insets − 32.
- **Enter**: scale 0.86→1 about the anchor's nearest corner on `spring.menu` (≈ 392 ms), opacity over the first 40 %; the rows are already in place (**no per-row stagger**). Reduced: fade.
- **Exit**: 100 ms reverse (`accel`), then done. A picked entry's action runs in a **microtask after the close has started**, so an action that opens a dialog or sheet starts clean.
- **Closes on**: a tap outside (the tap **also reaches what is under the finger**), the system Back (before the page), `Esc`, app hidden, another route starting to move, the control that opened it pressed again, **6 s** with no touch (a touch restarts the timer), another menu opening (replaces it, no animation).
- Only one menu per overlay. `TapRegion` groups the opening control with the menu so its own press is not an "outside" tap.

### 6.11 Dialogs, sheets, snackbars
§5.3. The scrim of a dialog/sheet is `scrim`; a confirmation **must not** let taps through (modal on purpose).

### 6.12 Grid pinch (per-photo morph, not a scaled layer)
- Two fingers down → the grid keeps its columns and is hidden (an `Opacity` kept in the tree so the scroll view never changes parent); a **layer** draws every visible photo and day heading travelling from its place in the layout with `⌊n⌋` columns to its place in the layout with `⌈n⌉` columns, where `n` is a **real number** = the columns the fingers ask for.
- `n` rubber-bands past 1 and 8 (the picture scales a little about the fingers). The photo under the fingers **stays under them** in both layouts; the fingers can also pan.
- A photo whose other end is more than **0.6 screens** away fades in place instead of flying.
- Haptic `selection` on each whole level.
- On release the layer springs to the nearest whole number (a quick flick carries on a little); in the very frame it is removed, the grid appears with that many columns scrolled to exactly where the layer left the photos. The new value is remembered.
- The layer also draws what tiles have over their pictures (video badge, heart, corner text, selection mark/inset) and ThumbHash blur for undecoded photos. Reduced motion: no layer; nearest columns.

### 6.13 Selection
1. **Enter**: long-press a tile (haptic `medium`, pressed tile 0.98) or ⋮ → Select.
2. Top bar: pill → "Select items" / "N selected" (`RollingText`, `label` style); the bar stretches to `textWidth + 48` in 300 ms. The big title stays the section's name.
3. ✕ circle opens on the left of the lower bar, **before** the bar changes; lower bar morphs to the action set (§6.2); ⋮ stays and changes entries.
4. Tiles: mark appears top-left; selected tiles inset to 92 % (90 ms) with a highlight overlay and the white check disc (§5.6). Day headers show a 48 dp group toggle (`unchecked` ⇄ `selectFilled`).
5. **Drag-select**: after the long press, moving the finger extends the range; within **56 dp** of the top/bottom edge the grid auto-scrolls at `distance × 0.2` px per 16 ms tick.
6. Leaving (✕, Back, an action that completes): the reverse of 2–3.

### 6.14 Timeline handle (`FastScrollThumb`)
- Appears only while scrolling a listing longer than **2 viewports**; hides **2 s** after scrolling stops (fade 280 ms; 180 ms in).
- Resting: **56 × 12** white pill, 8 dp from the right edge; follows the scroll position along a track between the bars.
- Touch it (zone 64 × 72): haptic `medium`, the pill becomes a **48 circle** (180 ms `standardCurve`) with a 20 dp `sort` icon in black and a 12 dp right margin; the grid dims (`scrim`) and the **month name** shows centred in `display` type (40/48). It follows the finger from exactly where it was grabbed and reaches the very bottom.
- Month name change: old fades out completely (**60 ms linear**) *then* the new fades in (**80 ms** `easeOut`) — never both on screen; a burst of changes ends on the newest. Haptic `selection` per change.
- Both bars leave while it is held (§6.7).

### 6.15 Viewer
- **Open** (420 ms): route is non-opaque and has no transition wrapper. Backdrop alpha = route value; the photo is a **`Hero`** with a plain `RectTween` (no arc) whose flight child is the already-decoded grid picture (no re-decode); bars fade in over the last 30 % (`Interval(0.7, 1)`). Only the photo on screen has a hero tag; neighbours do not fly.
- **Bar continuity**: opened over the shell, the viewer's lower bar starts as a copy of the shell's bar (the shell's bar hides under it, invisible and untouchable), then once the picture has landed it morphs (§6.2) to the viewer's actions. Closing morphs back. Opened over a pushed page (album, person) it has its own bar.
- **Chrome**: top `PageHeader` (back 40 + capsule `9 Mar 2026 · 5:31 pm`) at `top + 8`; top fade `top + 96` strength 0.7; bottom fade `bottom + 200` strength 0.7; filmstrip (52) at `bottom + 8 + 56 + 8`; lower bar at `bottom + 8`. A **tap** toggles all chrome (180 ms opacity); chrome is hidden automatically while zoomed in (> 1.01).
- **Pictures** (each fades in 180 ms over the last): the grid's decoded square (whole, `contain`) → whole-photo thumbnail (`fit`) → 512 px → screen-size picture (longest side = screen × dpr clamped 512–2048; skipped while a finger scrubs the filmstrip) → past **1.6×** zoom and 140 ms of rest, 512-px **deep-zoom tiles** of the original, ≤ 30, centre first, over the screen picture (never blank).
- **Pager**: page physics = spring mass 0.45 / stiffness 170 / damping ratio 1 (critically damped), `minFlingVelocity` 40, `allowImplicitScrolling` so neighbours are built before the swipe; the index is a `ValueNotifier` — page change rebuilds only the header, bars and hero tags. Neighbours are prefetched only **after a swipe has settled**.
- **Zoom**: 1:1 finger tracking, min 1, **max 6**; double-tap toggles 1 ⇄ **2.5×** about the tap point over 280 ms `standardCurve`, retargetable mid-flight; a pinch that ends between 1 and 1.08 snaps to exactly 1 (pager and close-drag handed back).
- **Close-drag** (vertical, only at scale 1 and with one finger): the picture follows the finger, scales `1 − 0.12 × progress` (progress = |dy| / 240), the backdrop alpha × `(1 − progress)`, bars fade `(1 − 3 × progress)`. Release closes when `|dy| > 120 dp` or a fling > **700 dp/s** in the same direction; else springs back on `spring.settle`. Closing flies the picture into its tile: the grid scrolls the viewer's current photo into view while the viewer is open (`MediaGridView.revealIndex`).
- **Two fingers down** → the pager and close-drag step aside for the rest of the gesture.
- **Filmstrip**: moved by the pager in the same frame (never by its own animation); flicking the strip glides across many photos; the pager jumps are rate-limited (90 ms); settle with the chosen thumb exactly in the middle (180 ms), then the pages may load big pictures 150 ms later.
- **Actions** — photo: Share · Like (heart) · Add to album · Details · Move to trash. Video: Share · Play/Pause · Mute · Move to trash, with a ⋮ circle (Add to Liked · Add to album · Details). Delete asks "Move 1 photo to Recently deleted?" / "You can restore it for 30 days." / "Move to trash".

### 6.16 Like
Tapping the heart (haptic `light`): the icon swaps outline → filled on `spring.pop` with a white-12 % circle behind it; **burst**: 6 small hearts (r 4, shrinking 30 %) radiate 18 dp from the button over **360 ms** (`easeOutCubic`), fading `1 − t`. Viewer's like button only; not in the grid. Unlike: no burst.

### 6.17 Video
- Plays when its page is the one on screen; pauses when it leaves. Opened straight from its content URI (nothing copied first).
- The **only** control on the picture: a thin line low on the screen just above the filmstrip — no panel, no blur, no buttons. 2 dp (4 dp held), played = white, rest = white 24 %; 32 dp touch height; 8 dp end padding. Visible while the chrome is visible and the video is paused, or for **2 s** after play starts or a tap brings the chrome back, or while a finger is on it (fades in over 120 ms, out over 200 ms — "in quickly, out gently").
- Finger down: thumb 12 dp grows in (90 ms), bubble (112 wide, `surface`, radius 12) shows the **time you would land on** and a preview frame when there is one; seeks live at most every **80 ms** and the last position is never dropped; haptic `selection` every tenth; releases and **carries on playing** if it was playing. A tap on the line jumps there without scrubbing.
- Play/pause and mute are in the **lower bar** (`quickSwap`, 110 ms): the icon flips in the same frame as the tap, the player is asked afterwards, the player's stale answers are ignored for 500 ms. Mute belongs to the session.
- A tap on the picture shows/hides the bars; a **second tap within 300 ms and 100 dp** takes that back and toggles play (so a single tap never waits). A **long press** plays at **2×** while held and shows a `glassFill` pill hint for 700 ms. No ±10 s buttons, no skip gesture, no speed chip, no centre play disc.
- Failure: centred `error` icon (secondary).

### 6.18 On this day and the memory player
**On this day (`OnThisDaySlideshow`)**: card height = width × 0.78, radius 20, 1 dp border. A picture stays **4 200 ms**; the next crossfades over **1 000 ms** (`easeInOut`). Each picture drifts: scale **1.04 → 1.12** and ±10 dp sideways (direction alternates) over `hold + 2 × crossfade`, `linear`, and keeps drifting while it fades out so nothing jumps. The next-next picture is pre-decoded. Bottom 150 dp scrim; bottom-left: period ("Last month", "2 years ago") in `cardHeading` + date in `caption` on-photo; bottom-right: segment row (inactive 4×4 `foregroundDisabled`, active 14×4 white, gap 3, radius 2, 280 ms). **Pauses** when off-screen (`TickerMode`) or with reduced motion. Tap → memory player; long-press (haptic `medium`) → menu "Remove for today".

**Memory player**: full-screen black; up to 24 stills; **4 s** each; the **title card** (`storyTitle`, centred, on `scrim`) shows over the first photo for **2.5 s** (full until 2 s, gone at 2.5 s). Progress = one **3 dp** segment per slide (gap 4, track `divider`, fill white, linear). Stills run a Ken Burns: scale **1.00 → 1.07** and drift **2 %** of the width (direction alternates), over 4 s + 420 ms so it never stops while the next slide fades in (420 ms cross-fade). Tap the **left third** = previous; **rest** = next; **hold** pauses (chrome fades out 180 ms); swipe **down** (> 120 dp or > 700 dp/s) closes; swipe **up** (< −80 dp or < −600 dp/s) opens a sheet: *Save as album · Share · Remove this memory*. Header: segments at `top + 8`, then a row with a close circle (40) and ⋮ circle (40). Reduced motion: still pictures, no zoom, 100 ms cut.

### 6.19 Arrivals (data appears)
- Explore sections: `FadeRise` (180 ms, 8 dp), 63 ms stagger per section; people bubbles `PopIn` (max 8, 30 ms stagger, first appearance only); a new face/place/scene rebuilds **only its own section**.
- Thumbnails: average colour → ThumbHash → sharp, fade 90 ms; none during a fast fling.
- Skeleton → content: cross-fade; a skeleton never has a spinner. The one exception in code is the memory player's loading spinner **[GAP]**.
- Library changes while scrolled away: the visible photo is anchored; a "refresh" pill offers the new content.

### 6.20 Reduced motion — the substitutions

| Normal | Reduced |
|---|---|
| any duration via `context.motion` | 0 |
| any spring/slide via `context.motionOrFade` | 100 ms fade |
| `AnimatedSize` | 1 ms (never 0) |
| `PressScale` | no scale |
| `FadeRise`, `PopIn` | shown at once |
| `MorphingBar` | 100 ms |
| Bar swap | instant |
| Hero, shared-axis push | cross-fade |
| Menu, dialog | fade only |
| Slideshow, Ken Burns, shimmer, pinch layer | off |
| Haptics | unchanged |

---

## 7. Reference compositions (how the parts combine)

These are the screen patterns the language was built around. Compose them from §5; do not redraw their chrome.

| Pattern | Composition |
|---|---|
| **Section page (tab root)** | Large serif title (scrolls away) → top bar (`MorphingBar`: section pill + optional search circle) docks under the status bar → content scrolls under both bars (padding from §4.3) → lower bar (`FloatingBarRow`: sub-tab pill + ⋮ circle). Sections cross-fade; each keeps its state. |
| **Drill-down page** | `PageHeader` (back 40 + capsule 32 with the page name + ⋮ 40 at the right edge) → one-line `support` subtitle that scrolls away → content → optional lower bar / extended FAB bottom-right. Pushed with the shared-axis transition (§6.8). |
| **Gallery grid** | Square tiles, gutter 2, day headings in `heading3`, pinch-to-change-columns (§6.12), long-press selection + drag-select (§6.13), timeline handle (§6.14), skeleton rows of the right height from the first frame. |
| **Selection mode** | Count in the top bar ("N selected"), ✕ opens before the lower bar morphs to actions, ⋮ stays and changes entries. |
| **Full-screen viewer** | Hero open (§6.15), black backdrop, header capsule, filmstrip, lower bar that *continues* the page's bar, close-drag, zoom, video line (§6.17). |
| **Story / slideshow** | Segments, Ken Burns, cross-fade, tap thirds, hold-to-pause (§6.18). |
| **Cards & carousels** | One `CollectionCard` look for every collection (framed cover, name left, count right); 148-wide card rows with a handoff to the page swipe; people bubbles; 2-column grids. |
| **Search** | The top pill grows into the field on one surface (§6.5); the tab declares its search scope or has none (no circle). |
| **Overlays** | Non-modal menu, one dialog frame, bottom sheet, snackbar (§5.3). |
| **Empty / loading / error / permission** | §9.1. |


---

## 8. Interaction rules

### 8.1 Navigation and Back
- Start location `/photos/all`. Sections = branches of an outer stateful shell; sub-tabs = branches of an inner one. Every level keeps its state.
- **System Back priority**: ① leave selection → ② close search → ③ go to the section's **first** sub-tab → ④ go to **Photos** → ⑤ leave the app. (`PopScope(canPop: atHome)`.)
- A menu consumes Back before the page does; a viewer/pushed page pops normally.
- Tap the active sub-tab → scroll to top (280 ms). Tap another sub-tab → haptic `selection`, close search, go. Tap another section → close search, go (re-tapping the current section resets it to its first tab).
- Pushed pages open on the **root** navigator, above the floating bars.

### 8.2 Search
- One `MorphingBar`; each tab registers a `SearchScope(hint, openLabel, closeLabel)` or none. **None ⇒ the circle is not drawn.**

| Tab | Scope |
|---|---|
| All photos | only when Smart search is installed: "Describe a photo" (Search photos / Close search) |
| Liked | none |
| Albums | "Search albums" |
| Explore | "Search people, places, things" |

- Typing is debounced **250 ms** in state; results replace the tab content (180 ms cross-fade); a tapped recent search fills the field and runs at once; the keyboard's search key runs now and stores a recent search.
- Search is closed by: the circle (✕), Back, switching section/tab. While selecting, the circle is not drawn.

### 8.3 Selection
Entry/exit §6.13. Rules: the count is in the **top bar**, never in the big title; every circle beside a bar is 48; swipe between tabs is off while selecting; Select-all loads the **whole listing**, not just the loaded pages; actions on a mixed selection act on all; the "Liked" action is on when **every** selected item is liked.

### 8.4 Gesture table (grid and viewer)

| Gesture | Where | Result |
|---|---|---|
| Tap | tile | open viewer (or toggle in selection / trash) |
| Long-press | tile | start selection + drag-select (haptic `medium`) |
| Pinch (2 fingers) | grid | per-photo morph, 1–8 columns (§6.12) |
| Drag handle | right edge | scrub the whole timeline (§6.14) |
| Pull down | Explore, Albums, grid | refresh (`RefreshIndicator`, white on `surface`) |
| Swipe left/right | tab content | change sub-tab (off when selecting/searching); a carousel hands off after 24 dp |
| Tap | viewer picture | show/hide chrome |
| Double-tap | viewer photo | zoom 1 ⇄ 2.5× about the tap |
| Pinch / pan | viewer photo | zoom to 6× / pan |
| Drag down or up | viewer (scale 1) | close with a hero return |
| Swipe | viewer | previous/next |
| Swipe | filmstrip | glide across photos; pager follows |
| Long-press | video | 2× while held |
| Double-tap | video | play/pause (a first tap still toggles bars at once) |
| Tap left third / rest | memory | previous / next; hold = pause; swipe down = close; up = actions |
| Long-press | album card | lift + menu |
| Long-press | person bubble | rename |
| Long-press | On this day | menu "Remove for today" |

Arbitration: a long-press recogniser yields to scroll when the finger moves first; the viewer ignores the system edge-back region for horizontal drags; with two fingers down the pager and close-drag step aside.

### 8.5 Menus — the six rules
1. Non-modal: **no barrier, no scrim**. 2. A tap outside closes it **and works**. 3. Pressing the opening control closes it (never opens a second). 4. Back, route change, app hidden and `Esc` close it. 5. 6 s untouched closes it. 6. Every ⋮ and every floating menu uses `showAppMenu`/`AppMenuButton`; `showMenu`, `PopupMenuButton`, `MenuAnchor` are not used. A ⋮ sits at the **right edge** of a page, or beside its lower bar — never mid-header next to the title.

### 8.6 Confirmations
Moving to trash is confirmed (reversible for 30 days); permanent delete is confirmed again ("This can't be undone."); removing an album keeps its photos ("Photos stay in your library."). The confirm button is the primary (white) one; Cancel is the quiet one on the left. Originals are never overwritten without an explicit per-action confirmation.

---

## 9. States, copy and formats

### 9.1 Every state is designed

| State | Rule | Example in the app |
|---|---|---|
| **Loading** | A **static** dark-grey skeleton in the real layout (tiles, blocks of `surface`, radius 16), with one shared shimmer (white 5 %). No spinner-only screen longer than 150 ms. The grid skeleton is *rows of the right size*, so the scroll length is right from the first frame. | Explore skeleton (a 24-high heading block, a 176-high card, a row of 148-high cards); grid skeleton rows |
| **Empty** | `EmptyState`: icon in a 96 dp circle · title · one sentence · (action). Sections inside a page use a **placeholder in the real layout + one `support` sentence** instead. Never a blank screen. | "Nothing liked yet" |
| **Error** | Plain-language title + a button that does something (`Try again`, `Open settings`). Never raw exceptions, paths, stack traces or codes. Typed codes live in Diagnostics. | `EmptyState(error)` "Couldn't load Explore. Try again." |
| **Permission** | Explain what and why, say "Nothing is uploaded.", then the action. Handle *limited* access with a banner. | the limited-access banner sits above the content |
| **Success** | A snackbar when nothing navigates. | "Added 3 items to Liked" |
| **Disabled** | Icon/text `foregroundDisabled`; no press scale; still present (a disabled bar action stays in the bar). | "Share" with nothing selected |
| **Selected** | Never colour alone: highlight pill / check / heavier stroke / inset tile. | chips, nav, tiles |
| **Pressed** | Scale on pointer-down (§6.1) + `highlight` ink. | all |
| **Destructive** | Words + icon; same colours. The confirm button is the primary (white) one. | "Delete permanently" |

### 9.2 Copy voice

- **Sentence case** everywhere ("Move to trash", "Add to album"). No Title Case, no ALL CAPS, no exclamation marks, no emoji (the single "♡" in the Liked empty text is the only glyph).
- Titles are short statements or questions ("Delete album?"); bodies are one or two short sentences; buttons are **verbs** ("Move to trash", "Download", "Try again"); Cancel is "Cancel".
- Counts: `1 item` / `N items`, `1 photo` / `N photos`; selection: `Select items` (0) then `N selected`.
- Reassure on privacy where data is involved: "Nothing is uploaded.", "Face data never leaves your phone.", "Your photos stay on this phone."
- Dates: `Today`, `Yesterday`, `Mon, 9 Mar` (this year), `9 Mar 2024` (earlier); with time: `9 Mar 2026 · 5:31 pm` (lower-case am/pm). Bytes: `1.4 MB` (1024-based; one decimal below 10, none above). Durations: `m:ss`, `h:mm:ss`. Months in the handle bubble: `Mar 2026`. Percent: `42%` in tabular figures.
- Echoed user text uses curly quotes: `No results for “beach”`. New copy uses a typographic apostrophe (’); older strings mix both — do not churn them.
- Errors read like help, not blame: "The download was interrupted. Check your connection and try again; it carries on where it stopped."
- **[GAP] Inconsistent spellings in shipped copy** — "recognised/analysed" and "organizes"; "PicSpace" (app label, access gate) and "Pic Space" (Explore). Do not rewrite old strings without the owner; in new copy use **"PicSpace"** and the spelling of the surrounding screen.

### 9.3 Typed failures (shown, never silent)

- Analysis codes (Diagnostics): `decode`, `model`, `vault`, `oom`, `inference`, `crashed`, `step_disabled`. Only `decode` marks a photo done; no background failure marks work as done.
- Smart-search codes (sheet + Diagnostics): `network`, `http`, `size`, `hash`, `disk`, `model`, `tokenizer`, `oom`, `inference` — each with a sentence (`smartSearchErrorText`).
- Explore's problem card sentence comes from the codes: "People, places and scenes are paused: …" or "Some photos could not be analysed: …" with "Details".

---

## 10. Accessibility

- **Targets ≥ 48 × 48 dp** (visuals may be 40/36; the hit area is padded). Pill items never shrink below 48 (the pill scrolls instead).
- **Every icon-only control** has a tooltip *and* a semantic label. `FloatingNavItem.label`, `GlassAction.label`, `semanticLabel` are mandatory. Where a custom `Semantics` wraps, set `excludeSemantics: true` so the label is not duplicated.
- Semantics in use: `button`, `selected`, `toggled` (like, mute), `enabled`, `checked` + `inMutuallyExclusiveGroup` (choice rows), `slider` with increase/decrease (scrubber, video line; value = time), `scopesRoute`/`namesRoute` (menus, dialogs), `image` for labelled icons. Tile label: "Photo, 9 Mar 2026, liked, selected". Viewer capsule: "Item 3 of 20, 9 Mar 2026". Memory: "Slide 2 of 9". Filmstrip thumb: "Photo 3 of 20".
- **Contrast (measured, WCAG AA needs 4.5:1 for text)**:

| Pair | On `#000000` | On `#1A1A1A` |
|---|---|---|
| `foreground` white | 21.0 : 1 | 17.4 : 1 |
| `foregroundOnPhoto` (80 %) | 13.1 : 1 | 11.4 : 1 |
| `foregroundSecondary` (60 %) | 7.4 : 1 | 6.9 : 1 |
| `foregroundDisabled` (38 %) | 3.4 : 1 | 3.6 : 1 *(disabled content is exempt; never use it for live text)* |
| `divider` / `highlight` | non-text, 1.2–1.4 : 1 — separators and states only, never the only cue |

  Text over photos always gets `onPhotoShadow` or a `FadeScrim`/`scrim` under it.
- **Never colour alone**: selected = check/fill/stroke; error = icon + words; liked = filled heart.
- **Text scale** 1.0 / 1.3 / 2.0 without overflow: containers use `minHeight`; counts shrink (`FittedBox`) before they push a title; label rows multiply by the scaler.
- **Reduced motion** (§6.20) and **high contrast** (opaque glass) are honoured everywhere. Touch-feedback haptics follow the system setting.
- **Back** works at every level (§8.1); `Esc` closes menus.
- Menus and dialogs are semantic route scopes (`scopesRoute`, `namesRoute`, labelled "Menu" / "Dismiss").

---

## 11. Performance limits that shape the design

These are design constraints, not tips. Each exists because something was measured on a real phone or reasoned from first principles.

1. **Animate transform and opacity only**, on small leaf subtrees, with `AnimatedBuilder(child: …)` and controllers owned by the smallest widget. Never animate layout size of anything that contains a long list or images. Hosts that must resize (bars, capsule) are small and use `AnimatedSize`.
2. **No full-screen filter, `saveLayer`, big shadow or blur over scrolling content.** The one measured example: a blur over the timeline halved the frames shown (≈ 1,050 vs ≈ 2,400 in eight flings) and moved the 90th-percentile frame gap from 8 ms to 42 ms — it was removed. The page-transition blur (σ ≤ 2.2, first 55 %) costs ≈ 2 slow frames per open/close and was kept because the owner asked. Add nothing like these without a number from a device run .
3. **Glass is a handful of small surfaces** sharing one `BackdropGroup`; never repeat it inside a list or grid cell. Badges on photos use the flat `glassFill` colour **without** blur.
4. **Grid tiles are `const`-ish and cheap**: square, no radius, no shadow, one `ColoredBox`, one picture; badges are tiny; the pinch layer paints (not widgets) while two fingers are down. Skeleton rows are one painter per row with one shared ticker.
5. **Thumbnails**: fixed sizes (384–448 px and 768), files at computed paths, a ThumbHash blur before the sharp picture, picture cache sized by RAM; never decode a full original for a cell; never wrap a grid thumbnail in plain `Image`.
6. **The first frame has layout.** Skeletons/placeholders occupy their real space; `main` awaits no I/O.
7. **Rebuild scope**: each Explore section is its own provider host inside a `RepaintBoundary`; per-frame values are `ValueNotifier`s read by leaf `ValueListenableBuilder`s; `select` narrows watches; analysis pauses while a long list scrolls and while the viewer is open.
8. **Gestures respond in the same frame** (press scale on pointer-down; play/pause icon flips before the player answers). Nothing delays a single tap waiting for a second one.
9. **Heavy work never runs in the UI isolate or the app process** (models run in `:analysis`; thumbnails are made natively). The UI renders.
10. **Hit the frame budget of the device** (8.3 ms at 120 Hz, 16.7 ms at 60 Hz); judge smoothness by the jank distribution, not one number, and only from a **profile build on a phone**.

---

## 12. Adopting the language in a new project

### 12.1 Order of work
1. **Tokens** — colours, type, spacing, radii, glass, motion, springs (Appendix A is the machine-readable set; §13.2 is ready-made CSS; Appendix E is ready-made Dart).
2. **Fonts** — self-host `AppSerif` (Arapey Regular today; the owner wants Scotch Deck Light — a commercial font, licence needed) and **Inter** variable; both bundled, never fetched at run time. Both are SIL OFL per the PicSpace docs — keep the licence files.
3. **Icons** — one family only: **Stratis UI** (stroke icons on a 24 grid). Draw at stroke **1.5** (selected variant **2.1**), round caps/joins, `currentColor`. Appendix C lists the token → Stratis icon mapping. Verify the pack's licence before redistributing; any other 24-grid stroke set must be re-stroked to 1.5 and approved first.
4. **Primitives** — `GlassSurface`, `PressScale`, `FloatingBar` + `BarContentSwap` + `AnimatedBarSlot`, `FloatingNavPill`, `GlassActionBar`, `GlassCircleButton`, `AppCapsule`, `PageHeader`, `MorphingBar`, `AppButton`, `AppChip`, menu, dialog frame, sheet, snackbar, `EmptyState`, `FadeRise`, `FadeScrim`, skeleton.
5. **Shell** — the floating-chrome layout (§4.3) and scroll coordination (title scrolls away, pill docks; bars hide while a scrub handle is held).
6. **Your screens**, composed from the above.

### 12.2 Per-stack mapping

| Concept | Web (CSS/JS) | Flutter | SwiftUI | Jetpack Compose |
|---|---|---|---|---|
| Colour/type/space tokens | CSS variables (§13.2–13.3) | Appendix E classes | asset catalog / `Color` constants | `MaterialTheme` overrides or a token object |
| Spring `(k, c)`, mass 1 | `linear()` easing + duration (§13.2), or Framer Motion `{type:"spring", stiffness, damping, mass:1}` | `SpringDescription(mass: 1, stiffness: k, damping: c)` | `.interpolatingSpring(mass: 1, stiffness: k, damping: c)` | `spring(dampingRatio = ζ, stiffness = k)` — ζ = c / (2√k); overlay the curve against Appendix D to confirm |
| Cubic curve `(a,b,c,d)` | `cubic-bezier(a,b,c,d)` | `Cubic(a,b,c,d)` | `UnitCurve`/`timingCurve(a,b,c,d)` | `CubicBezierEasing(a,b,c,d)` |
| Glass σ 24 | `backdrop-filter: blur(24px)` | `BackdropFilter(ImageFilter.blur(sigma 24))` grouped under one `BackdropGroup` | `.background(.ultraThinMaterial)` is **not** equivalent — use a blur of radius 24 + the fill/border of §2.5 | `Modifier.blur`/RenderEffect on a backdrop layer + fill/border |
| Press on pointer-down | `:active` with 90 ms press, spring release | `Listener` + `PressScale` | `.simultaneousGesture(DragGesture(minimumDistance: 0))` | `pointerInput` `awaitFirstDown` |
| Reduced motion | `prefers-reduced-motion` | `MediaQuery.disableAnimations` | `accessibilityReduceMotion` | `Settings.Global.ANIMATOR_DURATION_SCALE == 0` / system setting |
| High-contrast glass | `prefers-contrast: more` → opaque `#1A1A1A` | `MediaQuery.highContrast` | `accessibilityContrast` | contrast setting |
| Haptics | none (don't fake) | `HapticFeedback` selection/light/medium | `UIImpactFeedbackGenerator` / `UISelectionFeedbackGenerator` | `HapticFeedbackType` |

### 12.3 Verifying fidelity (do all of these)
- **Numbers**: assert in tests that your tokens equal Appendix A (a 30-line test).
- **Springs**: sample your spring at 0, 100, 200… ms and compare with Appendix D's `springAt` (within 0.01); check overshoot 4.6 % / 8.4 % / 1.5 % and settle ≈ 496 / 580 / 516 / 392 ms.
- **Look**: render each screen and compare with the §2–§6 numbers (sizes, gaps, radii); check at widths 320 / 360 / 411 and text scale 1.0 / 1.3 / 2.0.
- **Motion**: record a screen capture of each choreography in §6 and step through it against the timelines; check the reduced-motion path (§6.20).
- **Performance**: measure on a real device/browser profile; do not claim "smooth" without numbers (§11).


---

## 13. Web dashboard — the same language on a desktop-class surface **[DERIVED]**

This section **designs the web dashboard** as an extension of the mobile app. It assumes the dashboard exists and says exactly how it looks and moves; every decision is derived from §2–§12 so a dashboard feels like the same product. The tag **[DERIVED]** means "not in the shipped mobile app, specified here by extending it". What the dashboard *contains* (its data, back end, auth) is a product matter outside this file — this file fixes only how it is **presented and how it behaves**. It is touch-capable and pointer-first: every pointer behaviour has a touch twin and a keyboard twin.

### 13.0 The dashboard in one paragraph

Same black canvas, same floating glass chrome. A large serif page title scrolls away; the top glass pill (section icons, centred) docks under the viewport edge with a search circle beside it; a lower glass pill holds the section's sub-pages and a ⋮ circle. Content is a calm 12-column grid of `surface` cards — stat cards, charts, tables, forms — centred at a readable width, scrolling *under* the bars. A table row selection turns the top pill into "N selected" and the lower pill into bulk actions (exactly the mobile selection mode). Search is a command palette: the top pill grows into the field on the same surface. Drill-down is a pushed page with the back/capsule/⋮ header, or — on wide screens — a right-hand inspector panel. Colour is black, white, dark grey; meaning is carried by icons, words, dash patterns and opacity.


### 13.1 What transfers 1:1 from mobile, what adapts **[DERIVED]**

| Mobile | Web |
|---|---|
| Three colours, dark only, opacity variants | **Identical.** `color-scheme: dark`, no light theme, no accent |
| Serif headings (upright, never bold/italic, ≥ 18 px), Inter body | **Identical** font files and sizes (px = dp) |
| 1 dp = 1 CSS px; spacing scale, radii, bar 56 / item 48 / circle 48 / header circle 40 / capsule 32 | **Identical.** Do **not** shrink for desktop; the targets stay 48 |
| Floating glass pills that hug content, icon-only, content scrolls under, fades into the edge | **Identical** (fixed-position pills; `backdrop-filter`) |
| One bar that morphs; one header (back 40 + capsule 32 + ⋮ 40 at the right edge) | **Identical** pattern |
| Non-modal menus (tap outside closes *and* passes through; 6 s idle; Esc) | **Identical**, plus Esc/keyboard |
| Dialog frame (360, radius 28, equal-width buttons) / sheet | Dialog identical; sheet → centred panel (max 560) at ≥ 600 px |
| Press scale on pointer-down; springs only on the allow-list | `:active` scale + `linear` spring easings |
| Haptics | none on web (do not fake them) |
| Long-press for menus/tooltips | hover tooltip, right-click optional, long-press kept for touch |
| Pinch, swipe, drag-handle | Only where the screen is a touch surface; always provide pointer + keyboard equivalents |
| Real data only; invisible analysis; typed errors | **Identical** |

### 13.2 Tokens as CSS custom properties **[DERIVED]**

Names mirror the Flutter tokens (prefix `--ps-`). 1 dp = 1 px. Hex colours are RRGGBBAA (the Flutter `0xAARRGGBB` re-ordered).

```css
:root {
  color-scheme: dark;

  /* colour — AppColors */
  --ps-bg: #000000;
  --ps-fg: #ffffff;
  --ps-surface: #1a1a1a;
  --ps-fg-on-photo: #ffffffcc;     /* white 80 % */
  --ps-fg-secondary: #ffffff99;    /* white 60 % */
  --ps-fg-disabled: #ffffff61;     /* white 38 % */
  --ps-divider: #ffffff1a;         /* white 10 % */
  --ps-highlight: #ffffff1f;       /* white 12 % */
  --ps-glass-fill: #1a1a1ab3;      /* #1A1A1A 70 % */
  --ps-scrim: #00000099;           /* black 60 % */
  --ps-selected-fill: #363636;     /* highlight over surface */

  /* families — AppFonts */
  --ps-font-serif: "AppSerif", "Arapey", Georgia, serif;
  --ps-font-sans: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;

  /* spacing — AppSpacing */
  --ps-xs: 4px;  --ps-sm: 8px;  --ps-md: 12px;  --ps-lg: 16px;  --ps-xl: 24px;  --ps-xxl: 32px;
  --ps-touch-min: 48px;  --ps-small-circle: 40px;  --ps-capsule-h: 32px;
  --ps-photo-gutter: 2px;
  --ps-float-mx: 12px;  --ps-float-my: 8px;  --ps-float-gap: 6px;
  --ps-bar-h: 56px;  --ps-bar-item: 48px;  --ps-bar-pad: 4px;  --ps-bar-item-gap: 4px;
  --ps-bar-icon: 22px;  --ps-circle: 48px;
  --ps-content-gap: 16px;  --ps-title-h: 56px;  --ps-fade-extra: 32px;
  --ps-icon-stroke: 1.5;  --ps-icon-stroke-selected: 2.1;

  /* radii — AppRadii */
  --ps-r-sm: 8px;  --ps-r-md: 12px;  --ps-r-lg: 16px;  --ps-r-card: 20px;  --ps-r-dialog: 28px;  --ps-r-pill: 999px;

  /* glass — AppGlass (Flutter sigma 24 = CSS blur(24px): both are the Gaussian standard deviation) */
  --ps-glass-blur: 24px;

  /* motion — AppMotion */
  --ps-dur-instant: 90ms;  --ps-dur-short: 180ms;  --ps-dur-standard: 280ms;
  --ps-dur-long: 420ms;    --ps-dur-morph: 480ms;   --ps-menu-idle: 6s;
  --ps-ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --ps-ease-decel: cubic-bezier(0.05, 0.7, 0.1, 1);
  --ps-ease-accel: cubic-bezier(0.3, 0, 0.8, 0.15);

  /* springs — AppSprings sampled over their settle time (see 13.5). Values > 1 overshoot. */
  --ps-spring-settle: linear(0, 0.0497, 0.1588, 0.2874, 0.4141, 0.5286, 0.627, 0.7086, 0.7747, 0.8273, 0.8686, 0.9006, 0.9252, 0.944, 0.9582, 0.9689, 0.977, 0.983, 0.9875, 0.9908, 0.9932, 0.995, 0.9964, 0.9974, 0.9981, 0.9986, 0.999, 0.9993, 1);
  --ps-spring-settle-dur: 496ms;
  --ps-spring-soft: linear(0, 0.0672, 0.22, 0.4026, 0.5798, 0.732, 0.8515, 0.9375, 0.9941, 1.027, 1.0423, 1.0459, 1.0422, 1.035, 1.0266, 1.0185, 1.0117, 1.0063, 1.0025, 1.0001, 0.9987, 0.998, 0.9979, 0.9981, 0.9984, 0.9988, 0.9992, 0.9995, 1);
  --ps-spring-soft-dur: 580ms;
  --ps-spring-pop: linear(0, 0.0711, 0.2356, 0.4346, 0.6282, 0.7931, 0.9192, 1.0055, 1.0566, 1.0798, 1.0833, 1.0745, 1.0594, 1.0426, 1.0269, 1.0139, 1.0043, 0.998, 0.9945, 0.9931, 0.9931, 0.9941, 0.9954, 0.9968, 0.9981, 0.9991, 0.9998, 1.0003, 1);
  --ps-spring-pop-dur: 516ms;
  --ps-spring-menu: linear(0, 0.0489, 0.1624, 0.303, 0.4467, 0.5793, 0.6936, 0.7871, 0.8602, 0.9149, 0.9542, 0.981, 0.9981, 1.0082, 1.0133, 1.0151, 1.0147, 1.0132, 1.0111, 1.009, 1.0069, 1.0051, 1.0036, 1.0024, 1.0015, 1.0008, 1.0004, 1.0001, 1);
  --ps-spring-menu-dur: 392ms;
}

@media (prefers-reduced-motion: reduce) {
  :root { --ps-dur-instant: 0ms; --ps-dur-short: 0ms; --ps-dur-standard: 0ms; --ps-dur-long: 0ms; --ps-dur-morph: 100ms; }
}
```

### 13.3 Fonts and type classes **[DERIVED]**

```css
@font-face { font-family: "AppSerif"; src: url("/fonts/Arapey-Regular.woff2") format("woff2"); font-weight: 400; font-style: normal; font-display: swap; }
/* When the licensed Scotch Deck Light is supplied, only the src changes. */
@font-face { font-family: "Inter"; src: url("/fonts/Inter-Variable.woff2") format("woff2"); font-weight: 100 900; font-style: normal; font-display: swap; }

html { font-synthesis: none; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; background: var(--ps-bg); color: var(--ps-fg); }
body { margin: 0; font: 400 0.875rem/1.25rem var(--ps-font-sans); letter-spacing: .2px; }
*, *::before, *::after { box-sizing: border-box; }
```

Bundle both fonts (self-host; no Google Fonts request — the app never fetches fonts). Sizes are in `rem` (16 px root) so the browser's text-size setting scales them, as the system text scale does on mobile.

| Class | `font` shorthand (weight size/line family) | letter-spacing |
|---|---|---|
| `.t-display` | `400 2.5rem/3rem serif` (40/48) | −0.5px |
| `.t-screen-title` | `400 2.625rem/3rem serif` (42/48) | +0.5px |
| `.t-story-title` | `400 2.375rem/2.875rem serif` (38/46) | +0.4px |
| `.t-section` | `400 1.75rem/2.125rem serif` (28/34) | +0.4px |
| `.t-card-heading` | `400 1.5rem/1.875rem serif` (24/30) | +0.3px |
| `.t-heading3` | `400 1.25rem/1.625rem serif` (20/26) | +0.3px |
| `.t-card-title` | `600 0.9375rem/1.25rem sans` (15/20) | +0.1px |
| `.t-body` | `400 0.875rem/1.25rem sans` (14/20) | +0.2px |
| `.t-label` | `500 0.875rem/1.25rem sans` (14/20) | +0.2px |
| `.t-support` | `400 0.8125rem/1.125rem sans` (13/18) | +0.2px |
| `.t-caption` | `400 0.75rem/1rem sans` (12/16) | +0.3px |
| `.t-tab-label` | `500 0.75rem/1rem sans` (12/16) | +0.4px |
| `.t-button` | `600 0.875rem/1.25rem sans` (14/20) | +0.1px |

Counts, times, table numbers: `font-variant-numeric: tabular-nums`. Serif: never `font-weight: 700`, never `font-style: italic`, never below `1.125rem` (18 px). Over photos: `text-shadow: 0 1px 2px #00000059`.

### 13.4 Primitive recipes **[DERIVED]**

```css
/* glass — chrome only; never over scrolling content; keep ≤ ~4 on screen */
.ps-glass {
  background: var(--ps-glass-fill);
  border: 1px solid var(--ps-divider);
  border-radius: var(--ps-r-pill);
  -webkit-backdrop-filter: blur(var(--ps-glass-blur));
          backdrop-filter: blur(var(--ps-glass-blur));
  overflow: hidden;
}
@media (prefers-contrast: more), (prefers-reduced-transparency: reduce) {
  .ps-glass { background: var(--ps-surface); -webkit-backdrop-filter: none; backdrop-filter: none; }
}
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .ps-glass { background: var(--ps-surface); }
}

/* the floating bar: 56 high, hugs its content */
.ps-bar { display: inline-flex; align-items: center; height: var(--ps-bar-h); padding: 0 var(--ps-bar-pad); gap: var(--ps-bar-item-gap); position: relative; }
.ps-bar__item { position: relative; width: var(--ps-bar-item); height: var(--ps-bar-item); border-radius: var(--ps-r-pill); display: grid; place-items: center;
  color: var(--ps-fg-secondary); background: none; border: 0; cursor: pointer; }
.ps-bar__item[aria-selected="true"], .ps-bar__item[aria-pressed="true"] { color: var(--ps-fg); }
.ps-bar__highlight { position: absolute; top: var(--ps-bar-pad); height: var(--ps-bar-item); border-radius: var(--ps-r-pill); background: var(--ps-highlight); pointer-events: none; }

/* circle beside a bar: 48 (40 in a header) */
.ps-circle { width: var(--ps-circle); height: var(--ps-circle); border-radius: var(--ps-r-pill); display: grid; place-items: center; color: var(--ps-fg); }
.ps-circle--small { width: var(--ps-small-circle); height: var(--ps-small-circle); }

/* capsule: 32 high */
.ps-capsule { height: var(--ps-capsule-h); padding: 0 var(--ps-md); display: inline-flex; align-items: center; gap: var(--ps-xs); max-width: 100%; }
.ps-capsule > span { font: 500 0.75rem/1rem var(--ps-font-sans); letter-spacing: .3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* buttons */
.ps-button { min-height: 48px; min-width: 120px; padding: 8px 24px; border-radius: var(--ps-r-pill); display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  font: 600 0.875rem/1.25rem var(--ps-font-sans); letter-spacing: .1px;
  background: var(--ps-surface); color: var(--ps-fg); border: 1px solid var(--ps-divider); cursor: pointer; }
.ps-button--primary { background: var(--ps-fg); color: var(--ps-bg); border-color: transparent; }
.ps-button--expand { flex: 1 1 0; min-width: 0; }
.ps-button:disabled { color: var(--ps-fg-disabled); background: var(--ps-surface); border: 1px solid var(--ps-divider); cursor: default; }

/* chip */
.ps-chip { min-height: 40px; padding: 0 12px; border-radius: var(--ps-r-pill); display: inline-flex; align-items: center; gap: 4px;
  background: var(--ps-surface); border: 1px solid var(--ps-divider); color: var(--ps-fg); font: 500 0.75rem/1rem var(--ps-font-sans); letter-spacing: .4px; }
.ps-chip[aria-pressed="true"] { background: var(--ps-selected-fill); }   /* + an 18px check icon, never colour alone */

/* cards */
.ps-card { background: var(--ps-surface); border: 1px solid var(--ps-divider); border-radius: var(--ps-r-lg); padding: var(--ps-lg); }
.ps-collection-card { background: var(--ps-surface); border: 1px solid var(--ps-divider); border-radius: var(--ps-r-card); padding: 6px; }
.ps-collection-card__cover { border-radius: var(--ps-r-lg); overflow: hidden; background: var(--ps-bg); }

/* menu (non-modal: no overlay element) */
.ps-menu { min-width: 200px; max-width: 280px; padding: 8px 0; background: var(--ps-surface); border: 1px solid var(--ps-divider); border-radius: var(--ps-r-md); }
.ps-menu__row { display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 0 16px; color: var(--ps-fg); font: 400 0.875rem/1.25rem var(--ps-font-sans); }
.ps-menu__row[aria-disabled="true"] { color: var(--ps-fg-disabled); }

/* dialog (native <dialog>) */
dialog.ps-dialog { width: min(360px, calc(100vw - 48px)); padding: 24px; background: var(--ps-surface); color: var(--ps-fg); border: 1px solid var(--ps-divider); border-radius: var(--ps-r-dialog); }
dialog.ps-dialog::backdrop { background: var(--ps-scrim); }
.ps-dialog__actions { display: flex; gap: 12px; margin-top: 24px; }  /* equal-width buttons: quiet first, primary last */

/* input (the dialog text field) */
.ps-input { width: 100%; padding: 14px 16px; background: var(--ps-bg); color: var(--ps-fg); border: 1px solid var(--ps-divider); border-radius: var(--ps-r-lg);
  font: 400 0.875rem/1.25rem var(--ps-font-sans); caret-color: var(--ps-fg); }
.ps-input::placeholder { color: var(--ps-fg-secondary); }
.ps-input:focus { outline: none; border: 1.5px solid var(--ps-fg); padding: 13.5px 15.5px; }
.ps-input[aria-invalid="true"] { border-color: var(--ps-fg-secondary); }   /* + error icon and words, no red */

/* switch (no accent): on = black thumb on white track; off = secondary thumb on surface track */

/* skeleton + shimmer */
.ps-skeleton { background: var(--ps-surface); border-radius: var(--ps-r-lg); position: relative; overflow: hidden; }
.ps-skeleton::after { content: ""; position: absolute; inset: 0; width: 60%;
  background: linear-gradient(90deg, #ffffff00, #ffffff0d, #ffffff00); animation: ps-sweep 1.4s linear infinite; }
@keyframes ps-sweep { from { transform: translateX(-100%); } to { transform: translateX(167%); } }  /* band 60 % wide: from just off the left edge to just off the right */

/* fade that lets content dissolve under a bar (FadeScrim, strength 1; top shown, flip for the bottom) */
.ps-fade-top { pointer-events: none; background: linear-gradient(to bottom,
  rgb(0 0 0 / 0.940) 0%, rgb(0 0 0 / 0.776) 8.33%, rgb(0 0 0 / 0.629) 16.67%, rgb(0 0 0 / 0.499) 25%, rgb(0 0 0 / 0.385) 33.33%,
  rgb(0 0 0 / 0.287) 41.67%, rgb(0 0 0 / 0.205) 50%, rgb(0 0 0 / 0.137) 58.33%, rgb(0 0 0 / 0.084) 66.67%, rgb(0 0 0 / 0.045) 75%,
  rgb(0 0 0 / 0.018) 83.33%, rgb(0 0 0 / 0.004) 91.67%, rgb(0 0 0 / 0) 100%); }
```

Icons: ship the Stratis SVGs as `stroke="currentColor"`, `stroke-width="1.5"` (`2.1` for the filled/selected variant), `stroke-linecap="round"`, `stroke-linejoin="round"`, `fill="none"`, on a 24 × 24 viewBox, drawn 22 px in bars, 20 in headers/buttons. Generate them from `ICONS/` the same way  does; never substitute another family.

**Press** (all values from §6.1): the press runs 90 ms, the release runs the soft spring.

```css
.ps-press { transition: transform var(--ps-spring-soft-dur) var(--ps-spring-soft); }
.ps-press:active { transform: scale(var(--ps-press, .97)); transition: transform var(--ps-dur-instant) var(--ps-ease-standard); }
```

### 13.5 Motion on the web **[DERIVED]**

- **Durations/curves**: the CSS variables above. `Cubic(a,b,c,d)` ≡ `cubic-bezier(a,b,c,d)`.
- **Springs**: the allow-list is unchanged (§2.7). With a library use the same physics: `{ type: "spring", stiffness: 500, damping: 27.7, mass: 1 }` (`pop`), `380 / 27.3` (`soft`), `600 / 39.2` (`menu`), `400 / 40` (`settle`). CSS-only: the `linear` easings above, each used with its `-dur`. They were sampled from Flutter's `SpringSimulation` (start 0, end 1, velocity 0, tolerance 0.001 / 0.01): `settle` 496 ms (0 % overshoot), `soft` 580 ms (4.6 %), `pop` 516 ms (8.4 %), `menu` 392 ms (1.5 %).
- **Animate only `transform` and `opacity`**; never `width/height/top/left` of anything large. Hosts that must resize (the pill, the capsule) are small; prefer FLIP/`transform` where you can.
- **Liquid highlight**: animate the highlight's left and right edges separately — the edge in the direction of travel with `p^0.7`, the trailing edge with `p^1.4` (p = 0→1 along the move), then settle on `settle`. (CSS `transition: left …, width …` is an acceptable fallback; JS/`useSpring` reproduces it.)
- **Bar content swap**: out 90 ms (`accel`) → swap while invisible and resize 300 ms (`standard`) → in after 70 ms for 200 ms (`decel`), scale 0.9→1. Same key → update in place.
- **Search morph**: 480 ms `ease-in-out` (use `cubic-bezier(.645,.045,.355,1)` = easeInOutCubic); pill icons out over the first 35 %, field in from 45 %; focus the input after 260 ms.
- **Page push**: `translateX(30px → 0)` + fade, 280 ms `decel`; page beneath moves −30 px and fades over 40 %. The transition blur is horizontal-only (σ 2.2 → 0 by 55 %); CSS `blur` is isotropic, so use an SVG filter `<feGaussianBlur stdDeviation="2.2 0"/>` **only if the owner wants it and it is measured** — the default on web is no blur.
- **Reduced motion** (`prefers-reduced-motion: reduce`): durations → 0, springs/slides → a 100 ms opacity fade, no shimmer, no slideshow advance, no Ken Burns.
- **Respect the filters rule**: no `filter`/`backdrop-filter` on scrolling content; no animating box-shadow.

### 13.6 Pointer, focus and state styles **[DERIVED]**

The mobile app is touch-only, so these are the pointer/keyboard twins. They stay inside the three colours.

| State | Style |
|---|---|
| Rest | as mobile |
| Hover (pill item, row, menu row, circle, chip, card) | background `#ffffff14` (white 8 %) fading in over 90 ms; cards also lift nothing — **no shadow, no translate** |
| Hover (primary button) | background `#ffffffe6` (white 90 %) |
| Pressed | `--ps-highlight` (12 %) + the press scale of §6.1 (pointer-down) |
| Focus-visible | `outline: 2px solid #fff; outline-offset: 2px` (inside a glass pill use `-2px`); never remove it, never colour it |
| Disabled | `--ps-fg-disabled`, no hover, no press, `cursor: default` |
| Selected | check / heavier icon / `highlight` pill — never colour alone |
| Drag-over / drop target | 1.5 px dashed `--ps-fg-secondary` outline (the `DashedOutline` look), `--ps-highlight` fill |
| Cursor | `pointer` on actionable, `text` in inputs, `grab`/`grabbing` on drag handles, `default` elsewhere |
| Scrollbar | `scrollbar-width: thin; scrollbar-color: #ffffff3d transparent;` (inside tables/panels only; the page uses the native one) |
| Selection (text) | `::selection { background: #ffffff33; color: #fff; }` |
| Tooltip | after **400 ms** hover or on keyboard focus: `surface`, radius 8, `.75rem` Inter white, 8 px from the anchor, 150 ms fade; replaces the long-press tooltip. Every icon-only control has one **and** an `aria-label` |

### 13.7 Dashboard shell, navigation and grid **[DERIVED]**

**Shell** = §4.3 verbatim, with `position: fixed` bars and `env(safe-area-inset-*)`. Title row 56, top bar at `inset + 8 + 56`, lower bar at `bottom: inset + 8`, fades `+32`, content padding top `inset + 128`, bottom `inset + 72 + 16`. The bars **never stretch** — they hug their content and stay centred at every width.

**Navigation model**

| Layer | What it is | Rules |
|---|---|---|
| **Sections** | Top pill, icon-only, tooltip = name, `nav aria-label="Sections"`. **3–7 sections** (5 is the reference: width 264 px). More than 7 → group them or move extras into the ⋮ menu | selected = white-12 % liquid highlight + filled icon; `aria-current="page"` |
| **Pages of a section** | Lower pill, icon-only, 2–6 items, `nav aria-label="Section pages"`, ⋮ circle on its right | tapping the current item scrolls to top (280 ms `easeOutCubic`) |
| **Drill-down** | Pushed page: `PageHeader` = back circle 40 + capsule 32 (page name) + ⋮ 40 at the right edge of the viewport | shared-axis push (§6.8); Back = browser back |
| **Inspector** (≥ 1200 px) | A record opens in a right panel instead of pushing a page: 400 px wide, `surface`, radius 20, 1 px border, from `headerBottom` to `footerTop`, scrolls inside, close circle 40 at its top-right, title in `cardHeading` | enters `translateX(24 px → 0)` + fade 280 ms `decel`; leaves 180 ms `accel`; list narrows to `max 720` beside it (cross-fade, not animated reflow) |
| **Command palette** | `Ctrl/⌘ + K` or `/` or the search circle → the top pill **morphs into the search field** (§6.5) and a results panel opens under it: `surface`, radius 16, 1 px border, width = bar width (max 560), rows 48, group labels `caption` secondary, max height 60 vh; arrow keys move, `Enter` opens, `Esc` closes | panel fades/rises 8 px over 180 ms `decel`; no scrim; a click outside closes it and the click goes through (same as menus) |

**Page container and grid**

| Class | Page margin | Content max width | Columns × gutter |
|---|---|---|---|
| compact `< 600` | 16 | fluid | 4 × 12 (cards 2-up) |
| medium `600–839` | 24 | fluid | 8 × 12 |
| expanded `840–1199` | 32 | **1200** (grids/tables) · **720** (forms, settings, reading) | 12 × 12 |
| wide `≥ 1200` | 32 | 1200 + 400 inspector gap 12 | 12 × 12 (+ inspector) |

Cards span: **stat card** 2/4 (compact), 2/8 (medium), 3/12 (expanded); **chart** full width (compact/medium), 6/12 or 8/12 + 4/12 (expanded); **table** full width; **form card** 720 max, centred. Vertical rhythm = §4: heading → content 12, section → section 24, card gap 12.

### 13.8 Page templates **[DERIVED]**

| Template | Anatomy (top → bottom) |
|---|---|
| **Overview** | Large title · optional filter chips (time range: "Last 7 days · Last 30 days · Last 12 months" as `AppChip`s) · row of 2–4 stat cards · 1–2 charts · a "Recent activity" list card · links to tables. Sections separated by 24, each arrives with `FadeRise` 63 ms apart |
| **Collection (table/list)** | Large title · toolbar row (`sectionHeading` + count `support` on the left, filter chips and a ⋮ on the right) · active-filter chips · table card (virtualised) · empty/loading states inside the card |
| **Detail** | Drill-down header · identity block (avatar 88/176, name `sectionHeading`, meta `support`) · tabs as chips · key-value card(s) (label 96–160 px column `support` secondary, value `body`) · related table(s) · activity |
| **Form / settings** | Large title · cards of **rows** (56 high, title `body` + helper `support` secondary + trailing control, 1 px dividers between rows, radius 16) · destructive actions at the bottom in their own card with words + icon, never red |
| **Empty / error / permission** | `EmptyState` centred in the content area (§9.1) |

### 13.9 Dashboard components **[DERIVED]**

All use the §13.4 primitives. No shadows, no hues, no gradients except fades.

**New icon tokens** (Stratis, stroke 1.5; use these names): `trendUp` = `arrow-up-right` · `trendDown` = `arrow-down-right` · `chevronDown` = `chevron-down` · `chevronUp` = `chevron-up` · `table` = `table` · `chart` = `bar-chart-01` · `activity` = `activity` · `bell` = `bell-01` · `upload` = `upload-02` · `moreH` = `dot-horizontal` · `eye` = `eye-open`. Everything else comes from Appendix C.

**Stat card.** `surface`, radius 20, 1 px border, padding 16, min-height 112. Label `support` secondary (1 line, ellipsis) → 8 → value `sectionHeading` (serif 28/34) white → 4 → delta row: `trendUp`/`trendDown` 16 px + words in `caption` secondary ("up 12 % from last week"). Never green/red; direction is the icon and the word. Value changes roll vertically (`RollingText`, 180 ms). Clickable card = press 0.98, opens its table.

**Table.** Card radius 16 with the table inside.
- Header row: 40 high, `caption` weight 500 secondary, sentence case, 1 px bottom divider, **opaque `surface`** and sticky (never glass over scrolling rows). Sortable header: a 16 px `chevronUp/Down` appears on hover, stays on the sorted column (that header turns white). Click cycles asc → desc → none; `aria-sort`.
- Rows: min-height **56** comfortable / **48** compact (density switch in the toolbar ⋮, remembered); cell padding 16 horizontal; text `body`; secondary line `support` secondary; numbers right-aligned with `tabular-nums`; 1 px `--ps-divider` between rows (none after the last); hover `#ffffff14`; selected `--ps-highlight`.
- **Selection**: a 48 px leading column holds the `SelectMark` (22), visible on hover/focus and always when any row is selected (like grid tiles). `Space` toggles, `Shift + click` selects a range (the twin of drag-select), `Ctrl/⌘ + A` selects all **matching rows** (loads the whole result, not just the rendered window). Selecting starts **selection mode**: the top pill becomes "N selected" (`RollingText`, bar stretches to text + 48), a ✕ circle opens on the left of the lower bar, the lower bar morphs to the bulk actions (Share/Export, Add to…, Delete…) and a ⋮ circle holds the rest. `Esc` or ✕ leaves.
- Row actions: a ⋮ circle 40 at the end of the row, visible on hover/focus, always on touch; its menu is the standard non-modal menu.
- Long lists: virtualise with **fixed row heights** so the scroll length is known from the first frame; skeleton rows (real height) for unloaded ranges; a left-edge `n–m of N` caption in tabular figures at the card footer; no page-number pagination.
- Empty: `EmptyState` in the card + one sentence; filtered-empty has icon `filterOff`, "No matches", "Try removing a filter."
- **Compact (< 600 px)** the table becomes a **card list**: each row a 56–72 high item (primary `cardTitle`, secondary `support`, trailing value `support`), tap opens the record; same selection mode.

**Toolbar and filters.** `sectionHeading` + `HeadingCount` left; right: a ⋮ (density, columns, export, refresh). Filter chips under it: `AppChip` toggles and removable chips (✕); an "Add filter" chip opens a menu of fields, picking one opens a small popover (`surface`, radius 12, field + Apply/Clear). Applying cross-fades the table 180 ms and scrolls it to top.

**Charts** (SVG; one card per chart; title `cardTitle`, subtitle `support` secondary, chart padding 16, plot height 200–280).
- No hues. Series are told apart by **line dash, marker shape, opacity and direct labels**:

| Series | Line | Marker | Opacity |
|---|---|---|---|
| 1 | solid 2 px | circle | 100 % |
| 2 | dashed `6 4` | square | 60 % |
| 3 | dotted `1 4`, round caps | triangle | 100 % |
| 4 | dash-dot `8 3 2 3` | diamond | 60 % |
| 5 | long dash `12 6` | ring (hollow circle) | 38 % |

- Bars: fills white 100 % / 60 % / 38 %, then 45° 1 px hatch, then dots; bar radius `sm` (8) at the top only; gap 2 between bars of a group, 12 between groups. **No pie or donut** (slices cannot be told apart without hue) — use a stacked bar with direct labels.
- Gridlines: horizontal only, 1 px `--ps-divider`; axis labels `caption` secondary, tabular; baseline white 24 %. Area fill: flat white 8 %, no gradient.
- Labels at the end of each line (`caption`, same dash sample before the name) replace a legend; if a legend is needed it is a row of non-interactive chips with the dash/marker sample.
- Hover/focus: a 1 px white-24 % crosshair and a tooltip in the menu surface (radius 12, 1 px border, `caption` date + `support` rows, 8 px from the pointer, **90 ms fade, no spring**); keyboard: arrow keys move the crosshair.
- Every chart has `role="img"` + an `aria-label` summary and a **"View as table"** entry in the card's ⋮ (the accessible twin).

**Forms.** Label `support` secondary above (8 gap); field = the dialog input (height 48, fill `background` on `surface`, radius 16, 1 px divider border, focus 1.5 px white, hint secondary); helper `support` secondary 4 below; **error** = `error` icon 16 + words in `support` white, border `--ps-fg-secondary` (no red); optional fields say "(optional)", required fields say nothing. **Select** = field + `chevronDown` + the standard menu anchored to it (menu width = field width). **Switch**: Material-3 geometry — track 52 × 32, thumb 16 off / 24 on, on = black thumb on white track, off = secondary thumb on `surface` track, 180 ms. **Checkbox**: 20 px, 1.5 px secondary ring, checked = white fill + black check; **radio**: 20 px ring, checked = white dot 10 px. **Segmented control / tabs in a page**: a row of `AppChip`s (selected = `#363636` + check). Validation runs on blur and on submit; the first invalid field takes focus and the form scrolls it to 24 px below the header.

**Buttons and actions.** `AppButton` primary (white) for **one** action per card/dialog; secondary for the rest; destructive uses the same colours with words + icon and always opens a confirm dialog. Button rows in dialogs are equal-width. Loading: the label stays, a 16 px `refresh`-style indeterminate ring replaces the icon after 150 ms; the button is `aria-busy` and ignores clicks.

**Avatars.** Circle, `surface` fill, 1 px divider border, face/photo cover; initials fallback in `label` on `surface` (no hue per user); sizes **24 · 32 · 40 · 88 · 176**; stacked avatars overlap by 25 % with a 2 px `background` ring.

**Lists and feeds.** Rows 56 (avatar 40 · title `body` · meta `support` secondary · time `caption` secondary tabular, right); 1 px dividers; new items slide in at the top (`SlideFade`, 280 ms) with a "N new" glass capsule that scrolls to them.

**Status.** Icon + words, never a colour dot: Completed `check` · Failed `error` + "Failed — try again" · In progress `refresh` (rotates 1 turn / 1.2 s linear, none in reduced motion) · Waiting `hourglass` · Paused `pause`. Status words are sentence case.

**Toast.** The snackbar: `surface`, radius 12, max width 480, centred above the lower bar (`bottom = inset + 8 + 56 + 16 + 8`), 4 s (6 s with an action), slide-up 16 px + fade 180 ms `decel`, one at a time, `role="status"`. Destructive actions are **optimistic with Undo** (6 s).

**Modals.** Confirm / text dialogs = the 360 px frame. Form dialogs use the same frame at **560 px max** (radius 28, padding 24, equal-width buttons, quiet first). Sheets (≥ 600 px) = the bottom sheet constrained to **560 px**, centred, top radius 28. Backdrop = `--ps-scrim`; clicking it dismisses non-destructive dialogs; `Esc` always closes; focus is trapped and returns to the opener.

**Drag to reorder.** Handle icon `dragHandle` 24 secondary in a 48 px target; the lifted row scales **1.03**, gets a 1 px `--ps-fg-secondary` border (no shadow) and neighbours slide 200 ms (`settle`); drop settles on `settle`; keyboard: focus the handle, `Space` lifts, arrows move, `Space` drops, `Esc` cancels; announced via `aria-live`.

### 13.10 Dashboard choreography **[DERIVED]**

| Event | Motion |
|---|---|
| First load of a page | skeletons in the real layout → sections arrive with `FadeRise` (180 ms, 8 px), 63 ms stagger, first appearance only; table rows never stagger |
| Hover | background fade 90 ms; nothing moves |
| Row/tile select | select mark pops on `pop`; row fill 90 ms; top pill and lower bar morph (§6.2/§6.13) |
| Sort / filter / range change | table or chart cross-fades 180 ms, scroll resets to top (280 ms `easeOutCubic`) |
| Stat value change | vertical roll 180 ms (12 px) |
| Chart first view | bars grow from the baseline `scaleY 0 → 1` and lines reveal left → right with a clip, **420 ms** `decel`, once; data updates morph 280 ms `standardCurve`; reduced: none |
| Inspector open/close | 280 ms `decel` in, 180 ms `accel` out (§13.7) |
| Command palette | top pill → field 480 ms morph (§6.5); results panel 180 ms fade + 8 px rise |
| Inline edit | click a cell → text fades to the field 90 ms; `Enter` saves (toast), `Esc` cancels |
| New data available | a glass capsule "New data" slides in under the top bar (280 ms), click refreshes and scrolls to top |
| Navigation | shared-axis push 30 px + fade 280 ms; sections cross-fade 180 ms; the sub-page pill highlight stretches liquid (§6.4) |
| Delete (optimistic) | row/card shrinks to 0.9 and fades 180 ms `accel`, neighbours close up 200 ms `settle`; Undo toast 6 s |
| Menus, dialogs, sheets, toasts | exactly §5.3 / §6.10 / §6.11 |

Reduced motion: §6.20 applies unchanged (durations 0, 100 ms fades, 1 ms size animations, no chart draw-in, no shimmer).

### 13.11 Keyboard and accessibility on the web **[DERIVED]**

| Area | Rule |
|---|---|
| Landmarks | `<header>` holds the top pill (`nav aria-label="Sections"`); `<main id="main">`; the lower pill is `nav aria-label="Section pages"`; a **Skip to content** link is the first focusable element and appears as a glass capsule at `12 px / 8 px` on focus |
| Pills | `role="tablist"`-style roving `tabindex` (one tab stop; ← → move; Home/End; Enter/Space activate); each item `aria-label` = its tooltip; `aria-current`/`aria-selected` |
| Menus | button `aria-haspopup="menu" aria-expanded`; menu `role="menu"`, rows `role="menuitem"`; ↑ ↓ move, Enter activates, `Esc` closes and returns focus; **non-modal** — a click outside closes it and still reaches its target |
| Dialogs | native `<dialog>` / `role="dialog" aria-modal="true"`, labelled by its title; focus trapped, first field/primary focused, `Esc` closes, focus returns to the opener |
| Tables | semantic `<table>` (or `role="grid"` with roving focus when cells are interactive), `aria-sort`, `aria-rowcount` for virtualised lists, selected rows `aria-selected`; row hover actions also appear on `:focus-within` |
| Charts | `role="img"` + text summary + "View as table" |
| Live regions | toasts `role="status"` (`aria-live="polite"`); errors `role="alert"`; selection count change announced ("3 selected") |
| Shortcuts | `Ctrl/⌘ K` or `/` search · `Esc` closes the top layer (menu → inspector → palette → selection) · `↑ ↓` move in lists · `Space` select · `Shift+click` range · `Ctrl/⌘ A` select all · `Delete` opens the confirm dialog · `?` opens a shortcuts dialog (560 px) |
| Targets | ≥ 48 × 48 px for pill items, circles, buttons; table rows ≥ 48; text links inside rows may be smaller but have a 48 px row hit area |
| Contrast | §10 table; `forced-colors: active` → glass and surfaces fall back to `Canvas`/`CanvasText` with 1 px `ButtonText` borders |
| Zoom / text size | usable to 200 % zoom and large browser text; sizes in `rem`; no fixed-height text containers |

### 13.12 Web performance rules **[DERIVED]**

1. `backdrop-filter` only on chrome (the pills, circles, capsules — at most ~4 on screen); **never** in rows, cards or inside a scroller; the sticky table header is opaque.
2. Animate `transform` and `opacity` only; add `will-change` only for the duration of an animation; no animated `box-shadow` (there are none), no animated `width/height/top/left` on large subtrees.
3. Virtualise anything over ~100 rows with fixed heights; `content-visibility: auto` on long off-screen sections; skeletons occupy their real height so nothing shifts.
4. Self-host and preload the two fonts, `font-display: swap`; images have intrinsic `width`/`height` and a flat-colour placeholder; no layout shift from late data.
5. Charts are SVG up to ~2,000 points, canvas above; one `requestAnimationFrame` loop; pointer tracking throttled to a frame.
6. Never block input: long work in a Worker; one input → visible feedback in the same frame (press scale on pointerdown).
7. Measure in the browser profiler (CPU/paint/layout, long tasks) on a mid-range laptop and a phone; do not claim "fast" or "smooth" without numbers.

### 13.13 Web parity checklist

- [ ] Only the ten colour tokens; no other colour literal; dark only (`color-scheme: dark`).
- [ ] Serif headings (upright), Inter elsewhere; sizes from §13.3; fonts self-hosted.
- [ ] Stratis icons at stroke 1.5 / 2.1 only; new dashboard icons from §13.9.
- [ ] Bars 56 / items 48 / circles 48 (40 in headers) / capsule 32; hit areas ≥ 48; bars hug content and stay centred.
- [ ] One top bar and one lower bar that **morph** (selection, search); no second pill, no custom back button.
- [ ] Menus non-modal (click-through, 6 s idle, `Esc`); dialogs one frame (360 / 560); no `alert/confirm/prompt`.
- [ ] No `backdrop-filter`/`filter` over scrolling content; sticky headers opaque.
- [ ] Hover 8 %, pressed 12 %, white focus ring, tooltips on hover/focus.
- [ ] Series in charts distinguished by dash/marker/opacity/labels; status by icon + words; no hue anywhere.
- [ ] Loading = skeleton in real layout; empty = icon + one sentence; error = typed message + action; reduced-motion, high-contrast and forced-colors handled.
- [ ] Real data only; no mock content shipped.

---

## 14. Extending the language to something it has not covered

When you need a component, screen or data pattern this file does not define (a table, a chart, a form wizard, settings, onboarding…):

1. **Compose before you invent**: build it from existing primitives (card, chip, button, menu, dialog, empty state).
2. **Stay inside the tokens**: three colours + opacity variants, the type scale, the 4-pt spacing scale, the radii, the motion tokens. If a value is missing, *add one token* with a name and a reason; do not use a one-off literal.
3. **No hues.** Status, error, success, diff and chart series are conveyed with icon + words + dash pattern + opacity steps (100 / 60 / 38 %), never colour.
4. **Same physics**: pointer-down press feedback, springs only from the allow-list, transform/opacity only, reduced-motion path.
5. **Mark it [PROPOSED]** in the PR/notes and list it in your "gaps" so the owner can approve it, then add it to this file.
6. **Never** add a light theme, an accent colour, a second icon family, a second bar, or a full-screen filter over scrolling content.

---
## 15. Agent checklist and anti-patterns

### 15.1 Before you hand work back

- [ ] I read §0 and the sections for what I am building.
- [ ] I searched for an existing component and reused it.
- [ ] No literal colour, size, duration or text style outside `design_system` (or a §3 literal).
- [ ] Only black, white, `#1A1A1A` and their opacities; no accent; no coloured icon.
- [ ] Serif headings upright; Inter elsewhere; no bold serif; nothing under 18 sp serif.
- [ ] Icons from `AppIcons`, stroke 1.5 / 2.1.
- [ ] Bars, circles, capsules, back button come from the shared components; nothing drawn twice.
- [ ] Menus via `showAppMenu`/`AppMenuButton`; dialogs via `AppDialogFrame`/`showApp*Dialog`; sheets via `showAppSheet`.
- [ ] Every state done: loading, empty, error + action, permission, disabled, selected.
- [ ] Transform/opacity only; springs only from the allow-list; reduced-motion path exists.
- [ ] 48 dp targets, semantics labels, text scale 1.0/1.3/2.0 at 320/360/411 dp, no overflow.
- [ ] No spinner-only screen; no "scanning" UI; no mock data; no unbuilt control rendered.
- [ ] linters/type-checks/tests ran — and I looked at a rendered screenshot; I ran it on a real device/browser if it touches gestures, scrolling or layout, or I said "not verified".
- [ ] If I changed a token or documented behaviour, I changed this file in the same commit.

### 15.2 Never

1. Add a hue, gradient (other than black→transparent fades), coloured badge or error red.
2. Add a light theme or a theme switch.
3. Use italics, bold serif, or a second icon family; draw a raw SVG path.
4. Build a second pill/bar/capsule/back button, or replace a bar instead of morphing it.
5. Use `showMenu`, `PopupMenuButton`, `MenuAnchor`, `AlertDialog`, `Dialog`, or a modal menu with a scrim.
6. Put a ⋮ mid-header next to a title.
7. Show scan progress, counters or banners for background analysis; mark a failed background step as done.
8. Show a control that does nothing; ship mock/demo data; show a section that is "not built" (other than the four Coming-soon sections).
9. Put a blur/filter/opacity layer/big shadow over scrolling content; animate layout of a list; wrap a grid thumbnail in plain `Image`; decode a full original for a cell.
10. Use a bouncing spring outside the allow-list; stagger rows in menus or grids; animate scroll.
11. Add a network call, analytics, crash SDK or font fetch.
12. Add a text counter to the name field; add accent colour to destructive actions; add ±10 s buttons, a speed chip or a centre play disc to video.
13. Let a tap outside a menu be swallowed.
14. Hard-code a bar height, circle size or margin in a feature.
15. Rename or reuse a stable id (a released tool id) — ids are permanent.
16. Claim "smooth", "fast", "works on device" without a profile-mode number or a device run.

---

## Appendix A — Design tokens (machine-readable)

```json
{
  "$description": "PicSpace design tokens v1.0 (2026-10-15). dp = css px. Colours are RRGGBBAA.",
  "color": {
    "background": "#000000", "foreground": "#ffffff", "surface": "#1a1a1a",
    "foregroundOnPhoto": "#ffffffcc", "foregroundSecondary": "#ffffff99", "foregroundDisabled": "#ffffff61",
    "divider": "#ffffff1a", "highlight": "#ffffff1f", "glassFill": "#1a1a1ab3", "scrim": "#00000099",
    "selectedFill": "#363636"
  },
  "font": { "serif": "AppSerif", "sans": "Inter" },
  "type": {
    "display":        { "family": "serif", "size": 40, "line": 48, "weight": 400, "tracking": -0.5 },
    "screenTitle":    { "family": "serif", "size": 42, "line": 48, "weight": 400, "tracking": 0.5 },
    "storyTitle":     { "family": "serif", "size": 38, "line": 46, "weight": 400, "tracking": 0.4 },
    "sectionHeading": { "family": "serif", "size": 28, "line": 34, "weight": 400, "tracking": 0.4 },
    "cardHeading":    { "family": "serif", "size": 24, "line": 30, "weight": 400, "tracking": 0.3 },
    "heading3":       { "family": "serif", "size": 20, "line": 26, "weight": 400, "tracking": 0.3 },
    "cardTitle":      { "family": "sans",  "size": 15, "line": 20, "weight": 600, "tracking": 0.1 },
    "body":           { "family": "sans",  "size": 14, "line": 20, "weight": 400, "tracking": 0.2 },
    "label":          { "family": "sans",  "size": 14, "line": 20, "weight": 500, "tracking": 0.2 },
    "support":        { "family": "sans",  "size": 13, "line": 18, "weight": 400, "tracking": 0.2 },
    "caption":        { "family": "sans",  "size": 12, "line": 16, "weight": 400, "tracking": 0.3 },
    "tabLabel":       { "family": "sans",  "size": 12, "line": 16, "weight": 500, "tracking": 0.4 },
    "button":         { "family": "sans",  "size": 14, "line": 20, "weight": 600, "tracking": 0.1 }
  },
  "space": { "xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32, "touchMin": 48, "smallCircle": 40, "capsule": 32, "photoGutter": 2 },
  "chrome": { "marginH": 12, "marginV": 8, "gap": 6, "bar": 56, "item": 48, "pillPadding": 4, "itemGap": 4, "circle": 48, "barIcon": 22, "barIconNarrow": 20, "contentGap": 16, "titleRow": 56, "fadeExtra": 32 },
  "radius": { "sm": 8, "md": 12, "lg": 16, "card": 20, "dialog": 28, "pill": 999 },
  "glass": { "blurSigma": 24, "fill": "#1a1a1ab3", "border": "#ffffff1a" },
  "icon": { "grid": 24, "stroke": 1.5, "strokeSelected": 2.1, "family": "Stratis UI" },
  "motion": {
    "duration": { "instant": 90, "short": 180, "standard": 280, "long": 420, "morph": 480, "menuIdleClose": 6000, "story": 4000, "storyTitle": 2500 },
    "curve": { "standard": [0.2, 0, 0, 1], "decel": [0.05, 0.7, 0.1, 1], "accel": [0.3, 0, 0.8, 0.15] },
    "spring": {
      "settle": { "mass": 1, "stiffness": 400, "damping": 40,   "zeta": 1.0,  "overshoot": 0,     "settleMs": 496 },
      "soft":   { "mass": 1, "stiffness": 380, "damping": 27.3, "zeta": 0.70, "overshoot": 0.046, "settleMs": 580 },
      "pop":    { "mass": 1, "stiffness": 500, "damping": 27.7, "zeta": 0.62, "overshoot": 0.084, "settleMs": 516 },
      "menu":   { "mass": 1, "stiffness": 600, "damping": 39.2, "zeta": 0.80, "overshoot": 0.015, "settleMs": 392 }
    },
    "bounceAllowList": ["like heart", "selection mark/check", "FAB", "bar slot pop-in", "menu", "dialog", "person cover pop-in", "success check"]
  },
  "press": { "navItem": 0.9, "actionButton": 0.9, "toggle": 0.92, "circle": 0.94, "bubble": 0.94, "chip": 0.96, "button": 0.97, "tile": 0.98, "card": 0.98, "slideshow": 0.985 },
  "breakpoint": { "compact": 0, "medium": 600, "expanded": 840 }
}
```

---

## Appendix B — Flutter recipes (shape of the shared components; build them from §5)

```dart
import 'package:picspace_design_system/picspace_design_system.dart';

// Text: token style + token colour.
Text('Albums', style: AppTypography.sectionHeading.copyWith(color: AppColors.foreground));
Text('12 items', style: AppTypography.support.copyWith(color: AppColors.foregroundSecondary));

// Reduced-motion-safe animation.
AnimatedOpacity(opacity: shown ? 1 : 0, duration: context.motion(AppMotion.short), child: child);

// A spring-driven pop (allow-listed widgets only).
AnimatedScale(scale: shown ? 1 : 0.4, duration: context.motion(SpringCurve.popCurve.duration), curve: SpringCurve.popCurve, child: child);

// Press feedback on a tappable (the child keeps its own tap handling).
PressScale(pressedScale: 0.98, child: GestureDetector(onTap: onTap, child: card));

// A ⋮ menu that builds its entries when opened.
AppMenuButton.lazy(entriesBuilder: () => [
  AppMenuEntry(icon: AppIcons.refresh, label: 'Refresh', onTap: refresh),
]);

// A confirmation (title is a question, confirm is a verb).
final ok = await showAppConfirmDialog(context, title: 'Delete album?', body: 'Photos stay in your library.', confirmLabel: 'Delete');

// One line of text from the user.
final name = await showAppTextDialog(context, title: 'New album', confirmLabel: 'Create', hint: 'Album name');

// A sheet.
await showAppSheet<void>(context, builder: (_) => Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
  Text('Grid size', style: AppTypography.sectionHeading.copyWith(color: AppColors.foreground)),
  const SizedBox(height: AppSpacing.md),
  // … content …
]));

// Feedback that does not navigate.
showAppMessage(context, 'Library refreshed');

// A bar whose content morphs (never a second bar).
FloatingBarRow(
  contentKey: selecting ? 'selection' : 'nav',
  leading: GlassCircleButton(icon: AppIcons.close, semanticLabel: 'Exit selection', onPressed: clear),
  showLeading: selecting,
  child: GlassActionBar(surface: false, actions: [
    GlassAction(icon: AppIcons.share, label: 'Share', onPressed: share),
  ]),
);

// Empty / error / permission.
const EmptyState(icon: AppIcons.liked, title: 'Nothing liked yet', body: 'Tap ♡ on a photo or video to find it here.');

// A card of any collection.
CollectionCard(title: 'Beach', count: 42, cover: coverItem, onTap: open);

// Open a listing page over the app (back + capsule + ⋮ header comes with it).
openLibraryPage(context, title: 'Beach', subtitle: '42 photos', query: query);
```

Add to a scroll view the padding the shell hands you: `padding: EdgeInsets.fromLTRB(16, MediaQuery.paddingOf(context).top, 16, MediaQuery.paddingOf(context).bottom)`.

---

## Appendix C — Icon catalogue (`AppIcons`, generated; Stratis UI)

`…Filled` is the same glyph at stroke 2.1 (selected state). Map your icon component to these names; `…Filled` = same glyph at stroke 2.1 (never a colour change).

| Token | Stratis file (`ICONS/`) | Use | Filled variant |
|---|---|---|---|
| `photos` | `image-02` | Photos section, All photos tab. | `photosFilled` |
| `cleanup` | `eraser-01` | Cleanup section. | `cleanupFilled` |
| `editing` | `audio-settings-01` | Editing section. | `editingFilled` |
| `files` | `folder` | Files section. | `filesFilled` |
| `converters` | `arrow-switch-horizontal-1` | Converters section. | `convertersFilled` |
| `liked` | `heart` | Liked tab, like action. | `likedFilled` |
| `albums` | `layers-02` | Albums tab. | `albumsFilled` |
| `explore` | `compass-1` | Explore tab. | `exploreFilled` |
| `duplicates` | `copy-left` | Cleanup: Duplicates. | `duplicatesFilled` |
| `similar` | `layers-04` | Cleanup: Similar. | `similarFilled` |
| `screenshots` | `iphone-02` | Screenshots. | `screenshotsFilled` |
| `blurry` | `drop` | Cleanup: Blurry. | `blurryFilled` |
| `largeFiles` | `server-03` | Cleanup: Large files. | `largeFilesFilled` |
| `edit` | `pencil-01` | Editing: Edit. | `editFilled` |
| `collage` | `layout-grid-01` | Editing: Collage. | `collageFilled` |
| `drafts` | `file-02` | Editing: Drafts. | `draftsFilled` |
| `browse` | `folder-open-01` | Files: Browse. | `browseFilled` |
| `recent` | `clock-backward` | Files: Recent, recent searches. | — |
| `favorites` | `star-01` | Files: Favorites. | `favoritesFilled` |
| `storage` | `pie-chart-01` | Files: Storage. | `storageFilled` |
| `allTools` | `grid-01` | Converters: All tools. | `allToolsFilled` |
| `images` | `image-01` | Converters: Images. | `imagesFilled` |
| `pdf` | `file-04` | Converters: PDF. | `pdfFilled` |
| `documents` | `file-05` | Converters: Documents. | `documentsFilled` |
| `media` | `media-strip-02` | Converters: Media. | `mediaFilled` |
| `utilities` | `wrench` | Converters: Utilities. | `utilitiesFilled` |
| `search` | `search-01` | Search. | — |
| `searchOff` | `search-02` | No search results. | — |
| `add` | `plus-01` | Add, New album. | — |
| `close` | `x-01` | Close. | — |
| `check` | `check-01` | Confirm. | — |
| `back` | `arrow-left` | Back. | — |
| `more` | `dot-vertical` | Overflow menu. | — |
| `share` | `share-1` | Share. | — |
| `info` | `information-circle-contained` | Details. | — |
| `trash` | `trash-01` | Move to trash. | `trashFilled` |
| `deleteForever` | `trash-03` | Delete permanently. | — |
| `restore` | `arrow-rotate-left-01` | Restore from trash. | — |
| `refresh` | `arrow-refresh-01` | Refresh. | — |
| `sort` | `sort-vertical-01` | Sort. | — |
| `reorder` | `sort-vertical-02` | Reorder albums. | — |
| `dragHandle` | `menu-01` | Drag handle. | — |
| `select` | `check-contained` | Select, selected. | `selectFilled` |
| `selectAll` | `check-square-contained` | Select all. | — |
| `unchecked` | `circle` | Unchecked. | — |
| `removeFrom` | `minus-circle-contained` | Remove from album. | — |
| `addToAlbum` | `add-square-01` | Add to album. | — |
| `addPhotos` | `image-add` | Add photos. | — |
| `cover` | `image-focus` | Set cover. | — |
| `hide` | `eye-closed` | Hide, remove this memory. | — |
| `filterOff` | `filter` | No matches for the filter. | — |
| `settings` | `settings` | Settings. | — |
| `lock` | `lock-01` | Locked, access off. | — |
| `error` | `alert-circle` | Error. | — |
| `clear` | `x-02` | Clear text. | `clearFilled` |
| `chevron` | `chevron-right` | Row chevron. | — |
| `play` | `play-03` | Play, video badge. | `playFilled` |
| `playCircle` | `play-03` | Play overlay. | `playCircleFilled` |
| `pause` | `pause-03` | Pause. | `pauseFilled` |
| `video` | `video-on` | Videos. | — |
| `brokenImage` | `image-x` | Image failed to load. | — |
| `photo` | `image-01` | A photo. | — |
| `hourglass` | `hourglass-01` | Coming soon. | — |
| `people` | `users-profiles-01` | People. | `peopleFilled` |
| `person` | `user-profile-01` | One person. | `personFilled` |
| `places` | `marker-02` | Places. | `placesFilled` |
| `trips` | `plane` | Trips. | `tripsFilled` |
| `things` | `stars` | Things. | `thingsFilled` |
| `pets` | `feather-01` | Pets and animals. | `petsFilled` |
| `memories` | `clock-backward` | Memories. | — |
| `merge` | `union` | Merge people. | — |
| `face` | `face-id-01` | Face grouping. | — |
| `calendar` | `calendar-01` | Years. | — |
| `nature` | `sun-02` | Nature. | `natureFilled` |
| `sky` | `sun-down` | Sky and sunsets. | `skyFilled` |
| `beach` | `wind-02` | Beaches. | `beachFilled` |
| `flower` | `feather-02` | Flowers and plants. | `flowerFilled` |
| `food` | `wind-03` | Food. | `foodFilled` |
| `building` | `home-01` | Architecture and cities. | `buildingFilled` |
| `vehicle` | `car` | Vehicles. | `vehicleFilled` |
| `art` | `palette` | Art. | `artFilled` |
| `receipt` | `receipt-lines` | Documents and receipts. | `receiptFilled` |
| `selfie` | `face-id-02` | Selfies. | `selfieFilled` |
| `location` | `target-01` | Location access. | — |
| `shieldCheck` | `shield-check` | Privacy. | — |
| `volume` | `volume-05` | Sound on. | — |
| `mute` | `volume-07` | Sound off. | — |
| `rotate` | `arrow-rotate-right-01` | Rotate. | — |
| `download` | `download-02` | Save, download. | — |
| `zoomIn` | `maximise-01` | Zoom in. | — |
| `favorite` | `heart` | Favourite action. | `favoriteFilled` |
| `menu` | `menu-01` | Menu. | — |

---

## Appendix D — Reference algorithms (TypeScript; port to any language)

Pure functions, no dependencies. The spring easings produced by `cssSpring` equal the ones in §13.2 exactly (verified in Node): `cssSpring(400, 40, 496)`, `cssSpring(380, 27.3, 580)`, `cssSpring(500, 27.7, 516)`, `cssSpring(600, 39.2, 392)`.

```ts
// Spring position 0 -> 1 (start velocity 0, mass 1) at time t seconds. Same model as Flutter SpringSimulation,
// SwiftUI interpolatingSpring(mass:1, stiffness:, damping:), Framer Motion {type:"spring"}.
export function springAt(k: number, c: number, t: number): number {
  const disc = c * c - 4 * k;                       // mass = 1
  if (Math.abs(disc) < 1e-9) {                      // critically damped (settle: k 400, c 40)
    const r = -c / 2;
    return 1 + (-1 + r * t) * Math.exp(r * t);
  }
  if (disc > 0) {                                   // over-damped
    const r1 = (-c - Math.sqrt(disc)) / 2, r2 = (-c + Math.sqrt(disc)) / 2;
    const c2 = r1 / (r2 - r1), c1 = -1 - c2;
    return 1 + c1 * Math.exp(r1 * t) + c2 * Math.exp(r2 * t);
  }
  const w = Math.sqrt(4 * k - c * c) / 2, r = -c / 2; // under-damped (soft, pop, menu)
  const c2 = r / w;                                  // from x(0)=0, x'(0)=0 with c1 = -1
  return 1 + Math.exp(r * t) * (-Math.cos(w * t) + c2 * Math.sin(w * t));
}
// CSS linear() easing for a spring: sample over its settle time (ms), then use transition-duration = settleMs.
export function cssSpring(k: number, c: number, settleMs: number, samples = 28): string {
  const pts = Array.from({ length: samples + 1 }, (_, i) => +springAt(k, c, (settleMs * i) / samples / 1000).toFixed(4));
  pts[samples] = 1;
  return `linear(${pts.join(", ")})`;
}

// Liquid highlight of the nav pill: left/right edge at fractional item `position`.
// direction +1 = towards higher indexes. Leading edge p^0.7 (races ahead), trailing edge p^1.4 (lingers).
export function liquidHighlightEdges(position: number, count: number, direction: 1 | -1, item = 48, pad = 4, gap = 4): [number, number] {
  const step = item + gap, p = Math.min(Math.max(position, 0), count - 1), i = Math.floor(p), f = p - i;
  const L = (k: number) => pad + k * step, R = (k: number) => L(k) + item, lerp = (a: number, b: number, t: number) => a + (b - a) * t;
  if (f < 1e-4 || i >= count - 1) return [L(i), R(i)];
  if (direction >= 0) return [lerp(L(i), L(i + 1), f ** 1.4), lerp(R(i), R(i + 1), f ** 0.7)];
  const g = 1 - f;
  return [lerp(L(i + 1), L(i), g ** 0.7), lerp(R(i + 1), R(i), g ** 1.4)];
}

// Black fade that lets content dissolve under a bar. t = 0 at the bar's edge, 1 at the far end. 13 stops.
export const fadeScrimAlpha = (t: number, strength = 1) => Math.min(1, Math.max(0, 0.94 * strength * (1 - t) ** 2.2));

// Padding your scroll content needs so it scrolls UNDER the floating bars (title row 56, bar 56, margins 8, gap 16).
export function shellInsets(safeTop: number, safeBottom: number) {
  const headerBottom = safeTop + 8 + 56 + 56 + 8;   // = safeTop + 128
  const footerTop = safeBottom + 8 + 56 + 8;        // = safeBottom + 72
  return { contentTop: headerBottom, contentBottom: footerTop + 16, topFade: headerBottom + 32, bottomFade: footerTop + 32 };
}

// Non-modal anchored menu: below the anchor in the upper half of the screen, above it in the lower half.
export function menuPlacement(a: { left: number; top: number; right: number; bottom: number }, vw: number, vh: number, w: number, h: number, safeTop = 0, safeBottom = 0) {
  const alignRight = (a.left + a.right) / 2 > vw / 2, above = (a.top + a.bottom) / 2 > vh / 2;
  let x = alignRight ? a.right - w : a.left, y = above ? a.top - 8 - h : a.bottom + 8;
  x = Math.min(Math.max(x, 16), vw - 16 - w);
  y = Math.min(Math.max(y, safeTop + 8), vh - safeBottom - 8 - h);
  return { x, y, transformOrigin: `${alignRight ? "right" : "left"} ${above ? "bottom" : "top"}` };
}

// Close-drag of a full-screen viewer (vertical drag): progress = |dy| / 240.
export function closeDrag(dy: number) {
  const p = Math.min(1, Math.abs(dy) / 240);
  return { scale: 1 - 0.12 * p, backdropAlpha: 1 - p, chromeOpacity: Math.min(1, Math.max(0, 1 - 3 * p)) };
}
export const shouldClose = (dy: number, vy: number) => Math.abs(dy) > 120 || (Math.abs(vy) > 700 && (dy === 0 || Math.sign(vy) === Math.sign(dy)));
```

---

## Appendix E — Flutter token source (copy as-is into `lib/design/`)

These files are self-contained (Flutter SDK only). `typography.dart` expects the `AppSerif` and `Inter` font families declared in `pubspec.yaml` (`AppSerif` → `Arapey-Regular.ttf`, one weight; `Inter` → `Inter-Variable.ttf`) under a package named `picspace_design_system`, or change `AppFonts.package`/`bodyInTheme` to your package name.

**`colors.dart`**

```dart
import 'package:flutter/painting.dart';

/// The whole palette: black, white and dark grey, plus opacity
/// variants of those three. No other hue exists in the app.
abstract final class AppColors {
  /// Every background.
  static const Color background = Color(0xFF000000);

  /// All text and icons.
  static const Color foreground = Color(0xFFFFFFFF);

  /// Buttons, cards, boxes, bars, sheets: near-black, never pure black.
  static const Color surface = Color(0xFF1A1A1A);

  /// Secondary text over photos (white 80%): memory card subtitles.
  static const Color foregroundOnPhoto = Color(0xCCFFFFFF);

  /// Secondary text and icons (white 60%).
  static const Color foregroundSecondary = Color(0x99FFFFFF);

  /// Disabled text and icons (white 38%).
  static const Color foregroundDisabled = Color(0x61FFFFFF);

  /// 1 dp borders and dividers (white 10%).
  static const Color divider = Color(0x1AFFFFFF);

  /// Selected or pressed highlight (white 12%).
  static const Color highlight = Color(0x1FFFFFFF);

  /// Tint over the blurred backdrop of glass bars (dark grey 70%).
  static const Color glassFill = Color(0xB31A1A1A);

  /// Modal scrim and top/bottom fades (black 60%).
  static const Color scrim = Color(0x99000000);
}
```

**`typography.dart`**

```dart
import 'package:flutter/painting.dart';

/// Font families. Both are bundled as assets, never fetched at run time.
abstract final class AppFonts {
  /// Package that owns the font assets.
  static const String package = 'picspace_design_system';

  /// Headings. One family name for whichever serif is bundled (see the font declaration in the package's
  /// pubspec.yaml: Arapey Regular for now, Scotch Deck Light when the file is supplied). It ships one weight, so
  /// heading styles never ask for bold.
  static const String heading = 'AppSerif';

  /// Body and chrome.
  static const String body = 'Inter';

  /// [body] as a theme-level family name (a `ThemeData` has no `package` argument).
  static const String bodyInTheme = 'packages/$package/$body';
}

/// Type scale. Colour is applied by components.
///
/// Arapey is thin, so no Arapey style is smaller than 18 sp. On photos, add [onPhotoShadow].
abstract final class AppTypography {
  /// Arapey 40/48: onboarding and the memory title card.
  static const TextStyle display = TextStyle(
    fontFamily: AppFonts.heading,
    package: AppFonts.package,
    fontSize: 40,
    height: 48 / 40,
    fontWeight: FontWeight.w400,
    letterSpacing: -0.5,
  );

  /// Arapey 42/48: the large section title (Photos, Cleanup, ...) that scrolls away with the page.
  static const TextStyle screenTitle = TextStyle(
    fontFamily: AppFonts.heading,
    package: AppFonts.package,
    fontSize: 42,
    height: 48 / 42,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.5,
  );

  /// Arapey 28/34: section headings ("Memories", "My albums"), dialog titles.
  static const TextStyle sectionHeading = TextStyle(
    fontFamily: AppFonts.heading,
    package: AppFonts.package,
    fontSize: 28,
    height: 34 / 28,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.4,
  );

  /// Inter 9/10 w700: a tiny number inside an icon (the "10" on the skip-ten-seconds buttons).
  static const TextStyle micro = TextStyle(
    fontFamily: AppFonts.body,
    package: AppFonts.package,
    fontSize: 9,
    height: 10 / 9,
    fontWeight: FontWeight.w700,
  );

  /// Arapey 24/30: titles over photo cards (places, trips, memories).
  static const TextStyle cardHeading = TextStyle(
    fontFamily: AppFonts.heading,
    package: AppFonts.package,
    fontSize: 24,
    height: 30 / 24,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.3,
  );

  /// Arapey 38/46: the title card at the start of a memory.
  static const TextStyle storyTitle = TextStyle(
    fontFamily: AppFonts.heading,
    package: AppFonts.package,
    fontSize: 38,
    height: 46 / 38,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.4,
  );

  /// Arapey 20/26: day headers in the grid, memory subtitles (upright: no italics anywhere).
  static const TextStyle heading3 = TextStyle(
    fontFamily: AppFonts.heading,
    package: AppFonts.package,
    fontSize: 20,
    height: 26 / 20,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.3,
  );

  /// Inter 15/20 w600: card titles.
  static const TextStyle cardTitle = TextStyle(
    fontFamily: AppFonts.body,
    package: AppFonts.package,
    fontSize: 15,
    height: 20 / 15,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.1,
    fontVariations: <FontVariation>[FontVariation.weight(600)],
  );

  /// Inter 14/20 w400: body text.
  static const TextStyle body = TextStyle(
    fontFamily: AppFonts.body,
    package: AppFonts.package,
    fontSize: 14,
    height: 20 / 14,
    letterSpacing: 0.2,
    fontVariations: <FontVariation>[FontVariation.weight(400)],
  );

  /// Inter 14/20 w500: names under circles, list labels.
  static const TextStyle label = TextStyle(
    fontFamily: AppFonts.body,
    package: AppFonts.package,
    fontSize: 14,
    height: 20 / 14,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.2,
    fontVariations: <FontVariation>[FontVariation.weight(500)],
  );

  /// Inter 13/18 w400: supporting text.
  static const TextStyle support = TextStyle(
    fontFamily: AppFonts.body,
    package: AppFonts.package,
    fontSize: 13,
    height: 18 / 13,
    letterSpacing: 0.2,
    fontVariations: <FontVariation>[FontVariation.weight(400)],
  );

  /// Inter 12/16 w400: dates and sizes.
  static const TextStyle caption = TextStyle(
    fontFamily: AppFonts.body,
    package: AppFonts.package,
    fontSize: 12,
    height: 16 / 12,
    letterSpacing: 0.3,
    fontVariations: <FontVariation>[FontVariation.weight(400)],
  );

  /// Inter 12/16 w500: navigation and chip labels.
  static const TextStyle tabLabel = TextStyle(
    fontFamily: AppFonts.body,
    package: AppFonts.package,
    fontSize: 12,
    height: 16 / 12,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.4,
    fontVariations: <FontVariation>[FontVariation.weight(500)],
  );

  /// Inter 14/20 w600: button labels.
  static const TextStyle button = TextStyle(
    fontFamily: AppFonts.body,
    package: AppFonts.package,
    fontSize: 14,
    height: 20 / 14,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.1,
    fontVariations: <FontVariation>[FontVariation.weight(600)],
  );

  /// Subtle shadow that keeps white text readable on photos (memory cards, the player).
  static const List<Shadow> onPhotoShadow = [
    Shadow(color: Color(0x59000000), offset: Offset(0, 1), blurRadius: 2),
  ];
}
```

**`spacing.dart`**

```dart
/// Spacing, sizing and layout tokens.
abstract final class AppSpacing {
  /// Base unit; all spacing is a multiple.
  static const double unit = 4;

  /// 4 dp.
  static const double xs = 4;

  /// 8 dp.
  static const double sm = 8;

  /// 12 dp.
  static const double md = 12;

  /// 16 dp.
  static const double lg = 16;

  /// 24 dp.
  static const double xl = 24;

  /// 32 dp.
  static const double xxl = 32;

  /// Minimum tappable size.
  static const double touchMin = 48;

  /// Visible diameter of a small circle button (its touch area is still [touchMin]).
  static const double smallCircle = 40;

  /// Height of a capsule label (the viewer's date and time).
  static const double capsuleHeight = 32;

  /// Gutter between photo grid tiles.
  static const double photoGutter = 2;

  /// Horizontal inset of the floating bars from the screen edge.
  static const double floatingMarginH = 12;

  /// Vertical inset of the floating bars from the system insets.
  static const double floatingMarginV = 8;

  /// Gap between a floating bar and its companion circle button.
  static const double floatingGap = 6;

  /// Largest height of a floating bar and diameter of its circle button; `FloatingMetrics` steps it down on narrow screens.
  static const double floatingBarHeight = 56;

  /// Largest diameter of one icon item (and its highlight) inside a floating pill.
  static const double floatingItemSize = 48;

  /// Padding between a pill edge and its first/last item.
  static const double floatingPillPadding = 4;

  /// Gap between items inside a pill.
  static const double floatingItemGap = 4;

  /// Extra clearance between the last content row and a floating bar.
  static const double floatingContentGap = 16;

  /// Height of the large section title row that scrolls away above the upper pill.
  static const double screenTitleHeight = 56;

  /// How far a top or bottom fade reaches past the floating bar it belongs to.
  static const double fadeExtra = 32;
}
```

**`radii.dart`**

```dart
/// Corner radii.
abstract final class AppRadii {
  /// 8 dp.
  static const double sm = 8;

  /// 12 dp: cards, menus, text fields.
  static const double md = 12;

  /// 16 dp.
  static const double lg = 16;

  /// 28 dp: dialogs and sheet tops.
  static const double dialog = 28;

  /// 4 dp: photo tiles.
  static const double thumb = 4;

  /// Fully rounded.
  static const double pill = 999;
}
```

**`glass.dart`**

```dart
/// Frosted-glass tokens for the floating navigation bars.
abstract final class AppGlass {
  /// Gaussian blur sigma behind glass surfaces. Tune by profile-mode measurement.
  static const double blurSigma = 24;
}
```

**`motion.dart`**

```dart
import 'package:flutter/widgets.dart';

/// Durations and curves. Reduced motion is honoured through
/// [AppMotionContext]: springs and slides become short fades or jumps.
abstract final class AppMotion {
  /// 90 ms: press feedback, toggles.
  static const Duration instant = Duration(milliseconds: 90);

  /// 180 ms: menus, chips, fades, nav indicator.
  static const Duration short = Duration(milliseconds: 180);

  /// 280 ms: screens, sheets, scroll-to-top.
  static const Duration standard = Duration(milliseconds: 280);

  /// 420 ms: page and hero transitions (viewer open, memory open).
  static const Duration long = Duration(milliseconds: 420);

  /// 480 ms: a surface changing shape (the section pill growing into the search field): deliberately slow.
  static const Duration morph = Duration(milliseconds: 480);

  /// 6 s: a floating menu nobody touches closes by itself after this long.
  static const Duration menuIdleClose = Duration(seconds: 6);

  /// 4 s: one slide of a memory.
  static const Duration story = Duration(milliseconds: 4000);

  /// 2.5 s: how long a memory's title card stays over its first photo.
  static const Duration storyTitle = Duration(milliseconds: 2500);

  /// Default curve.
  static const Curve standardCurve = Cubic(0.2, 0, 0, 1);

  /// Enter curve.
  static const Curve decel = Cubic(0.05, 0.7, 0.1, 1);

  /// Exit curve.
  static const Curve accel = Cubic(0.3, 0, 0.8, 0.15);

  /// Constant speed: progress bars, Ken Burns.
  static const Curve linear = Curves.linear;
}

/// Reduced-motion helpers on [BuildContext].
extension AppMotionContext on BuildContext {
  /// Whether the user asked the system to reduce animation.
  bool get reduceMotion => MediaQuery.disableAnimationsOf(this);

  /// [duration], or [Duration.zero] when motion is reduced.
  Duration motion(Duration duration) => reduceMotion ? Duration.zero : duration;

  /// [duration], or a 100 ms fade when motion is reduced (for effects that would otherwise be springs or slides).
  Duration motionOrFade(Duration duration) =>
      reduceMotion ? const Duration(milliseconds: 100) : duration;
}
```

**`springs.dart`**

```dart
import 'package:flutter/animation.dart';
import 'package:flutter/physics.dart';

/// Spring tokens. `ζ = c / (2√k)`.
///
/// Only the allow-listed widgets may use a spring that overshoots (like heart,
/// selection check, FAB, menu, dialog, person cover, success check); everything
/// else uses [settle] or a curve from `AppMotion`.
abstract final class AppSprings {
  /// k 400, c 40, ζ 1.0, no overshoot: indicator settle, sheet settle, zoom release.
  static const SpringDescription settle = SpringDescription(
    mass: 1,
    stiffness: 400,
    damping: 40,
  );

  /// k 380, c 27.3, ζ 0.70, about 4.6% overshoot: dialogs, chips, press release, list inserts.
  static const SpringDescription soft = SpringDescription(
    mass: 1,
    stiffness: 380,
    damping: 27.3,
  );

  /// k 500, c 27.7, ζ 0.62, about 8.4% overshoot: heart, selection check, FAB, success check.
  static const SpringDescription pop = SpringDescription(
    mass: 1,
    stiffness: 500,
    damping: 27.7,
  );

  /// k 600, c 39.2, ζ 0.80, about 1.5% overshoot: popup menus.
  static const SpringDescription menu = SpringDescription(
    mass: 1,
    stiffness: 600,
    damping: 39.2,
  );
}

/// A [Curve] that follows a spring from 0 to 1, so a spring can drive a fixed-duration
/// controller. Values may exceed 1 (overshoot). `t = 1` is the moment the spring has settled.
class SpringCurve extends Curve {
  /// Creates the curve for [spring].
  SpringCurve(this.spring)
    : _simulation = SpringSimulation(spring, 0, 1, 0),
      duration = _settleTime(spring);

  /// The spring followed.
  final SpringDescription spring;

  /// Time the spring needs to come to rest within tolerance.
  final Duration duration;

  final SpringSimulation _simulation;

  static Duration _settleTime(SpringDescription spring) {
    final sim = SpringSimulation(spring, 0, 1, 0);
    var ms = 0;
    while (ms < 3000 && !sim.isDone(ms / 1000)) {
      ms += 4;
    }
    return Duration(milliseconds: ms);
  }

  @override
  double transformInternal(double t) =>
      _simulation.x(t * duration.inMilliseconds / 1000);

  /// The shared curves, built once.
  static final SpringCurve settleCurve = SpringCurve(AppSprings.settle);

  /// Soft spring curve.
  static final SpringCurve softCurve = SpringCurve(AppSprings.soft);

  /// Pop spring curve.
  static final SpringCurve popCurve = SpringCurve(AppSprings.pop);

  /// Menu spring curve.
  static final SpringCurve menuCurve = SpringCurve(AppSprings.menu);
}
```

**`haptics.dart`**

```dart
import 'package:flutter/services.dart';

/// Haptic feedback. The platform applies the user's
/// "touch feedback" setting, so nothing here needs to check it.
abstract final class AppHaptics {
  /// Select toggle and tab change.
  static void selection() => HapticFeedback.selectionClick();

  /// Like.
  static void light() => HapticFeedback.lightImpact();

  /// Long-press that starts selection, or lifts an item to reorder it.
  static void medium() => HapticFeedback.mediumImpact();
}
```

**`floating_metrics.dart`**

```dart
import 'package:flutter/widgets.dart';

// (import spacing.dart)

/// Size of the floating bars for the current screen width.
///
/// Wide phones get a 56 dp bar with 22 dp icons and 48 dp items; narrower screens keep the bar but use
/// 20 dp icons. Every tappable item stays at least 48 dp. A pill that cannot fit scrolls sideways.
@immutable
class FloatingMetrics {
  const FloatingMetrics._(this.bar, this.icon);

  /// Height of a floating bar and diameter of its circle buttons.
  final double bar;

  /// Icon size inside bars.
  final double icon;

  /// Diameter of every circle button beside a bar (search, close, more): one size everywhere, a little
  /// smaller than the bar so the pair reads as a bar with a companion.
  double get circle => AppSpacing.touchMin;

  /// Largest side of one item inside a pill: the bar minus its padding.
  double get item => bar - 2 * AppSpacing.floatingPillPadding;

  /// Smallest item side (tap target).
  static const double minItem = AppSpacing.touchMin;

  /// Metrics for a screen [width] in dp.
  static FloatingMetrics forWidth(double width) {
    if (width >= 340) return const FloatingMetrics._(56, 22);
    return const FloatingMetrics._(56, 20);
  }

  /// Metrics for the screen [context] is on.
  static FloatingMetrics of(BuildContext context) =>
      forWidth(MediaQuery.sizeOf(context).width);

  /// Item side for [count] items that have to fit in [maxWidth]: as big as allowed, never below [minItem].
  double itemFor(double maxWidth, int count) {
    if (!maxWidth.isFinite) return item;
    final room =
        maxWidth -
        2 * AppSpacing.floatingPillPadding -
        (count - 1) * AppSpacing.floatingItemGap;
    return (room / count).clamp(minItem, item);
  }
}
```
