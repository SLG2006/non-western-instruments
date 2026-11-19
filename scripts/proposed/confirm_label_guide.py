"""Human-run edit of docs/label_guide.md (decisions of 2026-11-19).

Run from the repo root:  python3 scripts/proposed/confirm_label_guide.py

1. Confirms the 8 proposed exclusion cells (removes the "proposed, unconfirmed" marker).
2. Adds bowed sitar to the sitar exclusions, with the decision.
3. Rewords the ney and siku decisions to match Wikipedia ("Ney" and "Siku", checked 2026-11-19):
   the ney is an end-blown flute; antara is the Quechua name for the siku.
Every replacement must match exactly once (the snare marker and the 8 cells as counted), or nothing is written.
"""
from pathlib import Path

p = Path("docs/label_guide.md")
t = p.read_text(encoding="utf-8")

edits = [
    # sitar row first, while its marker is still there
    ("electric sitar (proposed 2026-11-19, unconfirmed) |  |",
     "electric sitar; bowed sitar | Bowed sitar does not count (decided 2026-11-19). |", 1),
    (" (proposed 2026-11-19, unconfirmed)", "", 7),
    ("Proposed Western drum cousin. Confirm.", "Western drum cousin (decided 2026-11-19).", 1),
    ("siku, zampoña, zampona, antara panpipe, andean panpipe", "siku, zampoña, zampona, antara, andean panpipe", 1),
    ("They are the same rim-blown cane flute; playing technique differs, so variant is noted in the clip note when audible.",
     "All are end-blown flutes (Wikipedia, \"Ney\", checked 2026-11-19); playing technique differs, so the variant is "
     "noted in the clip note when audible.", 1),
    ("Antara (single-row panpipe) counts as siku.",
     "Antara is the Quechua name for the siku (Wikipedia, \"Siku\", checked 2026-11-19) and counts as siku.", 1),
]
for old, new, n in edits:
    found = t.count(old)
    if found != n:
        raise SystemExit(f"expected {n} match(es), found {found}: {old[:60]!r}. Nothing written.")
    t = t.replace(old, new)
assert "unconfirmed" not in t and "rim-blown" not in t
p.write_text(t, encoding="utf-8")
print(f"updated {p}: 8 cells confirmed, bowed sitar excluded, ney and siku decisions reworded")
