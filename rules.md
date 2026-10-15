# PicSpace — rules.md

Normative engineering rules. `CLAUDE.md` is the entry point; this file is the detail. Read the section for the area you are touching **before** you start. Cite rule IDs in plans, reviews, and reports.

- **MUST / MUST NOT** = blocking. **SHOULD** = default; deviating needs a one-line justification in the report. **MAY** = allowed.
- **[verify]** = platform/library/policy fact to confirm against current official docs before relying on it.
- **[PROPOSED]** = does not exist yet.
- Each section starts with `Applies to:` globs so it can later be split into `.claude/rules/<name>.md` with `paths:` frontmatter without editing the content.

Sections: 1 INSPECT · 2 SPEC · 3 ARCH · 4 FILE · 5 PERF · 6 ALG · 7 NATIVE · 8 JOB/OUT · 9 TOOL · 10 AI · 11 UI · 12 SEC · 13 TEST · 14 DEP · 15 GIT · **16 REAL (no demos)** · **17 VIS (palette + layout quality)** · **18 CFG/DOC**

**Precedence of the newest owner rules:** R-REAL (§16) and R-VIS (§17) were added by the owner on 2026-10-12 and override any older rule, spec table, or default in this file or in `docs/product documents/` that conflicts with them (notably the colour table in doc 03 §2.3, the light theme in D-004, and the "Coming soon"/placeholder allowances in R-TOOL-2 and R-UI-4).

---

## 1. R-INSPECT — Pre-change inspection
Applies to: everything.

1. MUST run `git status` and check the branch before changing anything; identify uncommitted user work and leave it untouched.
2. MUST read: `CLAUDE.md`, the relevant section here, the relevant `docs/product` and `docs/design` files, the existing code in the area, the package `pubspec.yaml`, and existing tests.
3. MUST search for an existing implementation (`rg`) of any widget, token, helper, provider, or algorithm before writing a new one.
4. MUST trace entry point → state owner → data source → native boundary → tests, and name the owner of every piece of state you add.
5. MUST NOT assume the repo is empty, that the current architecture is right, or that an unfinished implementation reflects the intended product.
6. MUST NOT reorganize toward the target tree as a side effect. If the actual tree differs from `CLAUDE.md §4`, write/update `docs/architecture/structure.md` (`[EXISTS]` vs `[PROPOSED]`) and migrate in dedicated, reviewable steps (extract `core` → `design_system` → `jobs` → …, one at a time, always building).
7. MUST inspect indirect references (AndroidManifest, platform registrations, Pigeon/ffigen configs, generated code, proguard rules) before removing "unused" code.
8. If a document cannot be accessed, say so, work from the evidence you have, and list assumptions in the report.
9. Use read-only commands during audits. No installs, downloads, resets, or destructive commands without a real requirement and authorization.

---

## 2. R-SPEC — Source of truth and spec conflicts
Applies to: `docs/**`, any feature work.

1. Hierarchy: owner decisions > PRD/feature specs > UI/UX specs > ADRs > existing code (evaluated, not worshipped) > official docs/measurements > judgment with stated assumptions.
2. MUST NOT invent screens, controls, copy, flows, tool options, defaults, APIs, models, visual styles, or performance guarantees.
3. If a tool screen has no design spec: MUST stop and ask, or propose a design as a clearly labelled proposal. MAY build only from a layout pattern that `docs/design` already defines.
4. On conflict between documents (or between a document and code), MUST surface it with both citations and a recommendation; MUST NOT pick silently.
5. Product-level unknowns are listed in `CLAUDE.md §16`; extend that list rather than guessing.
6. Do not copy specs into `CLAUDE.md`/`rules.md`; reference paths.

---

## 3. R-ARCH — Architecture and boundaries
Applies to: `app/**`, `packages/**`, `pubspec.yaml`.

**R-ARCH-1 Dependency matrix** (a package MAY depend only on what is listed):

| Package | May depend on |
|---|---|
| core | Dart SDK only |
| design_system | core (Flutter) |
| platform | core |
| native_core | core |
| storage | core |
| media | core, platform, native_core, storage |
| jobs | core, platform, native_core, storage |
| ai | core, platform, native_core, storage, jobs, media |
| converter_engine | core, platform, native_core, storage, media, jobs, ai |
| features/* | core, design_system, storage, media, jobs; `features/converters` additionally converter_engine. **Never another feature.** |
| app | everything |

**R-ARCH-2** MUST NOT import another package's `lib/src/`. Each package exposes one public barrel; keep the surface small.

**R-ARCH-3** Only `design_system`, `media/providers`, `features/*`, `app` MAY import `flutter/widgets|material|cupertino`. `core`, `storage`, `jobs`, `ai`, `converter_engine` MUST stay widget-free so they run under `dart test` and inside worker isolates.

**R-ARCH-4 Cross-feature communication.** (a) Navigation: emit a `NavIntent` (defined in `core`), handled by `app/routing` (e.g., Photos "Convert this image" → `NavIntent.openTool(toolId, inputs)`; Photos never imports Converters). (b) Data: shared packages only. (c) Never reach into another feature's providers.

**R-ARCH-5 State.** Default Riverpod [ADR]. State is owned by the lowest layer that needs it. Screen-scoped state is auto-disposed. `ref.watch` only in `build`; side effects in notifiers. Use `select`/narrow providers to limit rebuilds. High-frequency values (progress, scrubbers, drag) use `ValueNotifier`/stream scoped to leaf widgets. No global mutable singletons; wiring happens in `app/bootstrap`.

**R-ARCH-6 Navigation.** Default go_router [ADR]. `app/routing` owns the route table; features expose route builders. The 5 upper sections preserve state per section (stateful shell) and are built **lazily** (Photos first; others on first visit). The Converters lower navigation (All Tools | Images | PDF | Documents | Media | Utilities) lives inside `features/converters`.

**R-ARCH-7 Errors and logging.** Expected failures are `Result`/sealed `Failure` values: `code`, `messageKey` (l10n), `retryable`, non-PII `cause`. Unexpected exceptions are caught at job, isolate, and zone boundaries, logged redacted, and surfaced as a generic retryable failure. Never `catch (_) {}`; never swallow an error silently. Every error shown to a user has a plain-language message and an action (retry, open settings, dismiss); never show raw exceptions, stack traces, paths, or internal details. Log with enough context to diagnose (error code, operation, ids, sizes, durations) and never log secrets, file names/paths, EXIF/GPS, or personal data. Distinguish recoverable errors (retry/offer alternative) from fatal ones (stop, explain, leave data untouched).

**R-ARCH-11 Data layer and business logic.** Business logic (validation, grouping, sorting, calculations, data processing) lives in services/repositories/notifiers, never inside widgets. All platform, storage, and (when ever approved) network access goes through a repository/service in a package; widgets receive data via providers or parameters. Do not invent platform APIs, endpoints, fields, or schemas: verify against the library's source/docs or existing code. Validate and parse external data defensively (missing/null/corrupt entries must not crash the UI). There is no backend: rules for routes/controllers/services apply only if one is introduced by ADR.

**R-ARCH-8 Package justification gate.** A new package requires at least one of: enforced dependency boundary; ≥2 consumers; different build/runtime/test profile (native, isolate, plugin); independent ownership. Otherwise it is a folder inside an existing package.

**R-ARCH-9 Inside a feature.** Start flat (`screens/ widgets/ state/`). Add `domain/` or `data/` only when logic is shared, complex, or needs isolated tests. No empty layers, no one-class-per-file ritual, no repository/service wrapper without a second implementation or a test seam that is actually used.

**R-ARCH-10 Enforcement.** Boundary rules SHOULD be machine-checked in CI [PROPOSED `tools/scripts/check_deps.dart`: pubspec deps vs R-ARCH-1, forbidden imports per R-ARCH-3, `src/` imports per R-ARCH-2]. One strict `analysis_options.yaml`; no blanket `ignore_for_file`.

---

## 4. R-FILE — File creation and codebase discipline
Applies to: everything.

1. MUST search first (R-INSPECT-3). Reuse or extend when cohesion is preserved.
2. MAY create a file only for a distinct, justified responsibility. Justify every new file/dir/dependency in the report.
3. MUST NOT create: speculative interfaces/managers/factories/services; trivial wrappers; placeholder files for hypothetical features; a generic `utils/`/`helpers/` dumping ground; duplicate logic, widgets, algorithms, or state.
4. MUST NOT split one cohesive concept across many files, nor pile unrelated concerns into one oversized file. Optimize for clear ownership, discoverability, and testability, not a file-count target.
5. MUST NOT refactor unrelated code in a focused task. MUST NOT hand-edit generated files (`*.g.dart`, Pigeon/ffigen output, l10n output) — change the generator input.
6. Naming: files `snake_case.dart`; one public concept per file name; tool ids are stable strings (`image.convert`, `pdf.merge`) and MUST NOT be renamed or reused after release.
7. Public API: documented with `///`; private by default (`_`/`src/`).
8. Reuse before create: search for an existing widget/token/helper/provider first; extract logic repeated in ≥2 places into one shared function/component (buttons, dialogs, sheets, rows, tiles). Do not abstract on the first use.
9. Cleanup: remove unused variables, imports, functions, classes, dependencies, dead and unreachable code, leftover debug prints, obsolete implementations, and temporary files in every change you touch, once indirect references are checked (R-INSPECT-7). Do not leave commented-out code. Comments only for non-obvious intent/constraints.
10. Prefer the simplest readable implementation; do not rewrite working modules or touch unrelated code. Follow the repo's existing naming and structure.

---

## 5. R-PERF — Performance engineering
Applies to: `app/**`, `packages/media/**`, `packages/jobs/**`, `packages/features/**`, `benchmarks/**`.

**Mindset.** The goal is no noticeable lag in ordinary supported interactions — a *measurable target verified on representative hardware*, not a literal-zero promise. Consider the whole path: input → storage → processing → state update → displayed frame.

**R-PERF-1 Startup.** `main()` awaits no I/O. Before first frame: binding init, theme, shell skeleton, last-known snapshot from DB. After first frame (low-priority lane): DB warm-up, MediaStore sync, native library load, orphan-temp sweep, model checks. MUST NOT eagerly construct providers/services for non-visible sections. Use the Android 12+ splash API [verify] rather than a custom blocking splash.

**R-PERF-2 Image loading (grid).**
- Request thumbnail edge = cell px × DPR, rounded to a bucket (e.g., 128/256/512 — tune by measurement). MUST NOT decode full-resolution images for grid cells.
- Cache key = (mediaId, generation/dateModified, sizeBucket, orientation). In-flight requests are deduplicated; requests are cancelled when the cell disposes or scrolls far off-screen; prefetch is velocity-aware.
- Memory cache is byte-bounded LRU (tune `ImageCache.maximumSizeBytes` explicitly); disk cache has a size cap + eviction; decoded size (w×h×4) is what counts, not file size.
- Downscale **at decode time** (sample size / DCT-domain scaling / platform target size), never decode-then-resize.
- Viewer path is progressive: thumbnail → screen-fit → full-res (tiled/region decode for huge images).
- The thumbnail transport (platform `loadThumbnail` vs own decode; bytes via channel vs native buffer via FFI) is decided by an ADR with a benchmark on the device matrix.

**R-PERF-3 Scrolling and rendering.**
- Slivers + builder delegates; stable `ValueKey(mediaId)` + `findChildIndexCallback`; fixed/precomputed extents where the layout allows.
- `const` widgets; no work, allocation storms, sorting, or formatting in `build()`; narrow rebuilds with `select`.
- `RepaintBoundary` only where profiling shows benefit.
- MUST NOT use `Opacity`, `ClipRRect`+`saveLayer`, `BackdropFilter`, large shadows, `Intrinsic*`, or `shrinkWrap` nested scrollables inside scrolling lists/grids without a profiled justification. Custom shaders only with profile evidence [verify Impeller behavior on target Flutter version].
- During fast scrolling show cheap placeholders; defer expensive work until scroll settles.
- Frame budget = 1000 ms / actual refresh rate (16.7 ms @60 Hz, 8.3 ms @120 Hz); both build and raster must fit. Meeting one frame target does not prove smoothness; check jank distribution on-device.

**R-PERF-4 Search and indexing.**
- Tool search (dozens–hundreds of items) is an in-memory match over precomputed normalized tokens. MUST NOT use DB/FTS for it.
- Media search/index: SQLite indexes (+ FTS where needed [verify FTS5 availability in chosen SQLite build]); prepared statements; batched writes in transactions (batch size by measurement); DB work in a background isolate.
- Index sync is incremental (MediaStore generation/date-modified cursors + change observer [verify]); full rescans only on explicit repair or schema change.
- Debounce typed queries and cancel superseded ones. Persist derived results (hashes, thumbnails keyed by generation); do not recompute unchanged data.

**R-PERF-5 Background work.**
- Thumbnailing, indexing, hashing, OCR, AI, and conversion run as Jobs (R-JOB), never on the UI isolate.
- Concurrency is bounded by device tier (low-RAM flag, memory class, cores [verify APIs]); priority lanes: interactive > user-queued conversion > background index > opportunistic AI.
- Pause/throttle on low memory, thermal pressure, or battery saver where the platform signals it [verify].
- MUST NOT `Future.wait` over unbounded collections. UI-isolate tasks stay in small chunks (heuristic ≤~50 ms); input response ≤~100 ms (RAIL heuristics — ratify against baselines).

**R-PERF-6 Memory.**
- Decoded bitmap ≈ w×h×4 bytes (48 MP ≈ 192 MB; 108 MP ≈ 432 MB). MUST NOT hold more than the job's memory budget; use sampled, region, or tiled processing for large inputs.
- On the low-RAM tier, run at most one heavy decode/model/transcode at a time.
- Caches, queues, and buffers have explicit bounds. Stream files with bounded buffers; never read whole PDFs/videos/archives into memory.
- Release caches and idle models on trim-memory/low-memory signals [verify].

**R-PERF-7 Long-running use.** Dispose controllers, subscriptions, isolates, native handles. SHOULD run soak checks (scroll thousands of items; run 100 conversions; background/foreground cycles) and confirm memory plateaus (DevTools memory, `leak_tracker` [verify]). Detect stale tasks and repeated initialization.

**R-PERF-8 Device conditions.** Consider cold vs warm cache, low-RAM devices, large libraries, huge images, slow storage, SD/removable volumes, permission loss, storage changes, constrained CPU/thermal state.

**R-PERF-9 Measurement protocol.**
1. Physical devices from `docs/perf/devices.md` [PROPOSED; owner supplies the matrix; suggested tiers: low / mid / high]. Profile mode only (`flutter run --profile`); never debug mode.
2. Baseline before changing; compare after. Report median and p90/p99 over multiple runs, cold and warm cache, with dataset description (library size, resolution/format mix) and device config.
3. Metrics, where applicable: cold/warm start; time to first meaningful screen; time to first visible thumbnail; thumbnail latency; scroll jank/dropped frames; tap-to-feedback; search latency; index throughput; DB query latency; peak/sustained memory; cache hit rate + cache memory; background CPU; conversion throughput + peak memory; AI latency + memory; battery and storage impact.
4. Tools: Flutter DevTools, `integration_test` timeline summaries, Perfetto/Android profiler/Macrobenchmark [verify], repo benchmarks.
5. Targets are derived from baselines + product requirements and recorded in `docs/perf/budgets.md` (metric, target, device tier, dataset, method, owner). MUST NOT invent universal thresholds or fabricate results. A perf-sensitive PR reports before/after numbers or states that it could not measure.

---

## 6. R-ALG — Algorithm and technology selection
Applies to: any non-trivial logic, library, or runtime choice.

**R-ALG-1 Before choosing, answer:** exact problem; input sizes, frequency, growth; correctness/privacy constraints; time and space complexity incl. peak memory; real costs (allocation, disk, decode, serialization, transfer); can existing code solve it; credible alternatives; license/compat/maintenance cost; how it is measured and tested; does the complexity buy a material benefit; is a simpler equivalent available.

**R-ALG-2** Weigh asymptotics against constants (locality, allocation, I/O, concurrency). Avoid avoidable O(n²) on large collections. MUST NOT introduce ML, a database, a worker framework, or a cache where a deterministic algorithm or existing API suffices.

**R-ALG-3 PicSpace patterns** (apply when the relevant feature is specified):
- Exact duplicates: group by file size, then streamed content hash on collisions only; persist hashes keyed by generation.
- Near-duplicates/similar: perceptual hash + multi-index/BK-tree or LSH bucketing; embeddings + ANN only if the PRD needs semantic similarity. Never all-pairs over the library.
- Date grouping/sorting: rely on indexed `ORDER BY` in the DB; do not re-sort in Dart.
- Batch rename: O(n) with a hash set for collision detection; operate via MediaStore/SAF, not raw paths.
- PDF page operations: manipulate the page/object tree; do not rasterize.
- PDF compression: downsample/recompress images, dedupe/compact objects. Rasterizing pages is a disclosed last resort (loses text).
- Target-file-size image compression: bounded search over quality (≈6–8 iterations max), not brute force; stop on tolerance.
- Resampling: higher-quality filter for final export, cheaper for preview.
- Image→PDF: embed JPEG streams without re-encoding where the PDF library supports it [verify]; avoid quality loss and size bloat.
- Thumbnails/viewers: prefer decode-time downscaling over full decode + resize.

---

## 7. R-NATIVE — Kotlin, C++/FFI, Python policy
Applies to: `packages/platform/**`, `packages/native_core/**`, `native/**`, `tools/**`, `app/android/**`.

**R-NATIVE-1 Escalation ladder (evidence required at each step).** (1) Dart in a worker isolate. (2) Kotlin/Android platform API. (3) C++ in `native/picspace_core` via FFI. Step up only when (a) the capability does not exist at the lower level, or (b) a profile on the device matrix shows a material gain that survives FFI/copy/marshalling cost, and (c) the maintenance cost is accepted in an ADR. Never rewrite working Dart in C++ for its own sake.

**R-NATIVE-2 Kotlin.** Typed Pigeon APIs, no stringly-typed channels. `Dispatchers.IO/Default`; never block the main thread. Every long call supports cancellation. `app/android` stays thin; platform code lives in `packages/platform`. Workers on background isolates need `BackgroundIsolateBinaryMessenger` initialization [verify]. Long jobs use WorkManager/foreground service with the correct service type for the target SDK [verify current Android policy, including media-processing service type on newer SDKs].

**R-NATIVE-3 C ABI (FFI boundary).**
- `extern "C"` only; opaque handles + POD structs; no C++ types, exceptions, or RTTI across the boundary (catch at the boundary; return error codes + a retrievable message).
- The allocator frees: every `picspace_*_create` has a `picspace_*_free`; Dart wrappers add `NativeFinalizer` as a safety net but also expose explicit `dispose`.
- Pass file paths/fds/URIs, not byte arrays. Large buffers are native-owned with explicit lifetime. Avoid copying across isolates (`TransferableTypedData`/`Isolate.exit` only when transfer is truly needed).
- Cancellation via a shared atomic token checked inside loops; progress via polled counter or `NativeCallable.listener` [verify].
- Blocking FFI calls run on a worker isolate, never the UI isolate.
- Bindings generated by ffigen into `native_core/lib/src/generated/`; never hand-edited.

**R-NATIVE-4 Build.** One shared library (`libpicspace_core.so`), opened lazily on first use. ABIs: arm64-v8a primary; add others only per requirement/min-device policy. Native libraries MUST be 16 KB page-size compatible [verify current Play requirement and NDK version]. Pin third-party sources/versions in `native/third_party` with a LICENSE manifest. Host-run GoogleTest + ASan/UBSan builds in CI [PROPOSED].

**R-NATIVE-5 Hardening (untrusted input).** Every parser/decoder entry point enforces dimension, size, page/entry-count, and time limits; bounds checks; fuzz target per parser [PROPOSED]; track CVEs of vendored libraries. For risky decoders, consider isolating work in a separate Android process for crash containment [verify trade-offs].

**R-NATIVE-6 Python.** Only in `tools/` (model conversion/quantization, deterministic fixture generation, benchmark/trace analysis). Pinned requirements. MUST NOT ship Python in the app. Outputs (models, big fixtures) are not committed unless documented.

**R-NATIVE-7** Rust/Java/Swift or a second native language needs an ADR. Keep one native toolchain.

---

## 8. R-JOB / R-OUT — Job engine and output pipeline
Applies to: `packages/jobs/**`, `packages/converter_engine/**`, `packages/features/converters/**`.

**R-JOB-1 Job model.** Immutable spec (toolId, `List<FileRef>` inputs, typed serializable options, output policy). States: `queued → running → [awaitingCommit] → succeeded | failed | cancelled | interrupted`. Persisted for recovery and history.

**R-JOB-2 Scheduling.** Priority lanes + resource tokens (memory, CPU, foreground-service slot). Concurrency bounded by device tier. Batches report **per-item** results; one failing item MUST NOT silently kill the batch or hide partial success.

**R-JOB-3 Progress.** Determinate (0–1 + stage label key) when knowable, else indeterminate. Throttle UI updates (target ~10–30 Hz; tune). Progress never blocks work.

**R-JOB-4 Cancellation.** Cooperative `CancelToken` checked between chunks and propagated to Kotlin and native code. Cancel MUST promptly stop resource use and delete temp artifacts. Obsolete tasks MUST NOT keep consuming resources.

**R-JOB-5 Failure and retry.** Failures carry `retryable` + a user-presentable message key. The UI offers clear error text and Retry (spec'd behavior). Automatic retry only for transient I/O, bounded (≤2). Unsupported formats fail fast with a specific message before work starts.

**R-JOB-6 Recovery.** Survive backgrounding via WorkManager/foreground service [verify]. After process death, mark orphaned `running` jobs `interrupted` and offer retry; MUST NOT silently resume destructive operations. Sweep orphaned temp dirs at idle.

**R-OUT-1 Commit protocol.**
1. Write to app-private temp `cache/jobs/<jobId>/` — never directly to the destination.
2. Validate (R-OUT-2). Failure ⇒ job fails, temp deleted.
3. Preview from temp where the tool supports preview ("preview before saving").
4. Commit to destination: MediaStore insert with pending flag / SAF create, copy, clear pending [verify]; verify size/hash after write.
5. Record history; delete temp (always, including on failure/cancel).

**R-OUT-2 Validators** (success is reported only after the validator passes):
- Image: decodes; expected dimensions/format signature; orientation preserved.
- PDF: opens; page count as expected; non-empty; first page renderable.
- Audio/video: probe succeeds; expected streams/codec; duration within tolerance.
- ZIP: central directory readable; CRC test passes. OOXML (DOCX/XLSX/PPTX): valid package structure.
- QR: generated code round-trips through the decoder.
- GIF: frame count/dimensions/size cap as specified.

**R-OUT-3 Originals.** Originals are immutable. Output names are collision-safe (`name (1).ext`). MUST NOT overwrite or delete an existing file without explicit per-action user confirmation (not a silent persisted default unless the PRD says so). Modifying/deleting media owned by other apps uses the system consent flow on Android 11+ [verify `createWriteRequest`/`createDeleteRequest`].

**R-OUT-4 History.** Store metadata only (job, tool, input refs, output URI, size, timestamps, status) — never file contents. Actions: **open** (system intent via MediaStore/FileProvider URI), **share** (read-grant URIs; never raw paths), **rename** (file + record, collision-safe), **delete** (confirmed; semantics per PRD — see CLAUDE.md §16). On open/share, verify the file still exists; if moved/missing, offer to remove the entry.

---

## 9. R-TOOL — Converter tools and registry
Applies to: `packages/converter_engine/**`, `packages/features/converters/**`.

**R-TOOL-1 Registry.** Each tool is a `const ToolDescriptor`: stable `id`, category, l10n keys, icon token, accepted input types, output kinds, options schema (format/quality/resolution/…), capabilities `{batch, preview, cancellable, needsModel}`, `phase`, lazy runner factory, validator. The hub catalog, search, category pages, recents, favorites/pinned, and popular all derive from the registry. No hard-coded tool lists in UI. Standard options render from the schema; bespoke screens only where interaction demands it (page reorder, sign/annotate, trimmer, crop), per `docs/design`.

**R-TOOL-2 Phase gating.** Tools not yet implemented MUST NOT appear in the UI (no fake "coming soon" unless the design says so).

**R-TOOL-3 Definition of done for adding/changing a tool.**
1. Descriptor + options schema + l10n strings.
2. Runner implementing cancel, progress, bounded memory.
3. Output validator.
4. Input guards: unsupported/corrupt/encrypted/huge inputs fail with specific messages.
5. Tests: happy path, corrupted input, cancel mid-run, low-memory/huge input, missing/revoked file, batch partial failure, output validation failure.
6. UI per spec with all states; preview/save flow if supported.
7. History integration; queue integration.
8. License check for every new library/model (R-DEP, R-AI).
9. Perf measurement for throughput/peak memory on the device matrix.
10. Docs: row updated in `docs/product/converters.md` status.

**R-TOOL-4 Unresolved hard problem — PDF↔Word and Word/Excel/PowerPoint→PDF.** No proven lightweight, full-fidelity, on-device engine is established. Phase 1 includes PDF→Word and Word→PDF, so a spike + ADR is required **before any promise of fidelity**. Options to evaluate: (a) restricted-fidelity native converter with explicit limits shown to the user; (b) a bundled heavy engine (size, license, memory); (c) opt-in cloud conversion (explicit consent, privacy model, retention/deletion policy — contradicts local-by-default, so never chosen silently). Record measured fidelity on a defined document corpus.

**R-TOOL-5 Default routes** (starting hypotheses, not decisions — verify and ADR before building):

| Tools | Default route | Evaluate / hazards |
|---|---|---|
| Image convert/resize/compress/batch | Kotlin platform decoders/encoders (sampled decode, ExifInterface) in worker; C++ (libjpeg-turbo/libwebp/libheif) when profiling or missing control justifies | Pure-Dart `image` package only for small images/tests, never full-res hot paths. HEIC decode/encode support by API level [verify]; EXIF orientation, ICC/color, HDR/gain-map handling decided explicitly; 48 MP+ memory |
| Image→PDF / Images→PDF | PDF writer with JPEG passthrough | Page size/orientation/margins per spec; stream pages in large batches |
| PDF→Images | `PdfRenderer` or PDFium [verify] | Encrypted PDFs (prompt or clear error); render scale vs memory; page streaming |
| Merge / Split / Extract / Rotate / Reorder / Compress | Object-level PDF manipulation (qpdf or PDFium, C++) [verify licenses] | **MuPDF is AGPL — forbidden without a commercial license**; commercial SDKs need an ADR; never rasterize unless disclosed |
| Sign / Annotate | Renderer + annotation writing | Annotation objects vs flattening; signature storage is sensitive data; per design spec |
| OCR / Document Scanner | ML Kit text recognition / document scanner, or Tesseract/PaddleOCR via LiteRT/ONNX/native | Language-pack size; searchable-PDF needs invisible text layer support in the writer; Play-services dependency affects "local by default" — disclose |
| PDF↔Word, Office→PDF | **UNRESOLVED (R-TOOL-4)** | — |
| Text / Markdown → PDF | Layout in Dart or native | Fonts + licensing, CJK/RTL shaping, page breaks |
| Excel/CSV | CSV streaming in Dart; XLSX via OPC/zip + streaming XML | Formula/style fidelity; very large sheets |
| ZIP extract/create | `java.util.zip` via Kotlin, or libzip/miniz via C++, streaming | Zip-slip, bombs, name encodings, encrypted archives, SAF output |
| QR | Generate: Dart/native; scan: ML Kit or ZXing-based [verify] | Never auto-open decoded content; camera permission at point of use |
| Video / audio / GIF | Media3 Transformer + MediaCodec [verify per operation]; GIF = frame extraction + native encoder with palette quantization | Foreground service; **MP3 encoding lacks a platform encoder [verify] and LAME is LGPL → default AAC/Opus unless an ADR decides**; FFmpegKit was retired upstream [verify] — any FFmpeg build must be LGPL-only, dynamically linked, size/licence-reviewed; cap GIF fps/resolution/colors |
| Background remover / Upscaler | On-device segmentation / super-resolution via LiteRT/ONNX/ncnn | License (some popular weights are non-commercial [verify per model]); tiling for memory; alpha-preserving output |
| Batch renamer / Metadata viewer | Dart + MediaStore/SAF + ExifInterface | Rename via platform APIs, not raw paths; collision map |

---

## 10. R-AI — AI/ML models and libraries
Applies to: `packages/ai/**`, `tools/ml/**`, `docs/licenses/**`.

1. MUST prefer a deterministic algorithm or an OS/ML Kit API over a custom model; MUST NOT add ML where QR decoding, EXIF, hashing, or geometry suffices.
2. Before integrating any model/library: search the repo + dependency graph; read upstream official docs and maintained repos; verify supported OS/ABIs/formats/runtimes; evaluate accuracy on a defined test set, latency, model size, peak RAM, throughput, battery, cold-start; check quantization + acceleration (GPU/NNAPI/Vulkan) [verify]; compare ≥2 alternatives; define acceptance tests **before** claiming success.
3. MUST verify provenance (source URL, version, hash) and the **exact license**, including commercial-use and redistribution rights, and record it in `docs/licenses/models.md` [PROPOSED]. MUST NOT assume a public download is commercially usable.
4. Inference runs on-device, off the UI isolate, as a Job. On the low-RAM tier keep one heavy model resident; unload on trim-memory. Tile large images; bound memory.
5. Weights, datasets, build outputs, and caches stay out of Git unless a documented reason exists. Not bundled in the APK unless small/required; otherwise delivered via `ModelManager` (hash-verified, pinned HTTPS source, user-disclosed, evictable, storage-budgeted) [ADR]. Never download arbitrary models or run untrusted scripts.
6. Runtime choice (LiteRT, ONNX Runtime Mobile, ncnn, ML Kit) is per model, by benchmark [verify current versions/naming].
7. No user media, OCR text, or face-related data leaves the device unless the PRD authorizes it and a privacy model is defined. Do not claim accuracy, acceleration, or license compatibility without evidence.

---

## 11. R-UI — UI/UX and design system
Applies to: `packages/design_system/**`, `packages/features/**`, `app/lib/shell/**`.

1. `docs/design` and `docs/product documents/` are the authority for look and behavior, **except where R-VIS (§17) or an owner reference image says otherwise** (R-VIS wins). Before touching a screen: read its spec, the current implementation, the tokens, existing components, and any owner reference image.
2. Tokens only: color, typography, spacing, radius, elevation, motion, icon size. No literal values in features. New token = change in `design_system`, not a local constant.
3. Reuse `design_system` components; create one only when ≥2 uses or the spec demands a shared component. Specified placement, size, wording, spacing, and motion are followed exactly; no generic-widget substitution; no silent "improvements".
4. Every state implemented: loading, empty, error (with retry), success, disabled, selected, permission-denied/limited-access.
5. Overlays (menus, bottom sheets, dialogs, popovers, toolbars, contextual actions): spec'd size, anchor/placement, dismissal, and animation.
6. Layout: phones, small screens, landscape, foldables/tablets where supported; safe areas, cutouts, gesture nav, edge-to-edge [verify target-SDK enforcement]; text scale tested at 1.0 and 2.0.
7. Accessibility: semantic labels, logical TalkBack order, targets ≥48 dp, text contrast ≥ WCAG AA (4.5:1), honor reduced-motion settings.
8. All user-visible strings via l10n (ARB); no hard-coded copy; directional-safe layouts (RTL ready).
9. Animation is intentional and cheap: animate transforms/opacity on leaf widgets; scope rebuilds with `AnimatedBuilder`; no layout animation inside long lists; profile any shader/blur.
10. Converters flows follow the design docs for: upper nav → lower category nav → tool → options → run → progress → preview → save → history. Do not invent intermediate steps.
11. Material UX conflicts or spec gaps are escalated via R-SPEC, not resolved locally.
12. Golden tests for `design_system` components; screenshot/widget tests for key screens with fixed fonts.

---

## 12. R-SEC — Security, privacy, and data integrity
Applies to: everything; extra care in `packages/platform/**`, `native/**`, `packages/jobs/**`.

1. All user media, documents, metadata, signatures, scans, and OCR output are sensitive.
2. Permissions: least privilege, requested at point of use with rationale; handle partial access and revocation mid-session [verify Android 14+ selected-photos behavior]. Prefer photo picker/SAF for single-use inputs. Avoid `MANAGE_EXTERNAL_STORAGE` unless PRD + store policy justify.
3. Storage: scoped storage only (MediaStore/SAF/FileProvider). Never hand raw paths to other apps; grant URI read permissions. Canonicalize paths; reject traversal.
4. Treat input files and incoming intents/share-targets as untrusted: validate MIME by content, size, dimensions, page/entry counts, nesting; handle malformed and oversized files without crashing or exhausting memory.
5. Archives: reject `..`, absolute paths, and symlink escapes (zip-slip); enforce caps on total uncompressed size, compression ratio, and entry count; stream.
6. Logs: no file names, paths, EXIF/GPS, OCR text, face data, or signatures. Log ids, sizes, MIME types, durations, error codes.
7. Network: none by default. Any call (model download, cloud conversion, updates) needs an ADR, user disclosure, and a documented data policy. No analytics/crash SDK without approval. Do not make privacy claims the system cannot back.
8. Secrets never in the repo or app assets. Consider `allowBackup`/data-extraction rules for history/thumbnail data [verify]. Encryption at rest only if the PRD requires it (ADR).
9. Temp files: app-private, always cleaned (success, failure, cancel, process death sweep). Partial writes are never exposed as final outputs. Verify every write/conversion outcome.
10. Metadata in outputs (EXIF/GPS/ICC/orientation): behavior is a product decision (PRD/ADR). Until decided, preserve orientation and color-critical data and document; never silently add or strip personal metadata.
11. Dependency + license review per R-DEP; vulnerability scanning in CI [PROPOSED].
12. MUST NOT disable security protections to simplify implementation.

---

## 13. R-TEST — Testing and quality control
Applies to: `**/test/**`, `app/integration_test/**`, `benchmarks/**`, `native/**/tests/**`.

1. Validation is proportional to risk. Always: `dart format`, `flutter analyze`. Then the relevant tests/builds below.
2. Where tests live: pure logic → package `test/` (`dart test`); widgets → feature/`design_system` `test/`; goldens → `design_system`; cross-section flows → `app/integration_test/`; native → `native/picspace_core/tests/` (host) + on-device smoke; perf → `benchmarks/`.
3. Meaningful behavior and failure modes, not trivial lines. Do not add a library/framework/abstraction just for testability.
3a. **Android-only code needs a first run on a phone before it is called built.** The JVM and Flutter tests have no Android SQLite, services, WorkManager or codecs: on 2026-10-14 an `execSQL("PRAGMA …")` that passed every test crashed the app and the analysis process in a loop on the first launch (ADR 0007). A background thread of the plugin never ends the app (`safeThreads`), and a call that answers Dart answers with an error when it fails (`VisionHandler.background`). A speed claim comes from `ThumbTelemetry` on a phone in a profile build, not from a design argument (ADR 0009).
3b. **Tests that run on the phone** live in `packages/platform/android/src/androidTest` and run with `tools/bench/device-tests.ps1` (a separate test package, no screen, never PicSpace's own data). On 2026-10-15 they showed in minutes what the JVM tests could not: the decoder had failed on every photo since the analysis was written (`BitmapFactory.decodeStream` returns null when only the size is asked for), and two models closed under a running one aborted the process. A change to the decoder, the face/label/Smart-search pipelines, the inbox or the analysis engine is not done until `DeviceTests` passes. To see what the *app* stored, a debuggable build allows `adb shell run-as com.picspace.picspace` to copy `app_flutter/*.sqlite` and `databases/analysis_inbox.db` (read only); in non-release builds the failed import logs the exception to logcat (`picspace.ai`).

| Change type | Minimum validation |
|---|---|
| Pure logic / algorithm | unit tests incl. boundary + large input |
| Widget / screen | widget test (all states) + golden if shared component |
| Converter tool | R-TOOL-3 test list + validator test |
| Job / scheduler / cancel | deterministic tests with fake clock/tokens; cancel and recovery cases |
| Native/FFI | host native tests, sanitizer run, Dart wrapper test, on-device smoke |
| Perf-sensitive | before/after on device in profile mode (R-PERF-9) |
| Storage/migration | migration test from previous schema with data |
| Permissions/platform | manual or instrumented check with grant/deny/revoke |

4. Boundary cases to cover where applicable: huge library; corrupt/truncated media; missing/moved/revoked files; duplicates; low-memory; cancelled work; concurrent requests; permission denial; interrupted conversion; inaccessible/removed storage; encrypted PDFs; zero-length inputs.
5. Fixtures: tiny committed files in `testdata/` with a manifest; large/corrupt ones generated by `tools/fixtures` (deterministic, gitignored).
6. MUST NOT claim a test/build passed unless it ran successfully. MUST NOT hide analyzer errors, indiscriminately silence warnings, disable failing tests, or weaken checks to get green. Fix flaky tests; do not skip them. If a check cannot run, say why.
7. Add/update tests for every new behavior, validation rule, error path, edge case, and fixed bug. Verify refactors preserve behavior. Check the integration points (UI ↔ state ↔ repository ↔ platform). Fix problems your change introduced before declaring done. Fakes/mocks exist only under `test/`; shipped code never uses them (R-REAL-1).
8. Real-device verification (R-REAL-2) is required for anything that touches platform data, permissions, gestures, scrolling, or layout.

---

## 14. R-DEP — Dependencies and architectural decisions
Applies to: `**/pubspec.yaml`, `native/third_party/**`, `docs/adr/**`, `docs/licenses/**`.

1. Before adding or changing a dependency, check existing capability and evaluate: demonstrable benefit; compatibility/platform support; startup + runtime impact; binary size and memory; license + commercial use; security and maintenance status; build complexity; duplication; migration, testing, and rollback cost.
2. Keep sound existing conventions/libraries; do not blindly preserve legacy choices, and do not swap a working one without a measured reason.
3. Prefer first-party/Flutter-team/Google-maintained and actively maintained packages with permissive licenses. Pin versions. A package with no release for a long period needs justification.
4. License policy: MIT/BSD/Apache-2.0/ISC OK. GPL/AGPL forbidden. LGPL/MPL/other copyleft or commercial SDKs only via ADR (dynamic linking, relinking obligations, attribution). Maintain `docs/licenses/` (deps + native + models) with name, version, license, source, where used.
5. Dependencies belong to the lowest package that uses them; `app` does not accumulate feature dependencies.
6. **ADR required for:** state management, navigation, database, platform-channel/FFI wiring, PDF engine, video/audio engine, AI runtime, any native library, any network use, any new package, any rule deviation. ADR = title, status, context, options with measured data, decision, consequences, rollback. Location `docs/adr/NNNN-title.md`. No ADRs for trivial choices.

---

## 15. R-GIT — Git and change management
Applies to: everything.

1. Inspect Git state before implementing; preserve unrelated user changes.
2. MUST NOT reset, clean, overwrite, force-push, or rewrite history without explicit authorization.
3. Small, reviewable, cohesive commits/changes. No broad refactors during focused work.
4. MUST NOT hand-edit generated files; MUST NOT change lockfiles, dependencies, permissions, or build pipelines without justification.
5. Never perform destructive cleanup because a tool or suggestion recommends it. For high-impact or irreversible actions, assess consequences and ask first.
6. Keep build outputs, model weights, datasets, generated binaries, and caches out of Git unless a documented reason exists.
7. Final report follows `CLAUDE.md §15`; cite rule IDs for any deliberate deviation.

---

## 16. R-REAL — Real implementation only (no demos)
Applies to: everything. Owner rule, 2026-10-12. Highest priority after owner decisions.

1. **No demos, mocks, fake data, stub screens, or placeholder content in shipped code.** Every list shows real data from the device; every button, menu item, tab, and gesture performs its real action. Fakes/fixtures exist only under `test/`.
2. **Not built = not shown.** A control, tab, or section whose behavior is not implemented MUST NOT be rendered, with one exception: sections the owner explicitly asked to show "Coming soon" (currently Cleanup, Editing, Files, Converters), which show an honest "Coming soon" page and nothing that pretends to work.
3. **End-to-end or not at all.** A feature is UI + state + repository/platform + permissions + loading/empty/error states + tests. Never ship only the visible UI. Do not claim completion because code was written.
4. **Verify on the real device.** For anything touching platform data, permissions, scrolling, gestures, or layout: build, install and run on the connected device (`flutter devices`), exercise the feature with the device's real data, and check a screenshot (`adb exec-out screencap`) before reporting done. If no device is available, say it is **not verified** and why. The device is the owner's personal phone: before any screenshot or input command, confirm PicSpace has focus (`adb shell dumpsys window | grep mCurrentFocus`); never capture or read another app's screen, keep screenshots in the scratchpad (never in the repo) and delete them when done, and do not launch or drive the app while the owner is using the phone unless they said to.
5. **Layout is a correctness issue.** No overlapping, clipped, or overflowing text/widgets; no unexplained gaps; no RenderFlex overflow in logs. Check at 320/360/411 dp widths and text scale 1.0/1.3/2.0 (widget tests) and on the device.
6. **Owner reference images are binding visual specs.** Match their structure, proportions, spacing rhythm, and component shapes. State any deviation. Annotations (arrows, circles) mark problems to avoid or fix; if their meaning is unclear, say how you interpreted them.
7. **Before implementing**: list requirements, dependencies, existing code paths, constraints, and acceptance criteria; break the work into small verifiable steps; inspect the repo first (R-INSPECT). Resolve ambiguity from code/docs; ask only when a consequential requirement cannot be determined safely.
8. Report honestly: what works (verified how), what does not, what was not run. Never describe unbuilt or unverified behavior as ready.

---

## 17. R-VIS — Visual standard: three colours, clean layout
Applies to: `packages/design_system/**`, `packages/features/**`, `app/**`. Owner rule, 2026-10-12. Supersedes doc 03 §2.3 (colour table), D-004 (light theme), and doc 02 §1.1 (bottom bar).

1. **Exactly three colours app-wide:** (a) **black `#000000`** — all backgrounds; (b) **white `#FFFFFF`** — all text and icons; (c) **dark grey `#1A1A1A`** (near-black, never pure black) — all buttons, cards, boxes, chips, sheets, menus, and bar fills. Secondary text, dividers, and pressed/selected states use these same colours at reduced opacity (e.g., white 60% for secondary text, white 12% for selected/pressed, white 10% for 1 dp borders). No accent hue, no coloured icons, badges, gradients, or tinted states. Distinguish destructive/error states with wording and icon, not colour. Only user media may add colour.
2. **Dark only.** One theme; no light theme. System bars: transparent, light icons, edge-to-edge.
3. Colours come only from `design_system` tokens (`R-UI-2`); literal `Color(...)` outside `design_system` is forbidden.
4. **Floating navigation bars** (ADR 0002 + owner reference image): transparent blurred (glass) dark-grey pills that **hug their content and are centered**, never stretched edge to edge. Icon-only items, 48 dp targets; the selected item sits on a circular white-12% highlight; every item has a tooltip and Semantics label. Upper bar = 5 sections; lower bar = sub-tabs of the active section. Search lives in its own glass circle beside the upper pill. Content scrolls under both bars and always receives padding so nothing is hidden behind them.
5. **Spacing rhythm (multiples of 4 dp):** screen margin 16; heading → its content 12; section → section 24; grid gutter 2 (photos) / 12 (cards). No gap larger than the rhythm without a reason; headings sit directly above their content. Large page title (`screenTitle`+) left-aligned under the status bar; section headings use `sectionHeading` with trailing count/action on the same baseline.
6. Text never overlaps: single-line labels ellipsize; multi-line text wraps with min-height containers; middle-ellipsis for file names. Counts/badges sit in their own chip, never over text.
7. Every state is designed: loading (static skeleton in dark grey), empty, error with action, permission denied/limited. No spinner-only screens longer than 150 ms.
8. Animation is subtle: 100–300 ms, standard curves, respects reduced motion.

---

## 18. R-CFG / R-DOC — Configuration and documentation
Applies to: `app/**`, `docs/**`, `README.md`.

1. Environment-dependent values (flavors, base URLs, feature flags) live in `app/lib/flavors` or build-time `--dart-define`s, never in feature code. The app's only network use is the Smart search model download the user starts (ADR 0006); there are no secrets. If any more are introduced (ADR first), never commit them, validate required config at startup, and fail clearly when missing. Dev settings must not be able to reach production resources.
2. Keep `README.md` (repo root) accurate: prerequisites, setup, run (`flutter run` on a device), test, analyze, structure, and current feature status. Update it whenever setup, architecture, or behavior changes. Docs MUST NOT claim a feature works unless it was implemented and verified (R-REAL-8).
3. Document non-obvious decisions in ADRs (R-DEP-6) and keep `docs/architecture/structure.md` current.

## 19. R-PHX — Photos UX standards (owner decisions, 2026-10-12)
Applies to: `packages/features/photos/**`, `packages/viewer/**`, `packages/design_system/**`.

1. **Typography:** headings use the `AppSerif` family (`AppFonts.heading`) only. Today the file behind it is Arapey Regular; the owner asked for **Scotch Deck Light** (2026-10-15), a commercial font that is not in the repository, so the licensed file replaces the asset under the same family name in `packages/design_system/pubspec.yaml` and nothing else changes. Italic styles MUST NOT exist (`heading3` and every other style are upright). Screen titles 42 sp, section headings 28 sp, card headings 24 sp, day headers 20 sp.
2. **Icons:** only `AppIcons` (generated from the Stratis pack by `tools/scripts/gen_icons.py`); stroke 1.5 on the 24 grid, selected 2.1. Never a raw path or another family. A new icon is picked by looking at a rendered sheet, not by name.
3. **Chrome sizes** come from tokens: bar 56, circle 48, compact circle 40 (hit area 48), capsule 32, bar icon 22. No feature sets its own.
4. **Search:** one `MorphingBar`. The section pill grows into the field in 420 ms on the same surface; the circle keeps size and position and its icon morphs search to X; reduced motion uses a 100 ms fade. Each tab registers a `SearchScope` (or none; None means the search circle is not drawn). Never create a second bar.
5. **Analysis (faces, scenes, places, highlights, Smart search embeddings):** never shown as progress or "scanning" text. Results stream into the UI as they appear. Errors are typed (`decode`, `model`, `vault`, `oom`, `inference`, `crashed`, `step_disabled`), only `decode` marks an item done, and all are readable on the Diagnostics page. A background failure MUST NOT mark work as done. **Models run only in the `:analysis` process** (ADR 0007): a native crash there must never close the app, so no model session may be opened in the app process. The analysis may also run while the phone is charging with the app closed (WorkManager, charging and battery-not-low only, a switch in Explore settings, no network, nothing shown).
6. **Timeline:** the listing is counted first and laid out in full. On Android the library comes from the media index (ADR 0009) in one call, so every row is filled from the first frame; skeleton rows exist only on the fallback path (no index) and there the part in view loads first. Photos are ordered by the date taken. Layout changes above the viewport keep the on-screen photo in place; a scrubber follows the finger by absolute position.
7. **Video:** any scrubber shows the target time while it is dragged (bubble plus label), seeks live (throttled), and restores the play state on release.
8. **Titles:** a page's name is visible in its top bar from the first frame; it never waits for a scroll.
9. **Smart search (ADR 0006):** the model is never fetched unless the user presses Download in the Smart search sheet; the sheet states the size, the licence and what is sent; files are pinned to a revision and checked for size and digest before they are kept; failures are typed (`network`, `http`, `size`, `hash`, `disk`, `model`, `tokenizer`, `oom`, `inference`) and shown in the sheet and Diagnostics; the model runs in `:analysis` (ADR 0006 addendum) and R8 keeps `ai.onnxruntime.**` (`consumer-rules.pro`): a model error is an exception, never an abort. The All photos search circle exists only while the model is installed. Nothing else in the app may open a socket. **What counts as a result** (ADR 0006 addendum 3, measured on 5,233 real photos): a query is an ensemble of "q" and "a photo of q"; a photo close to everything (a "hub") is held back by a correction measured once against a bank of generic queries; a query finds nothing unless its best (corrected) cosine reaches the floor of the model in use (`SmartModelSpec.minScore`, 0.26 for the pinned CLIP; scale-free statistics were measured and separate real queries from nonsense far worse); the matches are the photos 2.5 spreads above the noise and 0.6 of the way to the best photo, at most 600. F1 0.70 on Caltech-101 (object photos); a person's photos and phrases are not measured: if real searches find too little the floor goes down (`tools/ml/smart_eval`, README).
10. **Verification:** new UI is rendered to PNG and reviewed (see `docs/plans/photos-v3-search-explore-viewer.md` §11); nothing is called smooth or working on device without a profile-mode number or a device run.

## 20. R-CHROME — one set of bars, buttons and capsules, and how they move (owner decisions, 2026-10-13)
Applies to: `packages/design_system/**`, `packages/features/**`, `packages/viewer/**`, `app/lib/shell/**`.

1. **Two tiers, fixed sizes.** Bar tier (the shell): bar 56, and **every circle beside a bar is 48** (search, ✕, ⋮: `FloatingMetrics.circle`). Header tier (pushed pages, viewer, story player): back circle 40 (touch area 48), capsule 32, header ⋮ 40 (`GlassCircleButton.small`, `AppMenuButton(small: true)`). Selection mark on a tile 22–30 (20% of the tile). No screen sets its own size.
2. **One component per job; nothing is drawn twice.** Lower bar of every section: `FloatingBarRow` (`FloatingBar` + `AnimatedBarSlot`s). Top bar: `MorphingBar`. Header of a pushed page and of the viewer: `PageHeader` (`AppBackButton` + `AppCapsule`). Tile selection: `SelectMark`. A new screen composes these; it does not build its own pill, circle, capsule or back button.
3. **A bar changes by morphing, never by being replaced.** When its content changes (`contentKey`): the old content fades out (90 ms), the bar stretches or shrinks to the new content (300 ms, `standardCurve`, no overshoot), then the new content pops in (70 ms later, 200 ms). The same key updates in place without an animation (a count going 3 to 4). A circle beside the bar opens from width 0 and closes back to it (`AnimatedBarSlot`). Reduced motion: instant (an `AnimatedSize` gets 1 ms, never zero).
4. **Selection.** The count ("5 selected") is in the top bar, which stretches or shrinks around the text; the big section title stays the section name. The ✕ opens before the lower bar, which shows the actions; the ⋮ stays and changes its entries.
5. **The viewer continues the bar under it.** Opened over the shell, its bar starts as that bar (the shell's bar hides under it), then morphs to the viewer's actions; closing morphs back (`ViewerLowerBar`). Only the photo on screen is a `Hero`; the grid scrolls the viewer's photo into view while the viewer is open (`MediaGridView.revealIndex`) so the picture flies into a tile that is really there.
   **Viewer pictures and strip** (ADR 0009): a photo shows three pictures, each fading in over the last (the grid's own decoded picture, a 512 px one, the screen-size one read straight from the file through `ViewerImageProvider`); neighbours are prefetched only after a swipe has settled; the filmstrip is moved by the pager every frame (never by its own animation), thumbnail size and outline come from the distance to the middle, and pages keep to small pictures while a finger scrubs the strip. Nothing in the viewer goes through `AssetEntityImageProvider` on Android except as the fallback when a file cannot be read.
6. **Grid.** 1 to 8 columns (`gridColumnsProvider`), remembered. **Pinch is a per-photo transition, not a scaled layer** (`PinchMorph`, `PinchSession`, `PinchLayer`): while two fingers are down the grid keeps its columns and is hidden (an `Opacity` that is always in the tree, so the scroll view never changes parent and keeps its position); a layer draws every visible photo and day heading travelling from where it is in the layout with the whole number of columns above what the fingers ask for to where it is in the one below. The asked columns are a real number, rubber-banded past 1 and 8 (the whole picture scales a little about the fingers). The photo under the fingers stays under them in both layouts (its vertical place is anchored; the grid never shifts sideways), and the fingers can also pan. A photo whose other end is more than 0.6 screens away fades in place instead of flying. Haptic tick on each whole level. On release the layer springs to the nearest whole number (a quick flick carries on a little further) and in the very frame it is removed the grid appears with that many columns, scrolled by `PinchMorph.scrollFor` to exactly where the layer left the photos (`pinch_grid_test.dart` compares the layer's last frame with the grid's first, tile by tile). Reduced motion: no layer; the grid takes the nearest columns. The layer also draws what the tiles have over their pictures (`PinchOverlays`: the video badge with its length, the liked heart, the corner text, the selection mark and the inset of a selected tile, checked pixel by pixel in `pinch_overlays_test.dart`), and a photo whose picture is not decoded yet shows its soft ThumbHash picture over its colour.
7. **Thumbnails** (`ThumbnailHandler`, `ThumbnailStore`, `ThumbImage`; ADR 0009): small square JPEGs on disk at a path the Dart side computes, at two sizes only (`ThumbnailSizes`: 384 up to 448 px wide, 768 above), so pinching never asks for a file that does not exist. A hit is read straight from the file (no channel call, no existence check); a miss is made from the system thumbnail, newest request first, equal requests merged. A native, low-priority warm-up prepares the **whole library** newest first and leaves each photo's average colour in `colors.bin`, which is the tile's colour until its picture arrives (never flat grey where the colour is known). Grid tiles draw through `ThumbImage`, which resolves the provider itself so a fling never defers a thumbnail; never wrap a grid thumbnail in `Image`. Never decode a full original for a grid cell. **What a jump to anywhere does** (ADR 0009): the grid tells `ThumbnailScheduler` what is on screen (`setViewport`, nearest the middle first); the scheduler keeps at most 8 requests with the Android side, serves the screen before landing guesses before older requests, and re-orders what waits whenever the screen moves; a fling's landing place is predicted from the scroll simulation (`PredictingScrollPhysics`) and those thumbnails are made while it still moves; a finger on the grid drops the guesses nobody asked for. Each photo also leaves a **ThumbHash** in `thumbhash.bin` (40 bytes; MIT, Evan Wallace): a tile shows that blurred picture the moment it is built, then the sharp one. The whole-photo thumbnail (`ThumbnailSizes.fit`, a negative size, `fit/<id>_<modified>.jpg`) is what a photo flies in as and what the viewer shows first, so opening does not re-frame it. The picture cache budget follows the phone's RAM (`mediaImageCacheBudget`). Explore settings has **Clear thumbnail cache** (it is also how a cold run is made); debug and profile builds log `thumbs jump: N tiles, first sharp, all sharp` (`ThumbTelemetry`, see `tools/bench/README.md`).
8. **Layout traps.** A `GridView`/`ListView` with `shrinkWrap` inside a list always gets `padding: EdgeInsets.zero` (it takes the bar's height as padding otherwise). A `PressScale` ignores pointer events after it was disposed. A `late` field that depends on the first `widget` value is set in `initState`, not by a lazy initializer. A stream from a service is exposed with `replayed(...)` so no update falls between "read the state" and "subscribe".
9. **Explore shows all of itself from the first frame**, in this order (owner request 2026-10-15): On this day, People, Places, Trips (when there are any), Scenes, Animals (when there are any), Browse by type, Years. There is no search card at the top: Smart search is an entry of Explore's ⋮ menu. **On this day** is one slideshow of good photos of today's date from earlier months and, where there are any, earlier years (`lookBackProvider`, `pickLookBack`: months 1–11 then years, a ±3-day window, screenshots left out; long-press "Remove for today"); it crossfades with a slow zoom and shows its period ("Last month", "2 years ago"). **People** is an endless row that slides both ways (`PeopleBubbleCarousel`), kept still and centred when there are too few to fill the width. **Scenes and Animals show only categories that have photos** (no dimmed boxes). Every collection is drawn as a `CollectionCard` (framed cover, name on the left, count on the right): Scenes, albums, smart albums, folders, Browse by type, Years. Each section is its own provider host inside a `RepaintBoundary`, so an analysis result rebuilds that section only, and the analysis waits while a list is scrolled (`PauseAnalysisOnScroll`). A section without data shows a static placeholder in its real layout and one sentence about what will be there (no shimmer, no counting, no "scanning"). A failure that is not about one photo shows a card on Explore itself with a way to the details. **Scenes come from the Smart search model when it is installed and has looked at 100 photos or more** (one zero-shot query per category in `explore_taxonomy.json`, described by a few prompts, answered by the same result policy as a search, so a category appears only when the library really has it); ML Kit labels are the fallback before it is. Trips are found per day by distance from where the phone usually is (a home chosen by the distinct weeks a place was visited), with a photo minimum that grows with the distance.
10. **Menus never block the screen** (`showAppMenu`, `AppMenuButton`; owner request 2026-10-13). A floating menu is non-modal: no barrier, no scrim. A tap outside it closes it **and reaches whatever is under the finger** (`TapRegion`, so the tap is not swallowed); a press on the control that opened it closes it (it never opens a second); Back, the app going to the background and a route change close it; a menu nobody touches closes by itself after `AppMotion.menuIdleClose` (6 s) and a touch on it restarts that time. Every ⋮ and every floating menu in the app uses this component; `showMenu`, `PopupMenuButton` and `MenuAnchor` are not used. Sheets and confirmation dialogs stay modal.
11. **Video controls** (`VideoTimeline`, `VideoPlayback`, `VideoTimelineVisibility`; owner request 2026-10-13). On the picture there is **one** control: a thin line (2 dp, 4 dp under the finger) low on the screen just above the thumbnail strip, with no panel, blur or buttons behind it. It is visible only while the chrome is visible and the video is paused, or for 2 s after playback starts or after a tap brings the chrome back, or while the finger is on it. Dragging shows the time you would land on (and a preview frame when there is one), seeks live (at most every 80 ms) and carries on playing on release if it was playing. Play/pause and mute/unmute are in the middle of the lower bar (share, play/pause, mute, delete; Like, Add to album and Details are in the ⋮ beside it) and respond in the same frame as the tap (the icon flips first, the player is asked after; the player's stale answers are ignored for 500 ms); mute belongs to the session. There are no ±10 s buttons, no skip gesture, no speed chip and no centre play disc; a long press on the picture plays at 2× while held. A double tap on the picture plays or pauses. It does not delay a single tap: the first tap acts at once (shows or hides the bars); a second one within 300 ms and 100 dp takes that back and toggles play instead (`VideoPage._tapUp`).
12. **Viewer pictures and deep zoom** (`ZoomableImage`, `DeepZoomLayer`, `ViewerImageProvider`; ADR 0009). A photo opens on the picture the grid already decoded, then the whole-photo thumbnail, then a 512 px one, then the screen-size one decoded straight from the photo's file (shrunk while decoding, rotation applied), each fading in over the last. Zoomed in past 1.6×, once the fingers rest for 140 ms, the screen-size picture is no longer sharp enough: `DeepZoomPlan` cuts the original into power-of-two levels of 512 px cells and asks the Android side (`RegionHandler`, `BitmapRegionDecoder`) only for the cells the screen shows, at most 30, centre first, three at a time; they paint over the screen-size picture, which stays under them, so nothing ever goes blank. Leaving the photo closes its decoder. Page changes do not rebuild the viewer (the index is a `ValueNotifier`); the filmstrip follows the pager in the same frame.
13. **Both bars leave while the timeline handle is held** (`ChromeVisibilityController`, `ChromeVisibilityScope`, `ChromeSlide`; owner request 2026-10-15). While a finger is on the white scroll handle (`FastScrollThumb`) the top bar and title slide up out of the screen and the lower bar slides down out of it, the fade scrims fade, and nothing under them takes a touch; when the finger lets go (or the touch is cancelled, or the page goes away while it is held) they slide back. Several askers are counted, so the bars stay away until all have let go. A page that has no controller above it does nothing. Verified on the Nothing A069.
14. **One dialog frame** (`AppDialogFrame`, `showAppConfirmDialog`, `showAppTextDialog`; owner request 2026-10-15). Every confirmation and every "type a name" box is the same card: at most 360 dp wide, 24 dp padding, the title in the serif, the content, then one row of **equal-width** buttons (the quiet Cancel on the left, the primary action in white on the right) that fills the card. The card is centred and moves up with the keyboard instead of sitting behind it. A text box selects the old name, capitalises words and shows no character counter. No feature builds its own `AlertDialog` or `Dialog`.
15. **A page has its ⋮ at its right edge, or next to its lower bar** (never in the middle next to the title): `PageHeader` puts its trailing control at the right edge. A page with many actions (a person) shows the common ones in its lower bar, which starts as a small pill and morphs open like every other bar, and the rest in the ⋮ circle beside that bar; its header is only the back button and, once the big title has scrolled away, the capsule.
16. **Motion blur: only on page transitions, never on scrolling.** A blur over the whole scrolling content was built and measured on the Nothing A069 (Photos timeline, eight hard flings each way, three runs per build): frames shown 1,050 with it against 2,400 without, the 90th percentile between frames 42 ms against 8 ms. It was removed. The blur on a page transition (`SharedAxisTransitionsBuilder`, at most 2.2 dp along the slide, gone after the first 55 % of the way in, none with reduced motion) stays because the owner asked for it; it costs about two frames over 25 ms per open-and-close (142 against about 95 in 24 transitions on the A069), and `--dart-define=PICSPACE_NO_TRANSITION_BLUR=true` builds an app without it to measure again. Do not add another full-screen filter to scrolling content without a number like this one. Frame times are read with `tools/bench/device.ps1` (`Frames`).
17. **Lists and carousels.** `PauseAnalysisOnScroll` holds the background analysis while a long list (Explore, albums, people) is scrolled. Each Explore section reads only its own data in its own host widget inside a `RepaintBoundary`. A faces carousel (`PeopleBubbleCarousel`) is a `CustomScrollView` with a `center` sliver and `null`-ended builders in both directions, so it needs no copies of the list; a face picture provider is not auto-disposed (a bubble that scrolls away and back must show its face in the same frame).
