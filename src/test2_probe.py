#!/usr/bin/env python3
"""Test 2: few-example logistic-regression probe on frozen embeddings.

  .venv/bin/python src/test2_probe.py --model beats [--dry-run]

Splits come from data/splits.csv (scripts/make_splits.py: source groups never cross train/test; the
class is the human label). For k in 1, 5, 10, 20 and 10 seeded draws, k training clips per class are
drawn from the train split; the probe is scored on every test clip of the classes in the probe.
Probe: multinomial logistic regression, L2, C fixed at 1.0 (not tuned), features standardized with
statistics of the k-shot training set only. Nothing is fit, tuned or selected on the test split.

A class that has fewer than k train clips or no test clip is marked missing at that k and left out
of the probe at that k (not filled). Two probes: all classes jointly, and within-family (the family's
instruments plus their configured cousin). Draws are keyed by (seed, k, draw, class) only, so both
probes and both models see the same training clips.

Per class: recall mean and sd over draws, and a percentile cluster bootstrap over test source groups of
the per-clip correct rate averaged over draws. No pooled "non-Western" number is computed.
"""
import argparse, hashlib, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_common as E  # noqa: E402
from eval_common import C  # noqa: E402
import features as F  # noqa: E402

KS = (1, 5, 10, 20)
DRAWS = 10
PROBE_C = 1.0
BOOT_REPS = 2000
LEAK_RECALL = 0.95  # mean recall at k=1 at or above this is flagged as possible leakage


# ---------------------------------------------------------------- logistic regression
def standardize(Xtr, Xte):
    mu = Xtr.mean(0)
    sd = Xtr.std(0)
    sd[sd < 1e-12] = 1.0
    return (Xtr - mu) / sd, (Xte - mu) / sd


def _softmax(Z):
    Z = Z - Z.max(1, keepdims=True)
    e = np.exp(Z)
    return e / e.sum(1, keepdims=True)


def logreg_numpy(X, y, n_classes, C=PROBE_C, max_iter=20000, tol=1e-7):
    """Multinomial logistic regression, objective C * sum(log-loss) + 0.5 * ||W||^2, intercept unpenalized.
    Accelerated gradient with restart and step 1/L (L from the Bohning bound). Deterministic."""
    n, d = X.shape
    Y = np.eye(n_classes)[y]
    Xa = np.hstack([X, np.ones((n, 1))])
    L = C * 0.5 * np.linalg.norm(Xa, 2) ** 2 + 1.0
    reg = np.ones((d + 1, 1))
    reg[-1] = 0.0
    W = np.zeros((d + 1, n_classes))
    V, t = W.copy(), 1.0

    def grad(M):
        return C * Xa.T @ (_softmax(Xa @ M) - Y) + reg * M

    def obj(M):
        P = _softmax(Xa @ M)
        return -C * np.log(np.clip(P[np.arange(n), y], 1e-300, None)).sum() + 0.5 * (reg * M * M).sum()

    f_prev = obj(W)
    for _ in range(max_iter):
        g = grad(V)
        W_new = V - g / L
        f_new = obj(W_new)
        if f_new > f_prev:  # restart momentum; a plain step that fails to descend means converged
            if t == 1.0:
                break
            V, t = W.copy(), 1.0
            continue
        t_new = (1 + np.sqrt(1 + 4 * t * t)) / 2
        V = W_new + ((t - 1) / t_new) * (W_new - W)
        if np.abs(W_new - W).max() < tol * (1 + np.abs(W).max()):
            W = W_new
            break
        W, t, f_prev = W_new, t_new, f_new
    return W


def fit_predict(Xtr, ytr, Xte, n_classes, impl="auto"):
    """Returns (predictions, implementation used)."""
    Xtr, Xte = standardize(Xtr, Xte)
    if impl in ("auto", "sklearn"):
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError:
            if impl == "sklearn":
                raise
        else:
            m = LogisticRegression(C=PROBE_C, solver="lbfgs", max_iter=5000)  # L2 is the default penalty
            m.fit(Xtr, ytr)
            return m.predict(Xte), "sklearn.LogisticRegression(lbfgs, l2, C=1.0)"
    W = logreg_numpy(Xtr, ytr, n_classes)
    Xa = np.hstack([Xte, np.ones((len(Xte), 1))])
    return np.argmax(Xa @ W, 1), "numpy multinomial logreg (l2, C=1.0, accelerated gradient)"


# ---------------------------------------------------------------- draws and probes
def _key(name):
    return int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big")


def draw_train(train_by_class, cls, k, seed, d):
    """k train clip ids of class cls for draw d. Independent of which other classes are in the probe."""
    pool = sorted(train_by_class[cls])
    rng = np.random.default_rng([seed, k, d, _key(cls)])
    return [pool[j] for j in rng.choice(len(pool), size=k, replace=False)]


def family_probes(classes):
    """family -> instruments in that family (by config) plus the configured cousins of those instruments."""
    ins = C.instruments()
    fam = defaultdict(set)
    for c in classes:
        fam[ins[c]["family"]].add(c)
    for f, members in list(fam.items()):
        for c in list(members):
            cz = ins[c]["cousin"]
            if cz and cz in classes:
                members.add(cz)
    return {f"within_{f}": sorted(m) for f, m in sorted(fam.items()) if len(m) >= 2}


def run_probe(classes, k, splits, emb, seed, draws=DRAWS, impl="auto"):
    """One probe (a class list) at one k. Returns the metrics dict."""
    train = defaultdict(list)
    test = defaultdict(list)
    for r in splits:
        (train if r["split"] == "train" else test)[r["instrument"]].append(r["clip_id"])
    group = {r["clip_id"]: r["source_group"] for r in splits}
    missing = {}
    for c in classes:
        if len(train[c]) < k:
            missing[c] = f"only {len(train[c])} train clips"
        elif not test[c]:
            missing[c] = "no test clips"
    used = [c for c in classes if c not in missing]
    res = {"k": k, "classes": used, "missing": missing, "chance": (1 / len(used) if used else None)}
    if len(used) < 2:
        res["skipped"] = "fewer than two classes can supply k train clips and a test clip"
        return res
    ci = {c: j for j, c in enumerate(used)}
    te_ids = [x for c in used for x in sorted(test[c])]
    yte = np.array([ci[c] for c in used for _ in test[c]])
    Xte = np.stack([emb[x] for x in te_ids])
    correct = np.zeros((draws, len(te_ids)))
    confusion = np.zeros((len(used), len(used)), dtype=int)
    impl_used = None
    for d in range(draws):
        tr_ids, ytr = [], []
        for c in used:
            ids = draw_train(train, c, k, seed, d)
            tr_ids += ids
            ytr += [ci[c]] * k
        if {group[x] for x in tr_ids} & {group[x] for x in te_ids}:
            raise SystemExit("a source group is on both sides of the probe split (leak); stop")
        pred, impl_used = fit_predict(np.stack([emb[x] for x in tr_ids]), np.array(ytr), Xte, len(used), impl)
        correct[d] = pred == yte
        np.add.at(confusion, (yte, pred), 1)
    per = {}
    for c in used:
        sel = yte == ci[c]
        rec = correct[:, sel].mean(1)
        rng = np.random.default_rng([seed, k, _key(c), 7])
        per[c] = {"recall_mean": float(rec.mean()), "recall_sd": (float(rec.std(ddof=1)) if draws > 1 else None),
                  "recall_per_draw": [float(v) for v in rec],
                  "boot95_test_groups": E.cluster_bootstrap(correct[:, sel].mean(0),
                                                            [group[x] for x, s in zip(te_ids, sel) if s], rng, BOOT_REPS),
                  "n_test": int(sel.sum())}
    res.update({"per_class": per, "probe_impl": impl_used, "draws": draws,
                "confusion_summed_over_draws": {"order": used, "matrix": confusion.tolist()}})
    return res


def split_counts(splits):
    out = defaultdict(lambda: {"train_clips": 0, "test_clips": 0, "train_groups": set(), "test_groups": set()})
    for r in splits:
        s = r["split"]
        out[r["instrument"]][f"{s}_clips"] += 1
        out[r["instrument"]][f"{s}_groups"].add(r["source_group"])
    return {c: {"train_clips": v["train_clips"], "test_clips": v["test_clips"],
                "train_source_groups": len(v["train_groups"]), "test_source_groups": len(v["test_groups"])}
            for c, v in sorted(out.items())}


def leakage_flags(probes):
    flags = []
    for name, by_k in probes.items():
        r = by_k.get("1") or {}
        for c, m in (r.get("per_class") or {}).items():
            if m["recall_mean"] >= LEAK_RECALL:
                flags.append(f"{name} k=1 {c}: mean recall {m['recall_mean']:.2f} (suspect leakage or near-duplicates "
                             "across uploaders before reading this)")
    return flags


def evaluate(splits, emb, seed, ks=KS, draws=DRAWS, impl="auto"):
    classes = sorted({r["instrument"] for r in splits})
    sides = defaultdict(set)
    for r in splits:
        sides[r["source_group"]].add(r["split"])
    leaks = sorted(g for g, s in sides.items() if len(s) > 1)
    if leaks:
        raise SystemExit(f"source groups on both sides of the split: {leaks[:5]}")
    probes = {"joint": classes, **family_probes(classes)}
    out = {name: {str(k): run_probe(cl, k, splits, emb, seed, draws, impl) for k in ks} for name, cl in probes.items()}
    return {"probes": {n: {"classes": cl} for n, cl in probes.items()}, "results": out,
            "split_counts": split_counts(splits), "leakage_flags": leakage_flags(out)}


def render(metrics):
    lines = []
    ins = C.instruments()
    for name, by_k in metrics["results"].items():
        lines += [f"### {name}", "", "| instrument | " + " | ".join(f"k={k}" for k in by_k) + " |",
                  "|---|" + "---|" * len(by_k)]
        classes = metrics["probes"][name]["classes"]
        for trad in E.TRADITION_ORDER:
            for c in [c for c in classes if ins[c]["group"] == trad]:
                cells = []
                for r in by_k.values():
                    m = (r.get("per_class") or {}).get(c)
                    cells.append(f"{m['recall_mean']:.2f} +/- {m['recall_sd']:.2f}" if m and m["recall_sd"] is not None
                                 else (f"{m['recall_mean']:.2f}" if m else "missing"))
                lines.append(f"| {c} ({trad}) | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def run(model, features=None, dry_run=False, allow_dirty=False, impl="sklearn"):
    warnings = E.require_gates()
    prov = E.dataset_commit()
    if prov["dataset_dirty"] and not allow_dirty:
        raise SystemExit("manifest/label/split files have uncommitted changes; commit them first (or --allow-dirty)")
    splits = C.read_csv(C.p("splits"))
    usable = E.usable_labels()
    stale = [r["clip_id"] for r in splits if usable.get(r["clip_id"]) != r["instrument"]]
    if stale or set(usable) - {r["clip_id"] for r in splits}:
        raise SystemExit("data/splits.csv does not match the current usable labels; rerun scripts/make_splits.py")
    ids = [r["clip_id"] for r in splits]
    fdir = F.find_features_dir(model, features)
    meta, _, X, _ = F.load_features(fdir, ids)
    emb = dict(zip(ids, X))
    seed = C.cfg("pipeline")["seed"]
    metrics = evaluate(splits, emb, seed, impl=impl)
    for f in metrics["leakage_flags"]:
        print("LEAKAGE CHECK:", f)
    print(render(metrics))
    payload = {"experiment": "test2_probe", "model": model, "checkpoint_sha256": meta["checkpoint_sha256"],
               "checkpoint_name": meta["checkpoint_name"], "seed": seed, **prov,
               "dataset_files_sha256": E.file_hashes(), "split_file": "data/splits.csv",
               "created_at": E.now(), "n_clips": len(ids), "features_meta": meta, "gate_warnings": warnings,
               "settings": {"ks": list(KS), "draws": DRAWS, "C": PROBE_C, "standardize": "train k-shot set only",
                            "bootstrap_reps": BOOT_REPS, "class_of_clip": "human label from data/splits.csv",
                            "missing_rule": "class with < k train clips or no test clip is left out at that k",
                            "leak_flag_threshold_k1": LEAK_RECALL},
               "metrics": metrics}
    return E.write_result("test2", model, payload, dry_run)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=E.MODELS)
    ap.add_argument("--features")
    ap.add_argument("--probe-impl", default="sklearn", choices=["sklearn", "numpy"],
                    help="real runs use scikit-learn; numpy is the dependency-free path the tests exercise")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    run(a.model, a.features, a.dry_run, a.allow_dirty, a.probe_impl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
