"""Human-run edit of the parent CLAUDE.md (../CLAUDE.md, outside the repo): mark §9.7 resolved and update
the week statuses in §5.

Run from the repo root:  python3 scripts/proposed/update_claude_md.py

Each replacement must hit exactly once, or the script stops and changes nothing. Week 1 item 2 (IRMAS
sanity check) is marked as not recorded: no IRMAS run exists in this repo. Change it if you ran it.
"""
from pathlib import Path

p = Path("../CLAUDE.md")
s = p.read_text(encoding="utf-8")

EDITS = [
    ("Last updated: Thursday, October 1, 2026 (Week 2 of the fall plan).",
     "Last updated: Thursday, November 19, 2026 (Week 9 of the fall plan)."),
    ("### Week 1 (Sep 21–27): Setup and source count ❓",
     "### Week 1 (Sep 21–27): Setup and source count ✅ (IRMAS sanity check: not recorded in the repo)"),
    ("### Week 2 (Sep 28–Oct 4): Rules before collecting 🔄 (current week)",
     "### Week 2 (Sep 28–Oct 4): Rules before collecting ✅ (Freesound previews, preview-hq-ogg, used for every class instead of OAuth originals)"),
    ("### Weeks 3–6 (Oct 5–Nov 1): Collect and label ⬜",
     "### Weeks 3–6 (Oct 5–Nov 1): Collect and label ✅ (done Nov 16–18: 806 clips cut, all labeled, 434 usable)"),
    ("### Week 7 (Nov 2–8): Freeze the dataset ⬜",
     "### Week 7 (Nov 2–8): Freeze the dataset ✅ (relabel n = 92, kappa 0.65; uploader-disjoint splits; extension file and datasheet drafted)"),
    ("### Week 8 (Nov 9–15): Test 1, models out of the box ⬜",
     "### Week 8 (Nov 9–15): Test 1, models out of the box ✅ (run Nov 19, both models; family@1 added)"),
    ("### Week 9 (Nov 16–22): Test 2, do a few examples help? ⬜",
     "### Week 9 (Nov 16–22): Test 2, do a few examples help? ✅ (fixed 11-class set, k = 1, 5, 10)"),
    ("### Week 10 (Nov 23–29, Thanksgiving): Analysis, report, hand-off ⬜",
     "### Week 10 (Nov 23–29, Thanksgiving): Analysis, report, hand-off 🔄 (current week; table, chart, notes ready)"),
    ("7. **BEATs headline number.** The lab-presentation slide says 50.6 mAP on AudioSet-2M. [U] That may be an "
     "ensemble figure rather than a single checkpoint. Verify against the BEATs paper/repo before it goes in the "
     "report. Record the exact checkpoint file name in results.",
     "7. **BEATs headline number. RESOLVED 2026-11-19.** [V] unilm/beats README, checked 2026-11-19: "
     "BEATs_iter3+ (AS2M) single model, 48.6 mAP on AudioSet-2M (Table 1, Chen et al., ICML 2023). The 50.6 on "
     "the lab slide is the 10-model ensemble (Table 3); do not cite it for our checkpoint. Checkpoint used: "
     "BEATs_iter3_plus_AS2M_finetuned_on_AS2M_cpt2.pt (sha256 in docs/model_metadata.md). The README does not "
     "score cpt1 and cpt2 separately."),
]

for old, new in EDITS:
    if s.count(old) != 1:
        raise SystemExit(f"not found exactly once: {old[:70]!r}; nothing written")
for old, new in EDITS:
    s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print(f"updated {p.resolve()}: {len(EDITS)} edits")
