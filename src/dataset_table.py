#!/usr/bin/env python3
"""Dataset table: per instrument, usable clips, source groups, split sizes, licenses, sources, padding.

  .venv/bin/python src/dataset_table.py

A clip's instrument is the human pass-1 label (solo, confident), as in make_splits.py and Test 2.
Reads data/clips_manifest.csv, labels (through validate.usable_clips), data/splits.csv and
data/approved.csv. Writes results/dataset/dataset_table.csv and .md. Never pools "non-Western".
"""
import csv, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from eval_common import C  # noqa: E402
import eval_common as E  # noqa: E402
import validate  # noqa: E402

LICENSES = ["cc0", "pd", "by", "by-nc"]
SOURCES = ["freesound", "commons"]


def build():
    ins = C.instruments()
    clips = {r["clip_id"]: r for r in C.read_csv(C.p("clips"))}
    usable = validate.usable_clips()
    split = {r["clip_id"]: r["split"] for r in C.read_csv(C.p("splits"))}
    cut = Counter(r["instrument"] for r in clips.values())
    rows = []
    by = defaultdict(list)
    for c, lab in usable.items():
        by[lab].append(clips[c])
    for i, meta in ins.items():
        cs = by.get(i, [])
        lic = Counter(r["license_code"] for r in cs)
        src = Counter("freesound" if r["candidate_id"].startswith("fs:") else "commons" for r in cs)
        other = sorted(set(lic) - set(LICENSES))
        rows.append({
            "instrument": i, "tradition": meta["group"], "role": meta["role"], "family": meta["family"],
            "cousin": meta["cousin"] or "", "clips_cut": cut[i], "usable": len(cs),
            "source_groups": len({r["source_group"] for r in cs}),
            "usable_cut_as_other": sum(1 for r in cs if r["instrument"] != i),
            "train": sum(1 for r in cs if split.get(r["clip_id"]) == "train"),
            "test": sum(1 for r in cs if split.get(r["clip_id"]) == "test"),
            **{f"lic_{k}": lic.get(k, 0) for k in LICENSES},
            "lic_other": ";".join(f"{k}:{lic[k]}" for k in other),
            **{f"src_{k}": src.get(k, 0) for k in SOURCES},
            "padded": sum(1 for r in cs if float(r["content_s"]) < 9.995),
            "meets_min_20": len(cs) >= C.cfg("pipeline")["min_clips_per_instrument"],
        })
    return rows


def render(rows):
    head = ("| instrument | usable (cut) | source groups | train / test | CC0 | PD | CC BY | CC BY-NC | Freesound / Commons | padded |\n"
            "|---|---|---|---|---|---|---|---|---|---|")
    out = [head]
    for trad in E.TRADITION_ORDER:
        rs = [r for r in rows if r["tradition"] == trad]
        if not rs:
            continue
        out.append(f"| **{trad}** | | | | | | | | | |")
        for r in rs:
            flag = "" if r["meets_min_20"] else " *"
            out.append(f"| {r['instrument']}{flag} | {r['usable']} ({r['clips_cut']}) | {r['source_groups']} | "
                       f"{r['train']} / {r['test']} | {r['lic_cc0']} | {r['lic_pd']} | {r['lic_by']} | {r['lic_by-nc']} | "
                       f"{r['src_freesound']} / {r['src_commons']} | {r['padded']} |")
    tot = {k: sum(r[k] for r in rows) for k in ("usable", "clips_cut", "lic_cc0", "lic_pd", "lic_by", "lic_by-nc",
                                                 "src_freesound", "src_commons", "padded")}
    out.append(f"| all 18 classes | {tot['usable']} ({tot['clips_cut']}) | | | {tot['lic_cc0']} | {tot['lic_pd']} | {tot['lic_by']} | "
               f"{tot['lic_by-nc']} | {tot['src_freesound']} / {tot['src_commons']} | {tot['padded']} |")
    out.append("")
    out.append("usable = human label, solo, confident (a clip counts for the instrument heard, not the one searched); "
               "cut = clips cut from recordings found under that instrument; * below 20 usable clips.")
    return "\n".join(out)


def main():
    rows = build()
    d = C.root() / "results" / "dataset"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "dataset_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = render(rows)
    (d / "dataset_table.md").write_text(md + "\n", encoding="utf-8")
    print(md)
    other = [r for r in rows if r["lic_other"]]
    if other:
        print("WARNING: licenses outside CC0/PD/BY/BY-NC:", [(r["instrument"], r["lic_other"]) for r in other])


if __name__ == "__main__":
    main()
