#!/usr/bin/env python3
"""HUMAN TOOL. Run it yourself in a terminal; agents must never run it.

  python3 scripts/label_tool.py            # blind: you hear the clip, see nothing about it
  python3 scripts/label_tool.py --show-title   # pass 1 only: also show the uploader's title (anchors your judgment)

Plays each clip in labels/queue.csv and appends your answer to labels/labels.csv
immediately, so you can quit (q) at any time and resume later.
"""
import argparse, csv, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def player():
    if shutil.which("afplay"):
        return ["afplay"]
    if shutil.which("ffplay"):
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
    sys.exit("No audio player found (need afplay on macOS, or ffplay).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-title", action="store_true")
    a = ap.parse_args()
    cfg = C.cfg("instruments")
    keys = [i["id"] for i in cfg["instruments"]]
    menu = "  ".join(f"{n + 1}={k}" for n, k in enumerate(keys))
    done = {(r["clip_id"], r["pass"]) for r in C.read_csv(C.p("labels"))}
    todo = [r for r in C.read_csv(C.p("queue")) if (r["clip_id"], r["pass"]) not in done]
    if not todo:
        print("Nothing to label. Ask the label-desk agent to rebuild the queue.")
        return
    titles = {}
    if a.show_title:
        cand = {r["candidate_id"]: r["title"] for r in C.read_csv(C.p("approved"))}
        titles = {r["clip_id"]: cand.get(r["candidate_id"], "") for r in C.read_csv(C.p("clips"))}
    out = C.p("labels")
    new = not out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    play = player()
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=C.schema("labels"))
        if new:
            w.writeheader()
        for n, r in enumerate(todo, start=1):
            print(f"\n[{n}/{len(todo)}] pass {r['pass']}" +
                  (f"   title: {titles.get(r['clip_id'], '')}" if a.show_title and r["pass"] == "1" else ""))
            proc = subprocess.Popen(play + [str(C.root() / r["path"])])
            label = None
            while label is None:
                ans = input(f"{menu}\n  x=reject  u=unsure  r=replay  q=quit > ").strip().lower()
                if ans == "q":
                    proc.terminate()
                    return
                if ans == "r":
                    proc.terminate()
                    proc = subprocess.Popen(play + [str(C.root() / r["path"])])
                elif ans == "x":
                    label = "reject"
                elif ans == "u":
                    label = "unsure"
                elif ans.isdigit() and 1 <= int(ans) <= len(keys):
                    label = keys[int(ans) - 1]
                elif ans in keys:
                    label = ans
            solo = confident = "n"
            note = ""
            if label not in ("reject", "unsure"):
                solo = "n" if input("  solo instrument only? [Y/n] ").strip().lower() == "n" else "y"
                confident = "n" if input("  confident? [Y/n] ").strip().lower() == "n" else "y"
            else:
                note = input("  note (optional): ").strip()
            proc.terminate()
            w.writerow({"clip_id": r["clip_id"], "pass": r["pass"], "label": label, "solo": solo,
                        "confident": confident, "note": note,
                        "labeled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
            f.flush()
    print("Queue finished.")


if __name__ == "__main__":
    main()
