#!/usr/bin/env python3
"""Test 1: frozen models out of the box, scored per instrument.

  .venv/bin/python src/test1.py check-config --class-labels <csv> --ontology <ontology.json>
  .venv/bin/python src/test1.py run --model beats --class-labels <csv> --ontology <ontology.json> [--dry-run]

A clip's class is its human pass-1 label (usable rule of scripts/validate.py), not the batch it was cut
under. For each instrument: (a) most common top-1 label and its share; (b) family hit in top-k, where a
hit is any family node from config/instruments.json or any ontology descendant of it, at k=5 and at k=1
(top-ranked class only); (c) exact label in
top-k where audioset_exact is set; (d) broad-label hit for tier-2 instruments (proposed mapping below).
Primary table ranks instrument nodes only; the unfiltered 527-way ranking is the secondary table.
Proportions get Wilson 95% intervals and a cluster bootstrap over source groups. No pooled
"non-Western" number is computed.
"""
import argparse, sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_common as E  # noqa: E402
from eval_common import C  # noqa: E402
import features as F  # noqa: E402

# PROPOSED, for the human to move into config/ (agents cannot edit config/).
# Instrument-node filter: keep only strict descendants of this ontology node. That removes "Music",
# "Musical instrument" itself, genres, moods, and every non-music class. The full kept list is written
# into each results file under metrics.instrument_nodes so it can be reviewed.
PROPOSED_INSTRUMENT_ROOT = "Musical instrument"
# Labels removed even though they sit under the root (exact AudioSet display names; checked at run time,
# an unknown name stops the run). Empty until the human reviews metrics.instrument_nodes.
PROPOSED_EXCLUDED_INSTRUMENT_NODES = ()
# Tier-2 broad labels (CLAUDE.md section 9 item 6). config/instruments.json has no field for these.
PROPOSED_BROAD_LABELS = {"guzheng": "Zither", "qanun": "Zither", "darbuka": "Drum", "bombo": "Bass drum"}

TOP_K = 5
PADDED_BELOW = 9.995  # content_s below this means the clip was zero-padded to 10 s (same cut as n_padded)
BOOT_REPS = 2000


def instrument_mask(classes, onto, root=PROPOSED_INSTRUMENT_ROOT, excluded=PROPOSED_EXCLUDED_INSTRUMENT_NODES):
    names = {n for _, n in classes}
    bad = [x for x in excluded if x not in names]
    if bad:
        raise SystemExit(f"excluded instrument nodes not in the class list: {bad}")
    keep = onto.descendants(onto.id_of(root), include_self=False)
    return np.array([m in keep and n not in excluded for m, n in classes])


def check_config(classes, onto):
    """Every audioset_exact / audioset_family / broad string vs. the class list and ontology."""
    names = {n for _, n in classes}
    out = []
    for i in C.cfg("instruments")["instruments"]:
        for kind, vals in (("exact", [i["audioset_exact"]] if i["audioset_exact"] else []),
                           ("family", i["audioset_family"]),
                           ("broad (proposed)", [PROPOSED_BROAD_LABELS[i["id"]]] if i["id"] in PROPOSED_BROAD_LABELS else [])):
            for v in vals:
                in_cls = v in names
                in_onto = bool(onto.by_name.get(v))
                out.append({"instrument": i["id"], "kind": kind, "label": v, "in_class_list": in_cls,
                            "in_ontology": in_onto,
                            "ok": in_cls if kind != "family" else in_onto})
    return out


def rank(probs, mask, k):
    """Indices of the top-k classes among mask=True, highest first (ties: lower index first)."""
    p = np.where(mask, probs, -np.inf)
    order = np.argsort(-p, kind="stable")
    return [int(j) for j in order[:k] if mask[j]]


def _share(hits, groups, rng):
    n, k = len(hits), int(sum(hits))
    return {"hits": k, "n": n, "share": (k / n if n else None), "wilson95": E.wilson(k, n),
            "boot95_groups": E.cluster_bootstrap(hits, groups, rng, BOOT_REPS)}


def score(clip_ids, labels, groups, probs, classes, onto, mask, k=TOP_K, seed=0, content_s=None):
    """Per-instrument metrics for one ranking (mask selects which classes may be ranked)."""
    ins = C.instruments()
    names = [n for _, n in classes]
    mid_idx = {m: j for j, (m, _) in enumerate(classes)}
    name_idx = {n: j for j, n in enumerate(names)}

    def family_set(i):
        s = set()
        for fam in ins[i]["audioset_family"]:
            for m in onto.descendants(onto.id_of(fam)):
                if m in mid_idx:
                    s.add(mid_idx[m])
        return s

    tops = {c: rank(probs[n], mask, k) for n, c in enumerate(clip_ids)}
    by = {}
    for n, c in enumerate(clip_ids):
        by.setdefault(labels[c], []).append(c)
    out = {}
    for i in [x for x in ins if x in by]:
        rng = np.random.default_rng([seed, sorted(ins).index(i)])
        cs = by[i]
        g = [groups[c] for c in cs]
        top1 = Counter(names[tops[c][0]] for c in cs)
        best = max(top1.values())
        modes = sorted(lab for lab, v in top1.items() if v == best)
        fam = family_set(i)
        row = {"tradition": ins[i]["group"], "role": ins[i]["role"], "family": ins[i]["family"],
               "cousin": ins[i]["cousin"], "tier": ins[i]["audioset_tier"], "n": len(cs),
               "n_source_groups": len(set(g)),
               "n_padded": (int(sum(1 for c in cs if content_s[c] < 9.995)) if content_s else None),
               "top1_mode": {"label": modes[0], "ties": modes[1:], "count": best, "share": best / len(cs)},
               "top1_counts": dict(top1.most_common()),
               "family_labels": ins[i]["audioset_family"],
               "family_topk": _share([any(j in fam for j in tops[c]) for c in cs], g, rng)}
        ex = ins[i]["audioset_exact"]
        if ex:
            j = name_idx.get(ex)
            row["exact_label"] = ex
            row["exact_topk"] = (_share([j in tops[c] for c in cs], g, rng) if j is not None
                                 else {"error": f"{ex!r} not in class list"})
        br = PROPOSED_BROAD_LABELS.get(i)
        if br:
            j = name_idx.get(br)
            row["broad_label"] = br
            row["broad_topk"] = (_share([j in tops[c] for c in cs], g, rng) if j is not None
                                 else {"error": f"{br!r} not in class list"})
        # family@1: the top-ranked class is a family node or a descendant. Computed last so the
        # bootstrap draws for the metrics above are unchanged from earlier runs.
        row["family_top1"] = _share([bool(tops[c]) and tops[c][0] in fam for c in cs], g, rng)
        out[i] = row
    per_clip = {c: [names[j] for j in tops[c]] for c in clip_ids}
    return out, per_clip


def _fmt(m):
    """Share, hits/n and the Wilson 95% interval (the cluster bootstrap stays in the JSON)."""
    if not m or "share" not in m:
        return "-"
    lo, hi = m["wilson95"]
    return f"{m['share']:.2f} ({m['hits']}/{m['n']}; {lo:.2f}-{hi:.2f})"


def render(table, title):
    """Markdown, grouped by tradition, controls and cousins in their own blocks; cousin family share alongside."""
    lines = [f"### {title}", "", "| instrument | n | groups | top-1 (share) | family@1 | family@k | exact@k | broad@k | cousin | cousin family@1 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for trad in E.TRADITION_ORDER:
        rows = [(i, r) for i, r in table.items() if r["tradition"] == trad]
        if not rows:
            continue
        lines.append(f"| **{trad}** | | | | | | | | | |")
        for i, r in rows:
            cz = table.get(r["cousin"]) if r["cousin"] else None
            lines.append(f"| {i} | {r['n']} | {r['n_source_groups']} | {r['top1_mode']['label']} "
                         f"({r['top1_mode']['share']:.2f}) | {_fmt(r['family_top1'])} | {_fmt(r['family_topk'])} | "
                         f"{_fmt(r.get('exact_topk'))} | {_fmt(r.get('broad_topk'))} | {r['cousin'] or '-'} | "
                         f"{_fmt(cz['family_top1']) if cz else '-'} |")
    return "\n".join(lines)


def run(model, class_labels, ontology, features=None, dry_run=False, allow_dirty=False, exclude_padded=False):
    warnings = E.require_gates()
    prov = E.dataset_commit()
    if prov["dataset_dirty"] and not allow_dirty:
        raise SystemExit("manifest/label/split files have uncommitted changes; commit them first (or --allow-dirty)")
    classes = E.load_classes(class_labels)
    onto = E.Ontology(ontology)
    cfg_check = check_config(classes, onto)
    bad = [r for r in cfg_check if not r["ok"]]
    if bad:
        raise SystemExit("AudioSet label strings not found; report to the human:\n  " +
                         "\n  ".join(f"{b['instrument']} {b['kind']}: {b['label']!r}" for b in bad))
    labels = E.usable_labels()
    man = E.manifest()
    clip_ids = sorted(labels)
    fdir = F.find_features_dir(model, features)
    meta, probs, _, cs = F.load_features(fdir, clip_ids)
    if meta["class_labels_sha256"] != E.sha256_file(class_labels):
        raise SystemExit("features were computed with a different class_labels_indices.csv")
    content = dict(zip(clip_ids, cs.tolist()))
    n_padded_dropped = 0
    if exclude_padded:  # sensitivity run: only clips with a full 10 s of source audio
        keep = np.array([content[c] >= PADDED_BELOW for c in clip_ids])
        n_padded_dropped = int((~keep).sum())
        clip_ids = [c for c, k in zip(clip_ids, keep) if k]
        probs = probs[keep]
        labels = {c: labels[c] for c in clip_ids}
    groups = {c: man[c]["source_group"] for c in clip_ids}
    seed = C.cfg("pipeline")["seed"]
    imask = instrument_mask(classes, onto)
    full = np.ones(len(classes), dtype=bool)
    t_ins, pc_ins = score(clip_ids, labels, groups, probs, classes, onto, imask, TOP_K, seed, content)
    t_all, pc_all = score(clip_ids, labels, groups, probs, classes, onto, full, TOP_K, seed, content)
    payload = {
        "experiment": "test1_zero_shot_unpadded" if exclude_padded else "test1_zero_shot", "model": model, "checkpoint_sha256": meta["checkpoint_sha256"],
        "checkpoint_name": meta["checkpoint_name"], "seed": seed, **prov, "dataset_files_sha256": E.file_hashes(),
        "created_at": E.now(), "n_clips": len(clip_ids), "features_meta": meta,
        "class_labels_sha256": E.sha256_file(class_labels), "ontology_sha256": E.sha256_file(ontology),
        "settings": {"top_k": TOP_K, "bootstrap_reps": BOOT_REPS, "ci": "Wilson 95% and percentile cluster bootstrap over source_group",
                     "class_of_clip": "human pass-1 label, usable rule of scripts/validate.py:usable_clips",
                     "family_hit": "any audioset_family node or ontology descendant in top-k",
                     "family_top1": "the top-ranked class is an audioset_family node or ontology descendant",
                     "instrument_root": PROPOSED_INSTRUMENT_ROOT,
                     "excluded_instrument_nodes": list(PROPOSED_EXCLUDED_INSTRUMENT_NODES),
                     "broad_labels": PROPOSED_BROAD_LABELS,
                     "exclude_padded": exclude_padded, "padded_below_s": PADDED_BELOW,
                     "n_padded_dropped": n_padded_dropped},
        "gate_warnings": warnings, "config_label_check": cfg_check,
        "metrics": {"instrument_nodes": [n for (m, n), keep in zip(classes, imask) if keep],
                    "primary_instrument_nodes_only": t_ins, "secondary_unfiltered": t_all},
        "per_clip": {c: {"label": labels[c], "source_group": groups[c], "content_s": content[c],
                         "topk_instrument_nodes": pc_ins[c], "topk_unfiltered": pc_all[c]} for c in clip_ids},
    }
    print(render(t_ins, f"{model}: top-{TOP_K} over instrument nodes (primary)"))
    print()
    print(render(t_all, f"{model}: top-{TOP_K} over all 527 classes (secondary)"))
    return E.write_result("test1_unpadded" if exclude_padded else "test1", model, payload, dry_run)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check-config", "run"])
    ap.add_argument("--model", choices=E.MODELS)
    ap.add_argument("--class-labels", required=True)
    ap.add_argument("--ontology", required=True)
    ap.add_argument("--features", help="features directory (default: the only one under data/features/<model>/)")
    ap.add_argument("--exclude-padded", action="store_true",
                    help="sensitivity run: drop clips zero-padded to 10 s (content_s below 9.995 s)")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.command == "check-config":
        rows = check_config(E.load_classes(a.class_labels), E.Ontology(a.ontology))
        for r in rows:
            print(f"{'ok ' if r['ok'] else 'BAD'} {r['instrument']:16s} {r['kind']:17s} {r['label']!r} "
                  f"class_list={r['in_class_list']} ontology={r['in_ontology']}")
        return 0 if all(r["ok"] for r in rows) else 1
    if not a.model:
        ap.error("--model is required for run")
    run(a.model, a.class_labels, a.ontology, a.features, a.dry_run, a.allow_dirty, a.exclude_padded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
