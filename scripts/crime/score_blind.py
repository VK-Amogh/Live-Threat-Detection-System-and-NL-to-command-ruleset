"""Score the blind parents (never trained on, never used to pick the model, temperature or thresholds) with the saved crime-type head.

python scripts/crime/score_blind.py [--write]
Reports, in this order: open-set per-type precision/recall with counts and parent-cluster bootstrap intervals, closed-set top-1/top-3, the confusion
matrix, the same-video diagnostic (label-1 vs label-0 sub-clips of the SAME videos), where Arson and the ambiguous label-0 clips land, a camera-similarity
split, and the pre-registered surface decision per type. --write stores the decision in the model sidecar (`supported`) - only when every check,
including the real-footage false-alarm run (scripts/crime/eval_recordings.py), has been measured.
The bar below was written down (docs/crime-type.md, shared notes) before any blind clip was scored; do not tune it after seeing results.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent))
from crime_common import CLASSES, NONE, PROPERTY_GROUP, ROOT, TYPES, VIOLENCE_GROUP, bootstrap_precision_recall, label_index, load_features, predict_types  # noqa: E402
from crime_head import CrimeHead, softmax  # noqa: E402
from train_crime import COLUMNS, logits_of  # noqa: E402

SURFACE_BAR = {'min_blind_parents': 5, 'precision': 0.70, 'precision_lower95': 0.50, 'recall': 0.30, 'parent_hit_rate': 0.50, 'same_video_auc': 0.70, 'recordings_window_far': 0.02}
HOLD_FOR_USER = {'Explosion': 'overlaps the removed fire/smoke scope (visible fireballs/smoke): needs the user to decide before it is surfaced'}


def load_model(name='crime_type'):
    side = json.loads((ROOT / f'storage/models/{name}.json').read_text())
    cfg = side['config']
    model = CrimeHead(hidden=cfg['hidden'], dropout=cfg['dropout'], blocks=tuple(cfg['blocks'])).cuda().eval()
    model.load_state_dict(torch.load(ROOT / f'storage/models/{name}.pt', map_location='cuda', weights_only=True))
    return model, side


def probabilities(model, side, X):
    return softmax(logits_of(model, X, side['config']['features']), side['temperature'])


def auc_with_ci(score, label, parents, reps=500, seed=0):
    """AUC (label 1 vs 0) with a parent-cluster bootstrap interval; None when either label is missing."""
    if len(set(label)) < 2:
        return None
    point = float(roc_auc_score(label, score))
    ps = np.unique(parents)
    at = {p: np.where(parents == p)[0] for p in ps}
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(reps):
        idx = np.concatenate([at[p] for p in ps[rng.integers(0, len(ps), len(ps))]])
        if len(set(label[idx])) == 2:
            draws.append(roc_auc_score(label[idx], score[idx]))
    return {'auc': point, 'ci95': [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))] if draws else [None, None], 'n_label1': int((label == 1).sum()), 'n_label0': int((label == 0).sum())}


def confusion(pred, rows_idx_by_group):
    table = {}
    for name, idx in rows_idx_by_group.items():
        counts = np.bincount(pred[idx], minlength=len(CLASSES))
        table[name] = {'n': int(len(idx)), **{CLASSES[c] if c != NONE else 'none/abstain': int(counts[c]) for c in range(len(CLASSES))}}
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', default='crime_type')
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    model, side = load_model(a.name)
    taus = side['thresholds']
    rows, X = load_features()
    blind = np.array([r['role'] == 'blind' for r in rows])
    rows, X = [r for r, b in zip(rows, blind) if b], X[blind]
    prob = probabilities(model, side, X)
    pred, p_top = predict_types(prob, taus)
    source = np.array([r['source'] for r in rows])
    category = np.array([r['category'] for r in rows])
    dlabel = np.array([-1 if r['dcsass_label'] is None else r['dcsass_label'] for r in rows])
    parents = np.array([r['parent'] for r in rows])
    truth = label_index(rows)                                                   # type / none index, -1 = no trusted label
    truth = np.where(source == 'arson_out_of_scope', -2, truth)                  # Arson: never a correct answer for any type
    scored = source != 'dcsass_noncalm_label0'                                   # ambiguous ground truth: excluded from precision/recall
    n_parents = {t: len({parents[i] for i in np.where((truth == c))[0]}) for c, t in enumerate(TYPES)}
    print(f'{len(rows)} blind clips from {len(set(parents))} parents; scored for precision/recall: {int(scored.sum())}')
    print('thresholds:', {k: (None if v is None else round(v, 2)) for k, v in taus.items()})

    report = {'generated_at': time.time(), 'bar': SURFACE_BAR, 'thresholds': taus, 'temperature': side['temperature'], 'blind_clips': int(len(rows)), 'blind_parents': int(len(set(parents))), 'types': {}}
    print('\n== open-set per type at the calibrated thresholds (precision counts none-source, other-type and Arson clips as wrong)')
    print(f'{"type":14s} {"parents":>7s} {"clips":>5s} {"flagged":>7s} {"prec":>6s} {"95% CI":>13s} {"recall":>6s} {"95% CI":>13s} {"parents hit":>11s}')
    for c, t in enumerate(TYPES):
        s = bootstrap_precision_recall(pred[scored], truth[scored], parents[scored], c)
        report['types'][t] = {'blind_parents': n_parents[t], **s}
        f = lambda v: 'n/a' if v is None else f'{v:.2f}'
        ci = lambda v: f'[{f(v[0])},{f(v[1])}]'
        print(f'{t:14s} {n_parents[t]:7d} {s["actual"]:5d} {s["predicted"]:7d} {f(s["precision"]):>6s} {ci(s["precision_ci95"]):>13s} {f(s["recall"]):>6s} {ci(s["recall_ci95"]):>13s} {s["parents_hit"]:>5d}/{n_parents[t]}')

    # closed set: which type is it, given that it is a crime clip (label-1 of a trained type)? thresholds are not used here
    typed = (truth >= 0) & (truth < NONE) & (source == 'dcsass_label1')
    top = np.argsort(-prob[:, :NONE], axis=1)
    top1 = float((top[typed, 0] == truth[typed]).mean())
    top3 = float(np.mean([truth[i] in top[i, :3] for i in np.where(typed)[0]]))
    per_class_top1 = {t: float((top[typed & (truth == c), 0] == c).mean()) for c, t in enumerate(TYPES) if (typed & (truth == c)).any()}
    macro_top1 = float(np.mean(list(per_class_top1.values())))
    chance = float(np.mean([1 / len(TYPES)]))
    # parent-level vote: most frequent argmax type over a parent's label-1 clips
    votes = []
    for p in np.unique(parents[typed]):
        m = typed & (parents == p)
        votes.append((truth[m][0], np.bincount(top[m, 0], minlength=NONE).argmax()))
    parent_acc = float(np.mean([a_ == b_ for a_, b_ in votes]))
    report['closed_set'] = {'clips': int(typed.sum()), 'top1': top1, 'top3': top3, 'macro_top1': macro_top1, 'chance_top1': chance, 'parent_vote_accuracy': parent_acc, 'parents': len(votes), 'per_class_top1': per_class_top1,
                            'majority_class_top1': float(np.bincount(truth[typed]).max() / typed.sum())}
    print(f'\n== closed set (label-1 clips of the 12 types, thresholds ignored): top-1 {top1:.3f}, macro top-1 {macro_top1:.3f}, top-3 {top3:.3f}, chance {chance:.3f}, always-the-biggest-class {report["closed_set"]["majority_class_top1"]:.3f}; parent vote accuracy {parent_acc:.3f} over {len(votes)} videos')
    print('   per-class top-1:', {k: round(v, 2) for k, v in per_class_top1.items()})

    # confusion at the operating thresholds
    groups = {t: np.where(truth == c)[0] for c, t in enumerate(TYPES)}
    groups['none: calm label-0 (DCSASS)'] = np.where(source == 'dcsass_calm_label0')[0]
    groups['none: ordinary footage (external)'] = np.where(source == 'external_none')[0]
    groups['ambiguous: label-0 of violent categories'] = np.where(source == 'dcsass_noncalm_label0')[0]
    groups['out of scope: Arson'] = np.where(source == 'arson_out_of_scope')[0]
    report['confusion'] = confusion(pred, groups)
    print('\n== confusion at operating thresholds (rows: truth, columns: what the system said)')
    names = [*TYPES, 'none/abstain']
    print(f'{"truth":42s} {"n":>5s} ' + ' '.join(f'{n[:5]:>5s}' for n in names))
    for k, v in report['confusion'].items():
        print(f'{k[:42]:42s} {v["n"]:5d} ' + ' '.join(f'{v[n]:5d}' for n in names))
    report['closed_set_confusion'] = {t: {u: int(((top[groups[t], 0] == j)).sum()) for j, u in enumerate(TYPES)} for t in TYPES if len(groups[t])}
    for t in TYPES:
        if t in report['closed_set_confusion']:
            row = {u: n for u, n in report['closed_set_confusion'][t].items() if n}
            print(f'   closed-set {t:14s} -> {dict(sorted(row.items(), key=lambda kv: -kv[1]))}')

    # same-video diagnostic: does the model tell the crime from the quiet part of the same videos?
    print('\n== same-video diagnostic: AUC of the type probability, label-1 vs label-0 sub-clips of the same category videos')
    for c, t in enumerate(TYPES):
        m = (category == t) & (source != 'external_none') & np.isin(dlabel, (0, 1))
        res = auc_with_ci(prob[m, c], dlabel[m], parents[m])
        report['types'][t]['same_video_auc'] = res
        if res:
            print(f'  {t:14s} AUC {res["auc"]:.3f} [{res["ci95"][0]:.2f},{res["ci95"][1]:.2f}]  label-1 {res["n_label1"]}, label-0 {res["n_label0"]}', end='')
        report['types'][t]['same_video_auc_anomaly'] = auc_with_ci(1 - prob[m, NONE], dlabel[m], parents[m])
        flagged = pred[m] == c
        report['types'][t]['same_video_flag_rate'] = {'label1': float(flagged[dlabel[m] == 1].mean()) if (dlabel[m] == 1).any() else None, 'label0': float(flagged[dlabel[m] == 0].mean()) if (dlabel[m] == 0).any() else None}
        rest = scored & (truth != -2)
        report['types'][t]['one_vs_rest_auc'] = auc_with_ci(prob[rest, c], (truth[rest] == c).astype(int), parents[rest], reps=200)
        fr, ovr = report['types'][t]['same_video_flag_rate'], report['types'][t]['one_vs_rest_auc']
        if res:
            print(f'   flagged {fr["label1"]:.1%} of label-1 vs {fr["label0"]:.1%} of label-0 clips of the same videos; type-vs-everything AUC {ovr["auc"]:.2f} [{ovr["ci95"][0]:.2f},{ovr["ci95"][1]:.2f}]')

    # where do out-of-scope / ambiguous clips land
    arson = np.where(source == 'arson_out_of_scope')[0]
    ambiguous = np.where(source == 'dcsass_noncalm_label0')[0]
    report['arson'] = {'clips': int(len(arson)), 'flagged_as_any_type': float((pred[arson] != NONE).mean()), 'label1_flagged': float((pred[arson][dlabel[arson] == 1] != NONE).mean()),
                       'landing': {CLASSES[c]: int(n) for c, n in enumerate(np.bincount(pred[arson], minlength=len(CLASSES))) if n}}
    report['ambiguous_label0'] = {'clips': int(len(ambiguous)), 'flagged_as_any_type': float((pred[ambiguous] != NONE).mean()),
                                  'flagged_as_own_category': float((pred[ambiguous] == np.array([CLASSES.index(c) if c in TYPES else -9 for c in category[ambiguous]])).mean())}
    print(f'\nArson (out of scope): {report["arson"]["clips"]} clips, {report["arson"]["flagged_as_any_type"]:.1%} flagged as some type; landing {report["arson"]["landing"]}')
    print(f'label-0 clips of violent categories (ambiguous truth): {report["ambiguous_label0"]["clips"]}, {report["ambiguous_label0"]["flagged_as_any_type"]:.1%} flagged as some type, {report["ambiguous_label0"]["flagged_as_own_category"]:.1%} as their own category')
    far = {}
    for src in ('dcsass_calm_label0', 'external_none'):
        for ds in sorted({r['dataset'] for r, s in zip(rows, source) if s == src}):
            idx = np.array([i for i, (r, s) in enumerate(zip(rows, source)) if s == src and r['dataset'] == ds])
            far[f'{src}/{ds}'] = {'clips': int(len(idx)), 'flagged_as_a_type': float((pred[idx] != NONE).mean()), 'by_type': {CLASSES[c]: int(n) for c, n in enumerate(np.bincount(pred[idx], minlength=len(CLASSES))) if n and c != NONE}}
    report['none_false_alarm'] = far
    print('none clips flagged as a crime type:', {k: f'{v["flagged_as_a_type"]:.1%} of {v["clips"]}' for k, v in far.items()})

    # camera-similarity split: blind parents whose scenes resemble a dev parent most vs least (guards against same-camera leakage between parents)
    all_rows, X_all = load_features()
    dev_idx = [i for i, r in enumerate(all_rows) if r['role'] == 'dev' and r['source'] != 'external_none']
    dev_mean = {}
    for i in dev_idx:
        dev_mean.setdefault(all_rows[i]['parent'], []).append(X_all[i, :1536])
    dev_vecs = np.stack([np.mean(v, 0) for v in dev_mean.values()])
    dev_vecs /= np.linalg.norm(dev_vecs, axis=1, keepdims=True)
    nearest = {}
    for p in np.unique(parents[source != 'external_none']):
        v = X[parents == p, :1536].mean(0)
        nearest[p] = float((dev_vecs @ (v / np.linalg.norm(v))).max())
    cut = float(np.median(list(nearest.values())))
    far_half = np.array([nearest.get(p, np.inf) < cut for p in parents])          # ordinary-footage sources have no dev twin score: in neither half
    half = {}
    for label, mask in (('less_similar_half', far_half), ('more_similar_half', ~far_half & (source != 'external_none'))):
        stats = {}
        for c, t in enumerate(TYPES):
            s = bootstrap_precision_recall(pred[scored & mask], truth[scored & mask], parents[scored & mask], c, reps=500)
            stats[t] = {k: s[k] for k in ('precision', 'recall', 'actual', 'predicted', 'parents_with_class')}
        half[label] = stats
    report['camera_similarity'] = {'median_nearest_dev_cosine': cut, 'halves': half}
    print(f'\n== camera-similarity split (median nearest-dev-parent cosine {cut:.3f}): recall/precision on the half of blind parents LEAST similar to any dev parent vs the rest')
    for t in TYPES:
        l, m_ = half['less_similar_half'][t], half['more_similar_half'][t]
        fmt = lambda s: f'recall {"n/a" if s["recall"] is None else format(s["recall"], ".2f")} (n={s["actual"]}) precision {"n/a" if s["precision"] is None else format(s["precision"], ".2f")} (n={s["predicted"]})'
        print(f'  {t:14s} less similar: {fmt(l)} | more similar: {fmt(m_)}')

    # group-level view (diagnostic only; no group is surfaced)
    for gname, members in (('violence (Abuse/Assault/Fighting)', VIOLENCE_GROUP), ('property crime (Burglary/Stealing/Shoplifting/Vandalism)', PROPERTY_GROUP)):
        ids = [TYPES.index(t) for t in members]
        in_group_truth = np.isin(truth, ids)
        flagged = np.isin(pred, ids)
        tp = (in_group_truth & flagged)[scored]
        report.setdefault('groups', {})[gname] = {'recall': float(tp.sum() / max(in_group_truth[scored].sum(), 1)), 'precision': float(tp.sum() / max(flagged[scored].sum(), 1)), 'clips': int(in_group_truth[scored].sum()), 'flagged': int(flagged[scored].sum())}
        print(f'group {gname}: recall {report["groups"][gname]["recall"]:.2f} ({int(in_group_truth[scored].sum())} clips), precision {report["groups"][gname]["precision"]:.2f} ({int(flagged[scored].sum())} flagged)')

    # surface decision against the pre-registered bar
    rec_path = ROOT / 'storage/benchmarks/crime_type_recordings.json'
    recordings = json.loads(rec_path.read_text()) if rec_path.exists() else None
    decision = {}
    for t in TYPES:
        r = report['types'][t]
        checks = {
            'tau_exists': taus[t] is not None,
            'blind_parents>=%d' % SURFACE_BAR['min_blind_parents']: r['blind_parents'] >= SURFACE_BAR['min_blind_parents'],
            'precision': r['precision'] is not None and r['precision'] >= SURFACE_BAR['precision'],
            'precision_lower95': r['precision_ci95'][0] is not None and r['precision_ci95'][0] >= SURFACE_BAR['precision_lower95'],
            'recall': r['recall'] is not None and r['recall'] >= SURFACE_BAR['recall'],
            'parent_hit_rate': r['blind_parents'] > 0 and r['parents_hit'] / r['blind_parents'] >= SURFACE_BAR['parent_hit_rate'],
            'same_video_auc': bool(r.get('same_video_auc')) and r['same_video_auc']['auc'] >= SURFACE_BAR['same_video_auc'],
            'recordings_far': None if recordings is None else recordings['types'][t]['window_flag_rate'] <= SURFACE_BAR['recordings_window_far'],
        }
        measured = all(v is not None for v in checks.values())
        passed = measured and all(checks.values())
        decision[t] = {'checks': checks, 'passed_bar': passed, 'held_for_user': HOLD_FOR_USER.get(t) if passed else None}
    report['decision'] = decision
    supported = [t for t in TYPES if decision[t]['passed_bar'] and t not in HOLD_FOR_USER]
    report['supported'] = supported
    print('\n== pre-registered surface bar:', SURFACE_BAR)
    for t in TYPES:
        d = decision[t]
        failed = [k for k, v in d['checks'].items() if v is False]
        pending = [k for k, v in d['checks'].items() if v is None]
        verdict = 'PASS' if d['passed_bar'] else ('NOT MEASURED: ' + ','.join(pending) if pending and not failed else 'unsupported')
        print(f'  {t:14s} {verdict:20s} failed: {failed or "-"}' + (f'  held: {d["held_for_user"]}' if d['held_for_user'] else ''))
    print('surfaceable now:', supported or 'none')
    (ROOT / 'storage/benchmarks').mkdir(exist_ok=True)
    (ROOT / f'storage/benchmarks/{a.name}.json').write_text(json.dumps(report, indent=2))
    if a.write:
        if recordings is None:
            sys.exit('refusing --write: run scripts/crime/eval_recordings.py first (the false-alarm check on real footage is part of the bar)')
        side['supported'] = supported
        side['supported_note'] = f'types that met the pre-registered bar on blind parents: {SURFACE_BAR}'
        (ROOT / f'storage/models/{a.name}.json').write_text(json.dumps(side, indent=2))
        print('wrote supported list to the sidecar')


if __name__ == '__main__':
    main()
