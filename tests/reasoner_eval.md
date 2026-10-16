# Phase 5 visual-review gate

Measured on 2026-10-16 with `gemma4:e2b` using the local Ollama server and three selected images per excerpt. The fixture builder split the five repository AVIs into 30 short excerpts. A real `person present` rule fired on 20 excerpts from four source AVIs. Excerpts from each source overlap; this is a functional review-safety probe, not 20 independent camera recordings or an accuracy estimate.

| Measure | Result |
| --- | ---: |
| Flagged excerpts reviewed | 20 |
| Final structured summaries accepted | 20/20 |
| Attempts rejected by the inference guard | 1 of 21 |
| Median visual-review time per attempt | 42.81 s |
| Longest attempt | 50.33 s |
| Positive identity or intent claims in final summaries | 0, by manual inspection |

The rejected attempt did not become an event summary. A retry of that excerpt passed. The original outputs, rejection, and final retry are in `tests/reasoner_20_results.json`. `tests/reasoner_initial_results.json` preserves the first prompt's two flawed responses; one incorrectly called a visible patio indoor and the other guessed that indistinct shapes might be dogs. The final prompt and validator reject those sorts of claims.

The LLM outage test uses the real adapter against an unreachable local endpoint. It verifies that the review is marked retryable while the API keeps the event in `DETECTED`; engine evaluation remains independent. The DB/API test verifies the later `NEEDS_REVIEW` event update and its change sequence.

Gate: **PASS for functional behavior on the available AVI excerpts.** Real night-camera review quality is unmeasured and must be evaluated when recordings are supplied.
