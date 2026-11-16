#!/usr/bin/env python3
"""Stage 2 (curator): apply the license whitelist to data/candidates/*.csv.

Writes data/approved.csv, data/flags.csv (needs a human decision) and
data/rejected.csv. Human decisions are read from data/human_decisions.csv
(candidate_id, decision=approve|reject, note), which only the human edits.
Deterministic: running it twice gives the same files.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    lic, pc = C.cfg("licenses"), C.cfg("pipeline")
    human = {r["candidate_id"]: r["decision"].strip().lower() for r in C.read_csv(C.p("human_decisions"))}
    approved, flags, rejected, owner = [], [], [], {}
    d = C.p("candidates_dir")
    for f in sorted(d.glob("*.csv")) if d.exists() else []:
        for r in C.read_csv(f):
            cid, code, dec = r["candidate_id"], r["license_code"], human.get(r["candidate_id"])

            def flag(reason):
                flags.append({**r, "reason": reason})

            def reject(reason):
                rejected.append({"candidate_id": cid, "instrument": r["instrument"], "reason": reason})

            if cid in owner:
                reject(f"already listed under {owner[cid]}")
                continue
            dur = float(r["duration_s"] or 0)
            if dur < pc["min_source_seconds"] or dur > pc["max_source_seconds"]:
                reject("duration out of range")
            elif dec == "reject":
                reject("human decision")
            elif r.get("gen_ai_preference") == "no-gen-ai":
                reject("uploader gen_ai_preference no-gen-ai")
            elif code in lic["reject"]:
                reject(f"license {code}")
            elif not r["uploader"].strip():
                reject("no uploader; cannot assign a source group")
            elif code in lic["accept"] or (code in lic["needs_human"] and dec == "approve"):
                owner[cid] = r["instrument"]
                approved.append({**r, "source_group": f"{r['source']}:{r['uploader'].strip().lower()}",
                                 "decided_by": "human" if dec == "approve" else "rule"})
            elif code in lic["needs_human"]:
                flag(f"license {code} needs a human decision")
            else:
                reject(f"license {code} not recognised")
    key = lambda r: (r["instrument"], r["candidate_id"])
    C.write_csv(C.p("approved"), sorted(approved, key=key), C.schema("approved"))
    C.write_csv(C.p("flags"), sorted(flags, key=key), C.schema("flags"))
    C.write_csv(C.p("rejected"), sorted(rejected, key=key), C.schema("rejected"))
    per = {}
    for r in approved:
        s = per.setdefault(r["instrument"], [0, set()])
        s[0] += 1
        s[1].add(r["source_group"])
    for i in sorted(per):
        print(f"{i}: {per[i][0]} approved recordings from {len(per[i][1])} source groups")
    print(f"approved={len(approved)} flagged={len(flags)} rejected={len(rejected)}")
    if flags:
        print("To decide flagged items, the human adds rows to data/human_decisions.csv "
              "(candidate_id,decision,note) and re-runs this script.")


if __name__ == "__main__":
    main()
