# Rule engine: what runs, how it was measured, what is not done

Implemented 2026-10-17 from the accuracy-first plan. Every number below says whether it was measured and on what. Nothing here
claims zero false alerts or general accuracy: the measurements are small, from one room, and partly tuned on the same footage.

## How a rule becomes an alert

```
frame -> blur gate -> scene guard -> detector + tracker (conf 0.1) -> plausibility gates -> [pose] -> rule engine
      -> candidate -> geometry/pose rules: verified at once      (services/rules/runtime.py, used by the phone path and the RTSP worker)
                   -> visual rules: evidence pack -> API verifier -> Gemma forced choice -> verified / rejected / unverifiable
```

* **Blur gate:** frames whose 320 px Laplacian variance is below `quality.blur_min_laplacian_var` (100) are skipped; they neither start nor end episodes.
* **Scene guard:** ORB features against a reference frame. Two moved frames pause every zone, line and object rule; three steady frames resume. A rotated phone or a frame of a different shape from the drawn geometry also pauses them. Same shape at another resolution: the geometry is scaled. One `camera_moved` health event per 10 minutes.
* **Plausibility gates (`quality:` in `config/rules.yaml`):** mean detector score over 2 s, share of the frame covered, number of frame borders touched. A failing detection is not a tracked object. `require_pose_support` is **on**: every "person" must also show a coherent skeleton (pose weights installed 2026-10-17). A very close person with a visible torso is kept (the box gates are waived); a person visible only from the legs down is not a tracked person. If `weights/yolo26n-pose.pt` is missing the skeleton check is skipped with a logged warning rather than failing.
* **Episodes:** a short run of false frames (1 s) does not end an episode; cooldown is per rule/zone (not per track id), with an hourly cap, so tracker id changes no longer produce one alert each.
* **Verification policy per rule:** `geometry` (deterministic evidence), `pose`, or `vlm`. Only `verified` becomes an incident. `unverifiable` follows the rule's `on_unverifiable`: `hold_for_review` (default: category `RULE_UNVERIFIED`, severity LOW, no phone push), `send_unverified` (a `RULE_ALERT` marked "Unverified"), or `drop`. `rejected` and `expired` go to `storage/logs/rule_gate.jsonl` only.
* **The visual check** (`services/api/app/rule_verify.py`): one consumer in the API process, shared priority gateway (P0), bounded queue of 8 (lowest severity, oldest evicted as `expired`), candidates older than `max_candidate_age_s` expire, a `camera_moved` event cancels what is queued for that camera, Ollama health cached 5 s, model warmed on rule activation. It asks one lettered question with an explicit "cannot tell" option (`services/rules/verify_questions.py`), options shuffled per request; only the positive letter verifies; anything unparseable is unverifiable. It is never asked about geometry.

## Demo rules: what they do and what they need

Phrases that work on a door zone (Zone polygon, role Door) drawn around the doorway, with the phone propped steady:

| Say | Becomes | Fires when |
|---|---|---|
| "a person comes in through the door" | `enters_zone` door | someone **first appears inside** the door zone (a person coming through a door has no earlier position outside it). In a zone with the role Door, walking from the room into the zone's image area is **not** coming in, and the one-frame inside/outside flips of a person standing at the edge never count |
| "someone goes out through the door" | `exits_zone` door | a person standing in the door zone is **lost for 0.8 s** (they walked out of view through the door). Walking into the door's image area and staying visible is neither coming in nor going out |
| "a person sits on a chair" | `sits_on` any chair | pose shows both hips in the chair's seat band with an upright torso and legs bent, held still for 1.0 s (the default hold for sit rules). Chairs are remembered after the detector loses them behind the sitter, and the remembered box keeps its full size while a person covers part of it (the detector shrinks the chair to its visible part, which used to move the seat band off the hips). Evidence method is `pose`; the Gemma visual check is **off by default** (`verification_defaults` is empty) because it has never been calibrated on real positives |
| "someone opens the door" | `zone_changes` door | the picture inside the door zone changes for 0.4 s with people masked out, and the brightness shift is measured on background pixels only (a dark jacket entering the frame makes the phone raise its exposure). Unknown while a person hides the zone (the previous answer is kept). A change only counts when someone is within 0.12 body heights of the door, or nobody is in view; a shadow or reflection while people are elsewhere does not. Experimental |

Cooldown: new rules default to 120 s between alerts for the same rule; the four live demo rules were set to 20 s so a second try soon after still alerts. People in a doorway are often partly hidden, so the pose-support requirement is waived **inside a door-role zone only** (the score and size gates still apply there).

Camera movement: picture-content rules (door opens) pause when the view shifts more than 4% of the frame width; detection-based rules (comes in, sits on) pause beyond 15% (`scene_guard` in `config/rules.yaml`). A hand-held phone shifts far more than that (median 48% on the stored door clip), so the phone must be propped or mounted for zone rules. On that clip with the guard disabled, "comes in" fired exactly when the person reached the doorway, but "door opens" also fired from camera motion alone, which is why it is strict.

**Replayed on the two real test videos** (`ruleset testing/`, steady phone, 478x850; `tests/test_rules_real_video.py`, skipped when the videos or weights are missing; 12.30.05 is a byte-identical copy of 12.28.32):

| Video | What happens | Alerts (seconds into the clip) |
|---|---|---|
| 12.28.20 | walks in from the left, sits, stands, leaves left | comes in 3.4, sits 8.0, goes out 11.8; no door-open |
| 12.28.32 | walks to the glass door, opens it, goes out | door opens 5.8, goes out 10.0; no comes-in |

Before the fixes the live rules fired none of this correctly: the pose requirement dropped a person in the doorway for 0.8 s of their entry, the detector's shrunken chair box moved the seat band off the sitter's hips, a door zone could not tell walking in from going out, and the door-open signal was moved by people and by auto-exposure. **This is not blind accuracy**: the fixes were made while looking at these same two clips (one person, one room, two clips), so the test guards against regressions and says nothing about other doors, chairs, people or lighting. A hand-held phone still defeats zone rules (see above).

## Writing rules

Rules are compiled by a deterministic parser first (sits on, touches, picks up, next to, goes missing, enters/leaves a door), then the local model for older phrasings. **Every action word, object noun and name must be honoured by a condition**, or the rule is refused with the word named (`config/rule_lexicon.yaml`). A rule that needs something you have not set up returns a "to make this rule work, first" list.

| You say | What you must have set up (dashboard: Zones, lines and objects) |
|---|---|
| "…sits on the chair" | the chair marked as an object, pose weights installed |
| "…enters the front door" | a line named with `door` in it; side A = outside, side B = inside (the arrow points A to B, use Flip) |
| "…the backpack goes missing for 10 seconds" | the backpack marked as an object |
| "…picks up the bag" | the bag marked as an object ("a bag" is refused: the rule needs one specific bag) |

Obvious misspellings are read charitably ("entres throught the door" is read as "enters through the door") and every correction is shown in the readback; a word is only corrected when exactly one known word is one edit away, never into a negation or an intent word, and real unknown words ("dances") are still refused. A door drawn as a **zone** fires when someone walks into that area, including walking past it (the readback says so); a door drawn as a **line** across the doorway knows which way people go. Rules that were refused before you set something up do not re-check by themselves: set them again after saving the geometry.

"Steals", "unauthorized" and "suspicious" are refused with a suggestion for the visible pattern instead. Pose-based and multi-step primitives are `EXPERIMENTAL` and need an explicit acknowledgement to activate.

Rules already stored whose text asks for more than their conditions check (the live "if someone sits on the chair" rule compiled to "a person is visible") are skipped by the workers and cannot be activated, without any change to the database.

## Measured (and how much to trust it)

**Phone footage A/B** (`scripts/eval/rules_ab_visible.py`, evidence in `storage/eval/rules/baseline_ab_2026-10-17/` and `ab_pose_2026-10-17/`): 6.6 minutes of the stored phone recordings (45 ten-second segments, handheld, portrait and landscape), rule "a person is visible", each alert's frame labelled by eye by one person. Re-running the "before" configuration reproduced its 17 alerts exactly.

| Configuration | Alerts | Real person | False |
|---|---|---|---|
| Before (conf 0.35, no gates) | 17 | 7 (+1 head at the frame edge) | 9 (backpack, fabric) |
| Shipped gates, pose off | 11 | 8 | 3 (denim close-up, two backpack corners) |
| Shipped gates + `min_track_score` 0.65 | 8 | 7: **loses the person standing in the doorway** (score 0.63) | 1 (the denim close-up, detector score 0.79) |
| Shipped gates + `require_pose_support: true` (**now the default**) | 7 | 7 | 0; **loses one real person**, visible only from the knees down at the top edge of the frame |

What this does and does not show:

* Pose support removed every false alert on this footage (denim close-up, backpack corners) because none of them has a coherent skeleton, and it did so with thresholds fixed before the footage was looked at (at least five keypoints at 0.5 confidence, including a shoulder and the nose or a hip). A score threshold cannot do this: the denim close-up scores 0.79 and the doorway person 0.63, so any score cut between them either keeps the false alert or drops the real person. The 0.65 row exists to show that, not as a recommendation.
* The cost is recall for people who show no torso: the legs-only person above is gone. Such a person is silently not a tracked person, not "unverifiable".
* Caveats that remain: seven to eleven alerts, one room, one labeller, and the same footage that shaped the other gates. A closer look during this work found that I had mislabelled one frame (the doorway person, first called a door-glass false alarm), so labels here are fallible, and an earlier version of this document wrongly said the 0.65 row lost nothing. Recall is only measured against what the old pipeline alerted on, not against all the people in the footage.
* `require_pose_support` is **on** in `config/rules.yaml` (turned on 2026-10-17 after this A/B; set it to `false` to go back). With it on, the runtime step measured p50 11 ms and p95 40 ms per processed frame over 1986 frames (blur gate, guard and pose together), and pose added under 100 MiB of GPU memory (not distinguishable from noise next to the detector's 214 MiB).

**Rule compiler with the real local model** (`scripts/evaluate_rule_compiler.py`, 24 golden prompts, `tests/golden_rules_results.md`): 24/24 correct, about 3 to 8 s per compile (the earlier 12 to 28 s figure predates the GPU-offload fix). Three things shaped this, all measured on that set:

* `think: false` made compiles ~25x faster (0.7 s) but the model then dropped the zone or the negation in 4 of the 20 older prompts, so thinking stays on for compilation (`llm.think` in `config/rules.yaml`).
* The coverage invariant catches such drops (a zone named in the text but unused, a negation without a `not`, a clock time without a time window, "at least N" without a count) and refuses the rule instead of compiling a weaker one. With thinking on it still refused 3 of 24 on one run; a corrective retry with the exact reason, plus three narrow repairs for unambiguous slips (a missing line that the text names, an empty time window, "no person is visible"), brought that to 0. Model output varies between runs even at temperature 0, so expect an occasional refusal.
* The invariant is applied to deterministic and model-compiled rules alike, and to stored rules (which is how the live "sits on the chair" rule is caught).

**Visual check against the real model** (Gemma 4 E2B through Ollama, the same request the API sends: forced-choice schema, `think:false`, three images): the schema, the images and the decode all work. Four checks on two stored frames (a standing person, a backpack): 560 to 630 ms, one 1.75 s run, and the answers were sensible ("standing near the table" for the person; "no" or "cannot tell" for the backpack, with different answers on repeated identical input). A *positive* case (a person actually seated on a marked chair) was never exercised, so the verifier's ability to say yes is untested. GPU memory was about 5.4 of 6.1 GB with the model resident, with other processes running.

Other measurements: tracking median 10.6 ms/frame (`tests/benchmarks.md`, one clip). **Not measured:** sit/touch accuracy with real keypoints, verifier accuracy on real candidates, end-to-end time-to-alert, any recall on sit/touch/door/pick-up events.

## Evaluate a change

```bash
python scripts/eval/rules_replay.py --clip <mp4> --camera-id <id> --rules rules.json --geometry geometry.json --out storage/eval/rules/run1
python scripts/eval/rules_score.py --alerts storage/eval/rules/run1 --labels tests/fixtures/rules/labels --out storage/eval/rules/run1 --baseline storage/eval/rules/baseline/report.json
```

Labels are `<clip>.json` with `{"negative": bool, "events": [{"rule", "start_s", "completion_s"}]}`. The scorer reports counts with 95% intervals and an event-level regression diff (newly missed events, new false alerts). Quote the interval bound: 0 false alerts in 4 camera-hours only supports "≤ 0.75 per hour"; showing ≤ 0.2 per hour needs about 15 hours.

## Not done

* Labelled scripted clips (door, sit, touch, pick-up, hard negatives) and the real baseline on them. Door, sit and door-open were replayed on the two clips above (which shaped the fixes); touch, pick-up and every hard negative (someone leaning on a chair, a passer-by, a pet, a curtain) have not been measured on video; they are unit-tested with synthetic tracks and keypoints.
* Pose weights are installed (`weights/yolo26n-pose.pt`, 7.9 MB, SHA-256 recorded on first use). One real seated person was run through the sit rule (one chair, one clip); touch has only synthetic keypoints.
* The visual check ran against real Gemma on two stored frames only (no positive case) and has no accuracy calibration; the 15 queue/outcome tests use a mocked model.
* Anchor presence uses detector overlap, not DINOv2 crop similarity, so it can mistake a different object of the same class in the same place for the original.
* `sequence` has no "leaves the scene" step; `violence_detected`, fall detection, the pick-up-and-leave theft template, the rule dry-run endpoint and the YOLOE setup helper are not implemented.
* Episode end does not cancel an in-flight visual check (only a moved camera and age do).
* Dashboard and mobile screens do not display the `verification` details yet; the phone app does not yet send `X-Capture-Ts` (the server accepts it and otherwise uses arrival time). Dart changes were not made because they cannot be compiled here.
* The ruleset readback and activation gate cover the rules created from templates and the builder; stored rules are re-checked only for dropped clauses.
