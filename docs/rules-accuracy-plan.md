# Rule accuracy plan: every defined rule fires when it happens, and only then

Status: superseded 2026-10-17 by the implemented design in [rule-engine.md](rule-engine.md) (what was built, how it was measured, what is not done). The root causes below still hold.

## 1. Why rules give false positives today (found in `storage/safespace.db`)

| # | Cause | Evidence |
|---|-------|----------|
| 1 | **The compiler silently drops clauses.** "if someone sits on the chair" compiled to `entity_present(person)`, marked SUPPORTED and active, so every visible person fires `person_on_chair`. | rule `r_239f2700…`, 3 alerts on 2026-10-16 |
| 2 | **The VLM describes but does not gate.** Review jobs run *after* `insert_event_once` has broadcast the alert. "Person after hours" alerted while Gemma's summary said "No people are clearly visible". | events of rule `rule_6a0805c152fb` |
| 3 | **The engine only knows "foot point in polygon".** There are no person-object relations (sit, touch, near), no keypoints, no entry/exit transitions, no line direction, and one flicker frame resets a hold. | `services/rules/engine.py` |
| 4 | **"Door" cannot be expressed.** Door is not a COCO class, and with no drawn zone the rule is UNSUPPORTED. | rule `r_dcc41cb4…` |
| 5 | **Two rule paths** (compiler `r_*` and template `rule_*`) are evaluated in **two places** (`services/api/app/mobile_camera.py` for the phone and `services/rules/worker.py` for RTSP/webcam), so a fix in only one place half-lands. | |
| 6 | Rule alerts are hardcoded `severity=MEDIUM`, `verified_by=NONE`, while the phone only pushes HIGH/CRITICAL, so a verified rule alert may never notify. | `rule_routes.ingest_rule_event` |

## 2. Target pipeline (one shared function, called from both camera paths)

```
frame (5 fps)
  -> YOLO26 detect+ByteTrack, all COCO classes      (~8-15 ms, already running)
  -> YOLO26n-pose, only if an active rule needs keypoints (~6-10 ms), matched to person tracks by IoU
  -> AnchorMemory: stable object boxes (chair, couch, bed, door zone...) kept 60 s through occlusion
  -> RuleEngine: primitives + hysteresis (K-of-N frames to start, M frames to end)
  -> Fire candidate
  -> Gemma gate (async thread, never blocks frames): 3 episode frames with boxes drawn,
     shuffled multiple-choice question, pass only on the positive option  (~1-2 s)
  -> verified -> RuleEvent(status CONFIRMED, verified_by VLM, spec severity) -> broadcast + push
  -> rejected -> audit log only (storage/logs/rule_gate.jsonl), never broadcast
```

Module layout: `services/rules/interactions.py` (pose matching, anchors, relations),
`services/rules/gate.py` (Gemma verification), `services/rules/runtime.py` (the shared
detect -> evaluate -> gate -> emit step used by `mobile_camera.py` and `worker.py`).

## 3. Work items, in order

1. **Compiler coverage invariant (fixes cause 1).** Every action verb (sit, touch, enter, leave, cross,
   pick up, open, approach...) and every object noun (COCO classes, door/gate/entrance) in the text must
   map to a condition. Otherwise the rule is UNSUPPORTED with a specific reason; it is never reduced to presence.
   Add a deterministic pattern parser for the common phrasings before the Gemma fallback (faster, predictable).
   Recompile or deactivate the live `person_on_chair` rule.
2. **New primitives** (contract: `RuleWhen` gains `object` and `direction`; add to the `expected` map, then
   run `scripts/export-contracts.py`; `ObservedTrack` gains optional `keypoints`):
   - `near_object(object)`: person box within 0.15 x person height of the object/anchor box.
   - `touches(object)`: a wrist keypoint (conf >= 0.3) inside the object box expanded by 5% of person height for >= 0.4 s.
   - `sits_on(object)`: both hips inside the expanded chair/couch/bench/bed box, thighs near horizontal
     (hip-knee dy < 0.5 x torso), sustained >= 1.0 s.
   - `enters_zone(zone)` / `exits_zone(zone)`: outside for >= 0.6 s, then inside for >= 0.6 s (or first seen
     inside the zone, i.e. came through it). "Inside" = foot or ankle in polygon, or >= 50% of the box in polygon.
   - `line_cross(line, direction)`: `a_to_b` / `b_to_a` / any (templates already say `A_TO_B`).
   - Hysteresis on every condition: tolerate <= 0.4 s of false frames inside an episode, and require a minimum track age and box size.
3. **AnchorMemory.** A seated person hides the chair, and YOLO then drops it. Boxes seen in >= 60% of frames over 2 s
   become anchors and are kept for 60 s, with no decay while a person overlaps them. A user-drawn zone named door/gate/entrance
   is a door anchor.
4. **Gemma gate (fixes cause 2).** Use the existing `LocalLLM`, aligned with `ollama_runtime()` (`num_gpu`/`num_ctx`).
   Ask a multiple-choice question per primitive, e.g. sits_on: sitting on the chair / standing or walking near it / no person / unclear.
   Shuffle the option order to cancel position bias. The verdict, reason and latency go into the event.
   If Ollama is down: HIGH-reliability rules are sent marked "unverified", and interaction rules are held for review.
5. **Delivery (fixes cause 6).** Use `spec.severity`, set status CONFIRMED and verified_by VLM on a pass, and confirm that a phone push arrives.
6. **Reliability tiers**, stored in `config/rule_capabilities.yaml` and shown in the readback:

   | Rule shape | Tier | Why |
   |---|---|---|
   | person in drawn zone / crosses drawn line (direction) / dwell / count / time window | HIGH | person detection is strong; geometry is exact |
   | enters/exits a drawn door zone | HIGH | transition + hysteresis + gate |
   | sits on chair/couch/bench/bed | MEDIUM-HIGH | needs visible hips/knees; anchors cover occlusion; gate confirms |
   | near object | MEDIUM-HIGH | box geometry, 2-D only |
   | touches large object (chair, door handle zone, laptop, fridge) | MEDIUM | wrist keypoint + depth ambiguity; gate decides |
   | touches/holds small object (phone, cup, keys) | LOW | small-object recall at 640 px is weak |
   | door without a drawn zone (auto-locate with YOLOE open-vocab, stretch goal) | MEDIUM | |
   | intent words (steal, fight, scratch), colours, identities | UNSUPPORTED | no detector; refused explicitly |

7. **Evaluation (honest, blind):**
   - Replay `storage/recordings/*` (real scenes where the events mostly do not happen) to measure **false alerts per hour
     per rule, before and after the gate**. Inspect each fire's keyframe and label it TP or FP.
   - Measure recall on six short phone clips: sit on chair, stand beside chair, touch chair, walk past door, enter door, empty room.
   - Report latency per stage (detect+track, pose, engine, gate) and event-to-alert time, plus GPU memory with Ollama
     loaded (budget: 6 GB, currently ~4.8 GB peak).
   - Measure `yolo26s` against `yolo26n` for chair and couch recall (both are already on disk).

## 4. Models (all open-source, all local)

- YOLO26n/s detect (on disk), **YOLO26n-pose** (Ultralytics release asset, ~7 MB, auto-downloaded on first use),
  Gemma 4 e2b via Ollama (already installed). Optional later: YOLOE open-vocab for door auto-location.
- CLIP is deliberately skipped: zero-shot "sitting vs standing near" is unreliable, and pose geometry plus the Gemma gate cover its role.

## Progress

- [x] Root-cause analysis and this plan
- [ ] 1 compiler coverage invariant + recompile live rule
- [ ] 2 primitives + contracts export
- [ ] 3 AnchorMemory
- [ ] 4 Gemma gate
- [ ] 5 delivery/severity
- [ ] 6 reliability tiers
- [ ] 7 evaluation report
