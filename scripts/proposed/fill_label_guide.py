"""Human-run edit: fill the Exclude column of docs/label_guide.md for 8 target instruments and record
three open decisions.

Run from the repo root:  python3 scripts/proposed/fill_label_guide.py

These are PROPOSALS written by Claude. The guide must describe the rules you applied by ear while
labeling. Before running, edit any text below that does not match what you did. Each replacement must
hit exactly once, or the script stops and changes nothing.
"""
from pathlib import Path

p = Path("docs/label_guide.md")
s = p.read_text(encoding="utf-8")

EXCLUDE = {  # row number and instrument -> Exclude column text
    (2, "pipa"): "other Chinese lutes (liuqin, ruan, yueqin, sanxian); Japanese biwa",
    (3, "dizi"): "end-blown xiao; free-reed bawu and hulusi; Western concert flute",
    (4, "guzheng"): "guqin (no bridges); Japanese koto; Korean gayageum; Vietnamese dan tranh",
    (6, "quena"): "quenacho (larger, lower); pinkillo and other duct flutes; ney",
    (7, "siku"): "non-Andean panpipes (Romanian nai, Western pan flute); ensembles of more than one player are solo = n",
    (9, "oud"): "European lute; baglama/saz and other long-necked lutes; cumbus",
    (10, "ney"): "kaval; shakuhachi; quena; Western flute",
    (11, "qanun"): "santur, cimbalom and other hammered zithers; guzheng and other East Asian zithers; harp",
}

DECISIONS = {  # open question line -> decided line
    "- Which ney variants count (Turkish, Arab, Persian)?":
        "- **ney variants (decided 2026-11-19):** Turkish, Arab and Persian ney all count as ney. They are the "
        "same rim-blown cane flute; playing technique differs, so variant is noted in the clip note when audible.",
    "- Is a zampoña ensemble 'solo' siku? (Proposed: no, unless one player.)":
        "- **siku ensembles (decided 2026-11-19):** a zampoña ensemble is not solo (solo = n) unless one player "
        "is heard. Antara (single-row panpipe) counts as siku.",
    "- Is an erhu with light reverb acceptable? (Proposed: yes; reject heavy effects.)":
        "- **reverb (decided 2026-11-19):** light reverb is acceptable for every instrument; heavy effects are "
        "rejected (x).",
}

lines = s.split("\n")
for (num, name), text in EXCLUDE.items():
    hits = [k for k, ln in enumerate(lines) if ln.startswith(f"| {num} | {name} |")]
    if len(hits) != 1 or lines[hits[0]].count("| TODO |") != 1:
        raise SystemExit(f"{name}: expected one row with one TODO cell; nothing written")
    lines[hits[0]] = lines[hits[0]].replace("| TODO |", f"| {text} |", 1)
s = "\n".join(lines)
for old, new in DECISIONS.items():
    if s.count(old) != 1:
        raise SystemExit(f"open question not found exactly once: {old!r}; nothing written")
    s = s.replace(old, new)

p.write_text(s, encoding="utf-8")
print("filled Exclude for:", ", ".join(n for _, n in EXCLUDE), "| recorded 3 decisions")
print("still TODO:", sum(ln.count("| TODO |") for ln in s.split("\n")), "cells (controls and cousins rows, darbuka)")
