"""HUMAN TOOL. Re-listen to clips that a label-guide exclusion may cover, and reject the ones it does.

Run from the repo root, in a terminal (it plays audio):
  python3 scripts/proposed/relabel_excluded.py --reason "bowed sitar" sitar_wc88877956_0 sitar_wc105114161_0

For each clip it plays the audio and asks you. Only the pass-1 row of a clip you confirm changes:
label=reject, solo=n, confident=n, note="excluded by label guide: <reason> (relabeled <date>)".
Pass-2 rows stay as labeled (self-agreement describes the labeling as it was done).
Before writing, the current labels file is copied to labels/labels_before_relabel_<timestamp>.csv.
"""
import argparse, csv, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common as C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reason", required=True)
    ap.add_argument("clip_ids", nargs="+")
    a = ap.parse_args()
    f = C.p("labels")
    rows = C.read_csv(f)
    clips = {r["clip_id"]: r for r in C.read_csv(C.p("clips"))}
    p1 = {r["clip_id"]: r for r in rows if r["pass"] == "1"}
    missing = [c for c in a.clip_ids if c not in p1 or c not in clips]
    if missing:
        sys.exit(f"no pass-1 label or clip for {missing}")
    play = ["afplay"] if shutil.which("afplay") else ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
    yes = []
    for c in a.clip_ids:
        print(f"\n{c}: current pass-1 label {p1[c]['label']!r}")
        proc = subprocess.Popen(play + [str(C.root() / clips[c]["path"])])
        while True:
            ans = input(f"  Does the exclusion '{a.reason}' apply? y=reject  n=keep  r=replay > ").strip().lower()
            if ans == "r":
                proc.terminate()
                proc = subprocess.Popen(play + [str(C.root() / clips[c]["path"])])
            elif ans in ("y", "n"):
                break
        proc.terminate()
        if ans == "y":
            yes.append(c)
    if not yes:
        print("No change.")
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f.parent / f"labels_before_relabel_{stamp}.csv"
    shutil.copy2(f, backup)
    for r in rows:
        if r["pass"] == "1" and r["clip_id"] in yes:
            r.update(label="reject", solo="n", confident="n",
                     note=f"excluded by label guide: {a.reason} (relabeled {stamp[:8]})")
    with open(f, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=C.schema("labels"))
        w.writeheader()
        w.writerows(rows)
    print(f"Rejected {len(yes)} clip(s): {yes}. Backup: {backup}")


if __name__ == "__main__":
    main()
