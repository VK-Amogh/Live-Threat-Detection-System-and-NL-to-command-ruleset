"""Crime-type classifier: leakage-safe manifest, calibration sidecar, gating of unsupported types, and the deployed heads still loading."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/inference"), str(ROOT / "scripts/crime")]
import crime_head  # noqa: E402
from crime_common import bootstrap_precision_recall, predict_types  # noqa: E402

MANIFEST = ROOT / "storage/datasets/crime/manifest.json"
SIDECAR = ROOT / "storage/models/crime_type.json"
WEIGHTS = ROOT / "storage/models/crime_type.pt"


def test_classes_exclude_arson_and_end_with_none():
    assert "Arson" not in crime_head.CLASSES
    assert crime_head.CLASSES[-1] == "none" and len(crime_head.TYPES) == 12
    assert crime_head.FEATURE_DIM == 2 * 1536 + 768 + 400


def test_pool_features_layout():
    dino = np.random.default_rng(0).normal(size=(3, 16, 1536)).astype(np.float16)
    vmae = np.ones((3, 1168), np.float16)
    pooled = crime_head.pool_features(dino, vmae)
    assert pooled.shape == (3, crime_head.FEATURE_DIM)
    np.testing.assert_allclose(pooled[:, :1536], dino.astype(np.float32).mean(1), atol=1e-3)
    assert np.all(pooled[:, -1168:] == 1)


def test_head_forward_shapes_for_every_variant():
    import torch
    for hidden in (0, 64):
        head = crime_head.CrimeHead(hidden=hidden).eval()
        assert head(torch.zeros(4, crime_head.FEATURE_DIM)).shape == (4, len(crime_head.CLASSES))
    assert crime_head.CrimeHead(blocks=(1536, 1536)).eval()(torch.zeros(2, 3072)).shape == (2, len(crime_head.CLASSES))


def test_decision_rule_respects_thresholds():
    k = len(crime_head.CLASSES)
    prob = np.full((3, k), 0.01)
    prob[0, 7], prob[1, 7], prob[2, 3] = 0.90, 0.60, 0.95           # Robbery strong, Robbery weak, Burglary strong
    pred, p = predict_types(prob, {"Robbery": 0.8, "Burglary": None})
    assert pred[0] == crime_head.TYPES.index("Robbery")               # above its threshold
    assert pred[1] == crime_head.CLASSES.index("none")               # below its threshold -> abstains
    assert pred[2] == crime_head.CLASSES.index("none")               # type without a threshold never fires
    assert p[0] == pytest.approx(0.90)


def test_surfaced_type_only_for_supported_calibrated_types():
    prob = np.full(len(crime_head.CLASSES), 0.005)
    prob[crime_head.TYPES.index("Robbery")] = 0.95
    side = {"thresholds": {"Robbery": 0.8}, "supported": []}
    assert crime_head.surfaced_type(prob, side) is None                # empty supported list switches the head off
    assert crime_head.surfaced_type(prob, {**side, "supported": ["Robbery"]})[0] == "Robbery"
    assert crime_head.surfaced_type(prob, {"thresholds": {"Robbery": None}, "supported": ["Robbery"]}) is None
    assert crime_head.surfaced_type(prob, {"thresholds": {"Robbery": 0.99}, "supported": ["Robbery"]}) is None
    assert crime_head.surfaced_type(prob, {}) is None


def test_parent_bootstrap_counts_and_resamples_videos():
    # parent A: 4 clips, 3 flagged correctly; parent B: 4 clips, 1 flagged wrongly (true class 1)
    pred = np.array([0, 0, 0, 5, 0, 5, 5, 5])
    truth = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    parents = np.array(["A"] * 4 + ["B"] * 4)
    s = bootstrap_precision_recall(pred, truth, parents, 0, reps=200)
    assert (s["tp"], s["predicted"], s["actual"]) == (3, 4, 4)
    assert s["precision"] == pytest.approx(0.75) and s["recall"] == pytest.approx(0.75)
    assert s["parents_with_class"] == 1 and s["parents_hit"] == 1
    assert s["recall_ci95"][0] <= s["recall"] <= s["recall_ci95"][1]


@pytest.mark.skipif(not MANIFEST.exists(), reason="crime manifest not built (python scripts/crime/build_manifest.py)")
def test_manifest_has_no_parent_leakage_and_clean_negatives():
    rows = json.loads(MANIFEST.read_text())
    dev = {r["parent"] for r in rows if r["role"] == "dev"}
    blind = {r["parent"] for r in rows if r["role"] == "blind"}
    assert dev and blind and not dev & blind
    for fold in range(5):
        held = {r["parent"] for r in rows if r["fold"] == fold}
        assert not held & {r["parent"] for r in rows if r["role"] == "dev" and r["fold"] != fold}
    assert not any(r["category"] == "Arson" for r in rows if r["role"] == "dev")                 # Arson is never trained on
    assert all(r["target"] is None for r in rows if r["category"] == "Arson")
    calm = {"RoadAccidents", "Shoplifting", "Stealing", "Vandalism", "Burglary"}
    for r in rows:
        if r["role"] == "dev" and r["source"] == "dcsass_calm_label0":
            assert r["category"] in calm and r["dcsass_label"] == 0
        assert r["role"] == "blind" or r["source"] != "dcsass_noncalm_label0"                    # ambiguous label-0 clips are blind-only diagnostics
        if r["target"] in crime_head.TYPES:
            assert r["dcsass_label"] == 1 and r["target"] == r["category"]


@pytest.mark.skipif(not SIDECAR.exists(), reason="crime-type model not trained")
def test_sidecar_schema_and_supported_gate():
    side = json.loads(SIDECAR.read_text())
    assert side["classes"] == crime_head.CLASSES
    assert set(side["thresholds"]) == set(crime_head.TYPES)
    assert set(side["supported"]) <= set(crime_head.TYPES)
    for t in side["supported"]:
        assert side["thresholds"][t] is not None                                                   # a surfaced type has a calibrated operating point
    assert "Arson" in side["out_of_scope"] and "Arson" not in side["supported"]
    assert side["temperature"] > 0
    for t in set(crime_head.TYPES) - set(side["supported"]):                                       # unsupported types can never be surfaced
        prob = np.full(len(crime_head.CLASSES), 0.001)
        prob[crime_head.TYPES.index(t)] = 0.999
        assert crime_head.surfaced_type(prob, side) is None


@pytest.mark.skipif(not (SIDECAR.exists() and WEIGHTS.exists()), reason="crime-type model not trained")
def test_saved_weights_load_into_head():
    import torch
    side = json.loads(SIDECAR.read_text())
    cfg = side["config"]
    head = crime_head.CrimeHead(hidden=cfg["hidden"], dropout=cfg["dropout"], blocks=tuple(cfg["blocks"]))
    head.load_state_dict(torch.load(WEIGHTS, map_location="cpu", weights_only=True))


@pytest.mark.skipif(not (ROOT / "storage/models/violence_head.pt").exists(), reason="violence weights not installed")
def test_deployed_violence_heads_still_load():
    import torch
    from violence_head import TemporalHead
    from motion import Head
    TemporalHead().load_state_dict(torch.load(ROOT / "storage/models/violence_head.pt", map_location="cpu", weights_only=True))
    Head().load_state_dict(torch.load(ROOT / "storage/models/violence_videomae.pt", map_location="cpu", weights_only=True))


def test_models_yaml_lists_unsupported_crime_types():
    import yaml
    config = yaml.safe_load((ROOT / "config/models.yaml").read_text())
    text = " ".join(config["unsupported"]).lower()
    assert "fire" in text and "smoke" in text                                                       # removed on purpose; Arson stays unsupported with it
    assert "arson" in text
