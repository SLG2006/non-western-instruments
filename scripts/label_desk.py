#!/usr/bin/env python3
"""Stage 4 (label-desk): build the listening queue and compute self-agreement.

  python3 scripts/label_desk.py queue        # pass 1 for unlabeled clips; pass 2 once pass 1 is complete
  python3 scripts/label_desk.py next         # pass 1 for the next listening group with unlabeled clips
  python3 scripts/label_desk.py groups       # progress per listening group
  python3 scripts/label_desk.py agreement    # writes labels/agreement.json and labels/summary.json

This script never writes labels/labels.csv. Only the human does, through
scripts/label_tool.py. The queue is blind: it carries no instrument name.
"""
import json, random, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


# Listening groups (author's choice, 2026-11-16): at most three similar instruments per queue, so the
# labeler compares like with like. Groups are by the batch a clip was cut under; the label is still what
# is heard, so a quena cut under dizi is labeled quena. Order follows the collection priority.
GROUPS = [
    ["erhu", "violin"],                 # bowed strings (done first)
    ["oud", "pipa", "sitar"],           # plucked lutes, Asian and Middle Eastern
    ["charango", "acoustic_guitar"],    # small Andean lute vs. guitar
    ["dizi", "flute"],                  # transverse flutes
    ["ney", "quena", "siku"],           # end-blown flutes and panpipe
    ["guzheng", "qanun"],               # plucked zithers
    ["darbuka", "tabla"],               # hand drums
    ["snare_drum", "bombo"],            # stick-played drums
]


def _status():
    clips = C.read_csv(C.p("clips"))
    labels = C.read_csv(C.p("labels"))
    p1 = {r["clip_id"] for r in labels if r["pass"] == "1"}
    return clips, labels, p1


def groups():
    clips, _, p1 = _status()
    for g in GROUPS:
        cs = [c for c in clips if c["instrument"] in g]
        done = sum(c["clip_id"] in p1 for c in cs)
        print(f"  {' + '.join(g):32s} {done:4d}/{len(cs):<4d} labeled")
    other = sorted({c["instrument"] for c in clips} - {i for g in GROUPS for i in g})
    if other:
        print("  not in any group:", ", ".join(other))


def next_group():
    clips, _, p1 = _status()
    for g in GROUPS:
        if any(c["instrument"] in g and c["clip_id"] not in p1 for c in clips):
            return queue(g)
    return queue()


def queue(only=None):
    pc = C.cfg("pipeline")
    clips, labels, p1 = _status()
    p2 = {r["clip_id"] for r in labels if r["pass"] == "2"}
    rng = random.Random(pc["seed"])
    todo = [c for c in clips if c["clip_id"] not in p1 and (only is None or c["instrument"] in only)]
    rng.shuffle(todo)
    rows = [{"clip_id": c["clip_id"], "path": c["path"], "pass": "1"} for c in todo]
    if only is not None:
        C.write_csv(C.p("queue"), rows, C.schema("queue"))
        print(f"queue: {len(rows)} clips to label (pass 1), group: {' + '.join(only)}; "
              f"{len(p1)}/{len(clips)} clips have a pass-1 label overall")
        return
    if clips and not [c for c in clips if c["clip_id"] not in p1]:
        # Blind re-label sample: fixed by the seed, so it cannot be cherry-picked.
        pool = sorted(c["clip_id"] for c in clips)
        random.Random(pc["seed"] + 1).shuffle(pool)
        sample = pool[: max(1, round(len(pool) * pc["relabel_fraction"]))]
        path = {c["clip_id"]: c["path"] for c in clips}
        again = [s for s in sample if s not in p2]
        rng.shuffle(again)
        rows = [{"clip_id": s, "path": path[s], "pass": "2"} for s in again]
    C.write_csv(C.p("queue"), rows, C.schema("queue"))
    print(f"queue: {len(rows)} clips to label (pass {rows[0]['pass'] if rows else '-'}); "
          f"{len(p1)}/{len(clips)} have a pass-1 label")


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None, None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return po, (1.0 if pe == 1 else (po - pe) / (1 - pe))


def agreement():
    labels = C.read_csv(C.p("labels"))
    one = {r["clip_id"]: r for r in labels if r["pass"] == "1"}
    two = {r["clip_id"]: r for r in labels if r["pass"] == "2"}
    pairs = [(one[c]["label"], two[c]["label"]) for c in sorted(two) if c in one]
    po, k = kappa(pairs)
    out = {"n_relabelled": len(pairs), "raw_agreement": po, "cohens_kappa": k,
           "disagreements": [{"clip_id": c, "pass1": one[c]["label"], "pass2": two[c]["label"]}
                             for c in sorted(two) if c in one and one[c]["label"] != two[c]["label"]]}
    (C.root() / "labels" / "agreement.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    extras = set(C.cfg("instruments")["label_extras"])
    clips = {r["clip_id"]: r for r in C.read_csv(C.p("clips"))}
    usable, groups, dropped = Counter(), {}, Counter()
    for c, r in one.items():
        if r["label"] in extras or r["solo"] != "y" or r["confident"] != "y":
            dropped[r["label"] if r["label"] in extras else ("not_solo" if r["solo"] != "y" else "not_confident")] += 1
            continue
        usable[r["label"]] += 1
        groups.setdefault(r["label"], set()).add(clips.get(c, {}).get("source_group", "?"))
    pc = C.cfg("pipeline")
    summary = {"labelled_pass1": len(one), "total_clips": len(clips), "dropped": dict(dropped),
               "usable": {i: {"clips": usable[i], "source_groups": len(groups.get(i, ())),
                              "meets_minimum": usable[i] >= pc["min_clips_per_instrument"]}
                          for i in C.instruments()}}
    (C.root() / "labels" / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"self-agreement: n={len(pairs)} raw={po} kappa={k}")
    for i, s in summary["usable"].items():
        print(f"  {i:16s} {s['clips']:3d} usable clips, {s['source_groups']} source groups"
              f"{'' if s['meets_minimum'] else '   <-- below minimum'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"queue": queue, "next": next_group, "groups": groups, "agreement": agreement}.get(cmd, lambda: sys.exit(__doc__))()
