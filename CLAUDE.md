# PicSpace — CLAUDE.md

Governing file for every Claude Code session. Read it fully. Detailed rules live in `rules.md`: **read the matching section BEFORE working in that area** (rule IDs like `R-PERF-3` are cited in plans and reports).

Tags: **[PROPOSED]** = does not exist yet; never imply it does. **[verify]** = platform/library fact to confirm against current official docs before relying on it. Keep this file lean: a rule needing more than 3 lines belongs in `rules.md` or an ADR.

---

## 0. Newest owner rules (2026-10-12; override anything below that conflicts) — detail: `rules.md` §16–§19

1. **Real only, no demos.** Everything you build must work and use real data (the device's real photos/files). No mock data, fake lists, dead buttons, stub screens, or "looks done" UI in shipped code. Fakes live only in `test/`. A control/tab that does not work yet is not rendered (except the owner-approved "Coming soon" sections: Cleanup, Editing, Files, Converters).
2. **Verify on the connected device** (`flutter devices`, `flutter run`, `adb exec-out screencap`) before saying anything is ready. If you cannot, say "not verified".
3. **Three colours only:** black `#000000` background, white `#FFFFFF` text/icons, dark grey `#1A1A1A` for buttons/boxes/bars (opacity variants of these only). Dark theme only. No accent colours.
4. **Clean layout:** no overlapping/clipped text, no odd gaps; match owner reference images (floating glass pills that hug their content, centered, icon-only with a circle highlight). Check overflow at 320/360/411 dp and text scale 1.0/1.3/2.0.
5. Follow the engineering standard in `rules.md` (modular, reusable, no duplication, cleanup, error handling, config, README, tests).
6. **Type and icons:** serif headings (`AppSerif`: Arapey until the owner supplies the licensed Scotch Deck Light file he asked for), upright only (no italics), big section titles; one thin icon family (Stratis, stroke 1.5) through `AppIcons`; small chrome (bar 56, compact circle 40, capsule 32).
7. **Search is one morphing bar:** the top pill itself grows into the search field (no second bar); the search circle keeps its size and its icon becomes X; each tab declares its own search scope or none.
8. **Background analysis is invisible and never silent:** no scan banners or progress text; people, places and scenes appear as found; every failure is typed and visible in Diagnostics (R-PHX).
9. **Timeline:** full length known up front, skeleton for unloaded parts, the part in view loads first, nothing may stall the scrubber.
11. **One chrome (`rules.md` §20):** a single lower bar morphs between the section pill, the selection actions and the viewer's actions (elongate, then icons pop in); every circle beside a bar is 48, every pushed page and the viewer share `PageHeader` (back 40, capsule 32); "5 selected" lives in the top bar, not in the big title. Explore always shows every section.
12. **Menus are non-modal and close themselves** (`rules.md` §20.10): a tap outside closes the menu and still reaches what is under it; 6 s untouched closes it; use `showAppMenu`/`AppMenuButton` only. **Video shows one thin line** (§20.11) that leaves 2 s after playback starts; play/pause and mute live in the lower bar.
13. **Models never run in the app process:** faces, scenes, places and Smart search embeddings are made in the `:analysis` process and handed over through an inbox (ADR 0007), so a native crash cannot close the app; analysis may also run while charging. The library comes from the media index (ADR 0009); thumbnails are files at computed paths, warmed for the whole library.
10. **Network only on request:** the app uses the network for one thing, the Smart search model download the user starts with a button (ADR 0006: disclosure in the sheet, size and hash checked, nothing about the user sent, photos never leave the phone). No other network call, analytics or crash reporting without a new ADR.
14. **Faces only in camera photos** (owner, 2026-10-15): faces are looked for only in photos saved in the camera's folder, `DCIM/Camera` (not screenshots, saved or received pictures, nor other apps' folders under `DCIM/`), and a detection below 0.90 is not a face (ADR 0008 addendum). Android code that touches the platform (decoders, models, SQLite, services) is checked on a phone with `tools/bench/device-tests.ps1`: the JVM tests could not see a decoder that failed on every photo, and nothing appeared on Explore for a day.

---

## 1. Product

PicSpace is a Flutter/Dart photo + file super-app. **Android-first** (assumption; no iOS/desktop-specific code until `docs/product` says so).

- Upper navigation (5 sections): **Photos | Cleanup | Editing | Files | Converters**
- Converters lower navigation: **All Tools | Images | PDF | Documents | Media | Utilities**
- Many more features are coming in every section. Design for growth; build only what a spec requires.

**Converters catalog** (canonical copy: `docs/product/converters.md` [PROPOSED — save the final spec there]):
- **Images:** Converter (JPG/PNG/WebP/HEIC/BMP), Resizer, Compressor, Batch Converter, Image→PDF, Background Remover, Upscaler/Enhancer
- **PDF:** PDF→Images, Images→PDF, Merge, Split, Compress, PDF→Word, Word→PDF, Rotate/Reorder, Extract Pages, OCR, Sign/Annotate
- **Documents:** Word (DOCX/PDF), Excel (XLSX/CSV/PDF), PowerPoint→PDF, Text→PDF, Markdown→PDF, Document Scanner→PDF
- **Media:** Video Converter/Compressor/Trimmer, Video→GIF, Video→Audio, Audio Converter/Trimmer
- **Utilities:** ZIP Extractor/Creator, QR Generator/Scanner, Batch Renamer, File Size & Metadata Viewer

**Phases.** P1: Image Converter, Resizer, Compressor, Batch Converter, Image→PDF, PDF→Images, Merge, Split, Compress PDF, PDF→Word, Word→PDF, QR. P2: OCR, Document Scanner, Excel/PowerPoint, ZIP, Background Remover, Upscaler/Enhancer, Video→Audio, Audio Converter. P3: Video Converter/Compressor/Trimmer, Video→GIF, remaining utilities. MUST NOT start a later phase while the current one is incomplete unless explicitly asked.

**Hub requirements:** search across all tools; recents; favorites/pinned; popular; category browsing; batch where supported; conversion queue with progress + cancellation; history (open/share/rename/delete); output preview before saving; configurable format/quality/resolution; clear errors + retry; **local processing by default**; validate outputs before reporting success; handle unsupported formats/failures; **never overwrite originals without explicit user approval**.

## 2. Source of truth (highest first)

1. Explicit decisions from the owner. 2. Canonical PRD / feature specs (`docs/product/`). 3. UI/UX specs (`docs/design/`). 4. ADRs (`docs/adr/`). 5. Existing code, after evaluating it. 6. Current official docs / measured evidence. 7. Engineering judgment, assumptions stated.

- MUST read the relevant product spec before implementing a feature and the design spec before touching its UI.
- MUST NOT invent screens, buttons, menus, flows, copy, APIs, models, styles, or performance guarantees. Missing spec → say so, state the assumption, ask or propose; do not silently decide.
- Spec conflicts → surface them; never resolve silently.
- Cleanup, Editing, and Files have no specs in this file; read their docs first or ask.

## 3. Engineering stance

- **Flutter + Dart by default.** Escalate in this order only with evidence: Dart worker isolate → Kotlin/Android platform API → C++ via FFI (`R-NATIVE`).
- **Move paths/URIs, not pixels/bytes**, across isolates, channels, and FFI.
- **UI isolate renders; it does not compute.** All long work is a cancellable, observable, resource-budgeted **Job**.
- **Measure, then optimize.** No "faster"/"smooth" claim without before/after numbers on a real device in profile mode.
- **Smallest cohesive change.** Fewest justified concepts, dependencies, and files; never fewest files at the cost of clarity.
- **Correctness and data integrity outrank speed.**
- Proposed defaults (ratify by ADR on first use; if the existing repo already uses a working alternative, keep it): Riverpod (state), go_router (navigation), SQLite via Drift (storage), Pigeon (typed platform channels), ffigen (FFI bindings), Media3 Transformer (video/audio) [verify each].

## 4. Repository structure

**Target (all [PROPOSED] unless an audit proves otherwise).** Create a package/directory only when its first real code lands; never empty placeholders. If the actual repo differs, first write `docs/architecture/structure.md` mapping `[EXISTS]` → target and migrate in small dedicated steps. Never big-bang reorganize; never reorganize as a side effect of a feature task.

```
picspace/                          # monorepo, Dart pub workspace [verify workspace support in installed SDK]
├── CLAUDE.md  rules.md            # governance (rules.md may later split into .claude/rules/*.md with `paths:` globs)
├── pubspec.yaml                   # workspace root: member list only, no app dependencies
├── analysis_options.yaml          # single strict lint config; every package includes it
├── .github/workflows/             # CI (or existing CI dir): format, analyze, dep-boundary check, tests, build, bench-smoke
│
├── app/                           # the Flutter app = COMPOSITION ROOT ONLY
│   ├── lib/main.dart              # minimal: binding init -> runApp. No awaited I/O.
│   ├── lib/bootstrap/             # DI wiring, post-first-frame init sequencing, error zones, job-handler registration
│   ├── lib/shell/                 # 5-section upper-nav shell; lazy section build + state keep-alive
│   ├── lib/routing/               # route table, deep links, NavIntent handlers (cross-feature navigation)
│   ├── lib/flavors/               # dev/staging/prod constants, feature flags
│   ├── android/                   # THIN: manifest, signing, flavors, splash, R8. No business Kotlin.
│   ├── integration_test/          # cross-section end-to-end flows
│   └── test/                      # shell / routing / bootstrap tests
│
├── packages/
│   ├── core/                      # pure Dart, no Flutter: Result/Failure, FileRef/MediaRef, ids, clock, logging interface, CancelToken, NavIntent
│   ├── design_system/             # tokens (color/type/spacing/radius/elevation/motion/icon), theme, primitives, shared components, goldens
│   ├── platform/                  # Flutter plugin + Kotlin (Pigeon): MediaStore, SAF, photo picker, share/FileProvider, permissions,
│   │                              #   thumbnails, PdfRenderer, Media3, WorkManager/foreground service, memory/thermal signals
│   ├── native_core/               # Dart FFI wrappers over native/picspace_core; isolate-safe, ownership-safe; src/generated/ never hand-edited
│   ├── storage/                   # SQLite schema + migrations + DAOs: media index, FTS, conversion history, tool prefs (favorites/pins/recents)
│   ├── media/                     # thumbnail pipeline, ImageProviders, memory+disk caches, incremental MediaStore sync, EXIF/metadata, hashing
│   ├── jobs/                      # JOB ENGINE: Job model/state machine, priority lanes, resource budgets, worker isolates, cancellation,
│   │                              #   progress, persistence/recovery, output commit pipeline (temp -> validate -> preview -> commit)
│   ├── ai/                        # [P2] ModelManager (fetch/verify/evict), runtime adapters, pipelines (OCR, segmentation, upscaling, ...)
│   ├── converter_engine/          # headless (no widgets): ToolDescriptor registry, ToolRunners, option schemas, output validators
│   │   └── lib/src/{registry,image,pdf,document,media,utility,validation}/
│   └── features/                  # one package per top-level section; UI + UI state only
│       ├── photos/                # grid, viewer, albums, search (exact scope per PRD)
│       ├── converters/            # hub (catalog, search, recents/favorites/pinned/popular, category pages), tool screens, queue UI, history UI, lower nav
│       ├── files/                 # file manager (per PRD)
│       ├── cleanup/               # [later] per PRD
│       ├── editing/               # [later] non-destructive edit graph per PRD
│       └── settings/              # per PRD
│
├── native/
│   ├── picspace_core/             # C++17, ONE shared lib, C ABI: include/picspace/*.h, src/{image,pdf,archive,hash}/, tests/ (host GoogleTest + fuzz targets)
│   └── third_party/               # pinned vendored/submodule libs + LICENSE manifest
├── tools/                         # dev-only: ml/ (Python model convert/quantize/benchmark), fixtures/ (deterministic large/corrupt media),
│                                  #   bench/ (runners, trace analysis), scripts/ (dep-boundary + license check, size report)
├── testdata/                      # tiny committed fixtures + manifest (large ones generated, gitignored)
├── benchmarks/                    # startup, scroll, thumbnail, conversion benchmarks (profile mode)
└── docs/                          # product/ design/ architecture/ adr/ perf/(budgets.md, devices.md, baselines/) licenses/(deps + models manifest)
```

**Why this shape.** Packages make dependency direction compiler-enforced and builds/tests cacheable. `jobs` is separate from `converter_engine` because indexing, AI, and conversions all share one scheduler. `converter_engine` is headless so every tool is testable without UI and adding a tool never touches navigation. `native/` is one library with one C ABI so there is one toolchain, one lazy `dlopen`, and one place to harden parsers.

## 5. Dependencies and ownership

- Arrows point **down only**: `app → features → converter_engine → ai → jobs/media → storage/platform/native_core → core`. `design_system` is used by `features` and `app` only.
- **Features MUST NOT import features.** Cross-feature navigation = a `NavIntent` (in `core`) handled in `app/routing`. Cross-feature data = shared packages (`media`, `jobs`, `storage`), never feature internals.
- Only `design_system`, `media/providers`, `features/*`, and `app` may import Flutter widget libraries. `core`, `storage`, `jobs`, `ai`, `converter_engine` stay widget-free.
- UI MUST NOT call platform channels, FFI, SQL, or filesystem directly; only package APIs.
- State lives in the lowest layer that needs it; UI state in features; domain/process state in services. No global mutable singletons.
- Expected failures are values (`Result`/`Failure`: code, l10n message key, retryable, non-PII cause). Exceptions are for bugs and are caught at job/isolate/zone boundaries.
- New package/abstraction/dependency needs a justification (`R-ARCH`, `R-DEP`). Start features flat (`screens/ widgets/ state/`); add `domain/` or `data/` only when logic is shared, complex, or needs isolated testing.
- Boundary rules are enforced by a CI check [PROPOSED `tools/scripts/check_deps.dart`], not by convention alone.

## 6. Runtime invariants (do not violate without an ADR)

1. `main()` awaits no I/O. First frame = skeleton + persisted snapshot; everything else after first frame on low-priority lanes. Native libs, models, tool runners, and non-visible sections load lazily.
2. **Library truth = MediaStore.** The PicSpace DB is a derived index, synced incrementally (generation/modified cursors + change observer) [verify], never full-rescanned on launch. First paint reads the DB.
3. **Thumbnails:** request size = cell px × DPR, bucketed; never decode full-res for grid cells; byte-bounded memory + disk caches; in-flight dedup; cancel on cell dispose.
4. **Every long operation is a Job:** typed spec, state machine, progress, cooperative cancellation propagated to Kotlin/native, bounded concurrency, persisted for history/recovery, survives backgrounding via WorkManager/foreground service [verify FGS type for target SDK].
5. **Output pipeline:** write to app-private temp → validate → preview (if applicable) → commit to destination (collision-safe name, pending-flag/atomic where the platform allows) → verify → record history → clean temp. Originals are immutable. Overwrite/delete of originals needs explicit per-action user confirmation.
6. **Tools are data:** each converter is a `ToolDescriptor` (id, category, accepted inputs, options schema, capabilities, phase, lazy runner, validator). Catalog, search, categories, recents, favorites derive from the registry; no hard-coded tool lists in UI. Adding a tool follows the `R-TOOL` checklist.
7. Local-first: no network call, analytics, or crash-reporting SDK without an ADR + disclosure. (Only exception so far: the user-started Smart search model download, ADR 0006.) User media never leaves the device unless the PRD authorizes it and a privacy model exists.

## 7. Language policy

- **Dart** — default for everything: UI, orchestration, state, DB access, light/medium CPU work (in worker isolates, never UI).
- **Kotlin** — Android capabilities and platform codecs (MediaStore, SAF, MediaCodec/Media3, PdfRenderer, WorkManager). Coroutines, typed Pigeon APIs, no blocking the main thread.
- **C++17 (single native language)** — only for (a) capability absent in Dart/platform, or (b) profiler-proven hot loops/library-bound codecs (JPEG/WebP/HEIC encode-decode, PDF object ops, hashing, archive streaming) where gain survives FFI + copy cost. Needs an ADR with benchmark.
- **Python** — `tools/` only (model conversion/quantization, fixture generation, benchmark analysis). Never shipped in the app runtime.
- Rust/Java/Swift/others — not without an ADR. C++ is not automatically faster; never rewrite working Dart for appearance.

## 8. Performance non-negotiables (detail: `R-PERF`, `R-ALG`)

- Treat startup, first thumbnail, scrolling, tap-to-feedback, search, indexing, conversion, and inference as **separate performance paths** with separate metrics.
- Frame budget = 1000 ms / refresh rate (16.7 ms @60 Hz, 8.3 ms @120 Hz). No UI-isolate task that blocks input noticeably (heuristic: ≤~50 ms chunks, ≤~100 ms input response — RAIL; ratify against baselines).
- No work in `build()`; stable keys (media id); slivers/builders; `select`-narrowed rebuilds; no `BackdropFilter`/`saveLayer`/large shadows in scrolling content.
- Bound everything: caches by **bytes**, queues by length, concurrency by device tier, buffers by size. Decoded bitmap ≈ w×h×4 bytes (48 MP ≈ 192 MB): use sampled/region/tiled decode.
- No avoidable O(n²) over libraries; no repeated full scans/sorts; incremental over recompute.
- Measure on physical reference devices in `--profile` mode, cold and warm cache, median + p90/p99, with dataset described. Budgets live in `docs/perf/budgets.md`; do not invent universal numbers or benchmark results.

## 9. File and change discipline (detail: `R-FILE`, `R-GIT`)

- Search for existing implementations first (`rg`); reuse/extend when cohesion holds.
- New file only for a distinct, justified responsibility. No speculative interfaces/managers/factories, no `utils/` dumping ground, no placeholders, no duplicated logic/widgets/algorithms.
- No unrelated refactors in a focused task. Inspect indirect references (manifest, platform registrations, generated code, Pigeon/ffigen configs) before deleting "unused" code.
- Never hand-edit generated files. Never touch lockfiles/permissions/build pipeline without justification.
- Preserve unrelated user work. No reset/clean/force-push/history rewrite without explicit authorization.

## 10. AI/ML (detail: `R-AI`)

Prefer a deterministic algorithm or OS/ML Kit API over a model. Before adopting any model/library: verify upstream docs, **exact license (commercial use + redistribution)**, provenance/hash, size, quantization, peak RAM, latency, battery, min device, accuracy on a defined test set; compare alternatives; record in `docs/licenses/`. Inference runs on-device, off the UI isolate, through `jobs`. Weights are never committed to Git. Never download models/run untrusted scripts without a real requirement and authorization.

## 11. UI/UX (detail: `R-UI`)

Design docs are the authority except where §0 / `R-VIS` or an owner reference image overrides them. Centralized tokens only (no literal colors, sizes, text styles, durations in features). Reuse `design_system` components. Implement every state (loading/empty/error/success/disabled/selected/permission-denied). Follow specified placement/size/wording/motion exactly; never substitute a generic widget for a specified one. Accessibility (semantics, ≥48 dp targets, contrast, font scale 1.0 and 2.0), insets/cutouts/edge-to-edge, and all strings via l10n are mandatory.

## 12. Security and privacy (detail: `R-SEC`)

Least-privilege permissions requested at point of use; handle partial access and revocation. Scoped storage (MediaStore/SAF/FileProvider); avoid `MANAGE_EXTERNAL_STORAGE` unless PRD + store policy justify. Treat all input files and incoming intents as untrusted: validate type, size, dimensions, page/entry counts; defend against zip-slip and decompression bombs. No sensitive data in logs (paths, file names, EXIF/GPS, OCR text, face data). Temp files app-private and always cleaned. Verify every write/conversion outcome.

## 13. Workflow for every task (scale to risk; trivial edits get the same thinking, less text)

1. **Understand** — this file, the matching `rules.md` section, product + design specs, existing code, `git status`.
2. **Trace** — related code, data flow, state owner, native boundary, tests, reusable components.
3. **Evaluate** — simpler alternatives, complexity (time and space), memory, correctness, privacy, maintenance.
4. **Plan** — for substantial, risky, cross-cutting, or perf-sensitive work: affected files, new files (with justification), design, validation plan.
5. **Challenge** — unnecessary files, duplication, premature abstraction, new dependencies, perf regression, data loss, security, spec deviation.
6. **Implement** — smallest cohesive change.
7. **Verify** — format, analyze, relevant tests, build, perf measurement where applicable.
8. **Review** — diff, resource cleanup, error handling, UI fidelity, regressions.
9. **Report** — see §15.

CLAUDE.md never excuses skipping inspection or validation.

## 14. Commands (baseline; if one fails, fix this section — do not invent)

```
flutter pub get                                    # from repo root (workspace)
dart format --output=none --set-exit-if-changed .
flutter analyze                                    # or `dart analyze` for pure-Dart packages
flutter test                                       # per package: (cd packages/<pkg> && flutter test|dart test)
(cd app && flutter test integration_test)          # needs device/emulator
(cd app && flutter run --profile)                  # ALL perf work in profile mode, physical device; never debug
(cd app && flutter build apk --profile|--release)
cmake -S native/picspace_core -B build/native && ctest --test-dir build/native   # [PROPOSED] host native tests
```

## 15. Definition of done and report

Done = spec satisfied, boundaries respected, validation actually run, no unexplained regressions. **Never claim a test/build/benchmark passed unless it ran successfully**; say honestly what could not run and why. Do not suppress analyzer warnings, skip failing tests, or weaken validation to get green.

Report: what changed and why this approach; files created/modified (justify each new file/dependency); validation run + results; perf numbers (before/after, device, dataset) if relevant; spec assumptions/conflicts; unresolved issues; rule IDs deliberately deviated from.

## 16. Open decisions (ask or propose; never assume)

Platforms + minSdk; reference device matrix (`docs/perf/devices.md`); ADRs for state/navigation/DB/native build wiring; **PDF↔Word and Office→PDF engine** (`R-TOOL-4`, no proven lightweight on-device option); video/audio engine + FFmpeg licensing; source of the "Popular tools" list (editorial vs local usage); history "delete" semantics (record only vs file); where converted files are saved by default; Cleanup/Editing/Files PRDs; localization languages; analytics/crash reporting (default: none).

## 17. Maintaining this file

Keep under ~250 lines. When a rule is repeatedly missed, tighten it here; when detail grows, move it to `rules.md`. Add nested `CLAUDE.md` files inside packages only for package-specific facts (they load on demand when working there). Update the structure tree whenever packages actually change.
