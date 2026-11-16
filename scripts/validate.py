#!/usr/bin/env python3
"""Gate checks for every pipeline stage. Standard library only.

Usage:
  python3 scripts/validate.py --stage candidates|approved|clips|queue|labels|splits|results
  python3 scripts/validate.py --all            # every stage whose file exists
  python3 scripts/validate.py --all --strict   # warnings count as failures

Exit code 0 = PASS, 1 = FAIL. Errors name the file and row so they can be fixed.
HUMAN-ONLY FILE: agents may not edit this script.
"""
import argparse, hashlib, json, re, sys, wave
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE_HOSTS = {"freesound": {"freesound.org", "www.freesound.org"},
                "commons": {"commons.wikimedia.org"}}
DOWNLOAD_HOSTS = {"freesound": {"cdn.freesound.org", "freesound.org", "www.freesound.org"},
                  "commons": {"upload.wikimedia.org"}}
ID_RE = re.compile(r"^(fs|wc):\d+$")
STAGES = ["candidates", "approved", "clips", "queue", "labels", "splits", "results"]


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def _header_ok(rep, path, stage):
    want = C.schema(stage)
    got = C.csv_header(path)
    if got != want:
        rep.err(path.name, f"columns must be exactly {want}; got {got}")
        return False
    return True


def _host(url):
    u = urlparse(url)
    return u.hostname if u.scheme == "https" else None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def check_candidates(rep):
    d = C.p("candidates_dir")
    files = sorted(d.glob("*.csv")) if d.exists() else []
    inst = C.instruments()
    for f in files:
        if f.stem not in inst:
            rep.err(f.name, f"file name must be an instrument id from config/instruments.json")
            continue
        if not _header_ok(rep, f, "candidates"):
            continue
        seen = set()
        for n, r in enumerate(C.read_csv(f), start=2):
            w = f"{f.name} row {n} ({r['candidate_id']})"
            if not ID_RE.match(r["candidate_id"]):
                rep.err(w, "candidate_id must look like fs:123 or wc:123")
            if r["candidate_id"] in seen:
                rep.err(w, "duplicate candidate_id")
            seen.add(r["candidate_id"])
            if r["source"] not in SOURCE_HOSTS:
                rep.err(w, f"source must be freesound or commons, got {r['source']!r}")
                continue
            if _host(r["source_url"]) not in SOURCE_HOSTS[r["source"]]:
                rep.err(w, f"source_url is not an https {r['source']} URL")
            if _host(r["download_url"]) not in DOWNLOAD_HOSTS[r["source"]]:
                rep.err(w, f"download_url host not allowed for {r['source']}")
            if r["instrument"] != f.stem:
                rep.err(w, f"instrument {r['instrument']!r} does not match file name")
            if C.normalize_license(r["license_raw"]) != r["license_code"]:
                rep.err(w, f"license_code {r['license_code']!r} does not match license_raw {r['license_raw']!r}")
            dur = _num(r["duration_s"])
            if dur is None or dur <= 0:
                rep.err(w, "duration_s must be a positive number")
    return files


def _all_candidates():
    out = {}
    d = C.p("candidates_dir")
    for f in sorted(d.glob("*.csv")) if d.exists() else []:
        for r in C.read_csv(f):
            out[(r.get("candidate_id"), r.get("instrument"))] = r
    return out


def _human():
    return {r["candidate_id"]: r["decision"].strip().lower() for r in C.read_csv(C.p("human_decisions"))}


def check_approved(rep):
    f = C.p("approved")
    if not f.exists() or not _header_ok(rep, f, "approved"):
        return
    lic, cands, human = C.cfg("licenses"), _all_candidates(), _human()
    seen = set()
    for n, r in enumerate(C.read_csv(f), start=2):
        w = f"approved.csv row {n} ({r['candidate_id']})"
        if r["candidate_id"] in seen:
            rep.err(w, "duplicate candidate_id")
        seen.add(r["candidate_id"])
        src = cands.get((r["candidate_id"], r["instrument"]))
        if src is None:
            rep.err(w, "not found in data/candidates for this instrument")
            continue
        for col in ("license_code", "source_url", "download_url", "uploader"):
            if src[col] != r[col]:
                rep.err(w, f"{col} differs from the candidates file")
        if not r["source_group"].strip():
            rep.err(w, "source_group is empty (needed for the uploader split)")
        code, dec = r["license_code"], human.get(r["candidate_id"])
        if dec == "reject":
            rep.err(w, "human decision is reject")
        elif code in lic["accept"]:
            if r["decided_by"] not in ("rule", "human"):
                rep.err(w, "decided_by must be rule or human")
        elif code in lic["needs_human"]:
            if dec != "approve" or r["decided_by"] != "human":
                rep.err(w, f"license {code!r} needs a human 'approve' in data/human_decisions.csv")
        else:
            rep.err(w, f"license {code!r} is not allowed")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_clips(rep):
    f = C.p("clips")
    if not f.exists() or not _header_ok(rep, f, "clips"):
        return
    pc = C.cfg("pipeline")
    approved = {r["candidate_id"]: r for r in C.read_csv(C.p("approved"))}
    ids, shas, per_src, per_group = set(), {}, Counter(), Counter()
    for n, r in enumerate(C.read_csv(f), start=2):
        w = f"clips_manifest.csv row {n} ({r['clip_id']})"
        if r["clip_id"] in ids:
            rep.err(w, "duplicate clip_id")
        ids.add(r["clip_id"])
        a = approved.get(r["candidate_id"])
        if a is None:
            rep.err(w, "candidate_id is not in data/approved.csv")
        else:
            for col in ("instrument", "source_group", "license_code"):
                if a[col] != r[col]:
                    rep.err(w, f"{col} differs from approved.csv")
        per_src[r["candidate_id"]] += 1
        per_group[(r["instrument"], r["source_group"])] += 1
        path = C.root() / r["path"]
        if not path.is_file():
            rep.err(w, f"file missing: {r['path']}")
            continue
        try:
            with wave.open(str(path), "rb") as wf:
                sr, ch, frames = wf.getframerate(), wf.getnchannels(), wf.getnframes()
        except (wave.Error, EOFError) as e:
            rep.err(w, f"not a readable WAV: {e}")
            continue
        if sr != pc["sample_rate"] or str(sr) != r["sample_rate"]:
            rep.err(w, f"sample rate {sr}, expected {pc['sample_rate']}")
        if ch != 1:
            rep.err(w, f"{ch} channels, expected mono")
        if abs(frames / sr - pc["clip_seconds"]) > 0.01:
            rep.err(w, f"length {frames / sr:.3f}s, expected {pc['clip_seconds']}s")
        cs = _num(r["content_s"])
        if cs is None or cs < pc["min_source_seconds"] - 0.01 or cs > pc["clip_seconds"] + 0.01:
            rep.err(w, "content_s out of range")
        sha = _sha(path)
        if sha != r["sha256"]:
            rep.err(w, "sha256 does not match the file")
        if sha in shas:
            rep.err(w, f"identical audio to {shas[sha]}")
        shas[sha] = r["clip_id"]
    for cid, k in per_src.items():
        if k > pc["max_clips_per_source"]:
            rep.err("clips_manifest.csv", f"{cid} has {k} clips; max is {pc['max_clips_per_source']} per recording")
    for (ins, g), k in per_group.items():
        if k > pc["max_clips_per_group"]:
            rep.err("clips_manifest.csv", f"{ins}: source group {g} has {k} clips; max is {pc['max_clips_per_group']}")


def check_queue(rep):
    f = C.p("queue")
    if not f.exists() or not _header_ok(rep, f, "queue"):
        return
    clips = {r["clip_id"] for r in C.read_csv(C.p("clips"))}
    seen = set()
    for n, r in enumerate(C.read_csv(f), start=2):
        w = f"queue.csv row {n} ({r['clip_id']})"
        if r["clip_id"] not in clips:
            rep.err(w, "clip_id is not in the clips manifest")
        if r["pass"] not in ("1", "2"):
            rep.err(w, "pass must be 1 or 2")
        if (r["clip_id"], r["pass"]) in seen:
            rep.err(w, "duplicate (clip_id, pass)")
        seen.add((r["clip_id"], r["pass"]))


def check_labels(rep, complete=False):
    f = C.p("labels")
    if not f.exists():
        if complete:
            rep.err("labels.csv", "no labels yet")
        return
    if not _header_ok(rep, f, "labels"):
        return
    clips = {r["clip_id"] for r in C.read_csv(C.p("clips"))}
    vocab, seen = C.label_vocab(), set()
    for n, r in enumerate(C.read_csv(f), start=2):
        w = f"labels.csv row {n} ({r['clip_id']})"
        if r["clip_id"] not in clips:
            rep.err(w, "clip_id is not in the clips manifest")
        if r["pass"] not in ("1", "2"):
            rep.err(w, "pass must be 1 or 2")
        if (r["clip_id"], r["pass"]) in seen:
            rep.err(w, "duplicate (clip_id, pass)")
        seen.add((r["clip_id"], r["pass"]))
        if r["label"] not in vocab:
            rep.err(w, f"label {r['label']!r} is not in the controlled vocabulary")
        for col in ("solo", "confident"):
            if r[col] not in ("y", "n"):
                rep.err(w, f"{col} must be y or n")
    missing = clips - {c for c, ps in seen if ps == "1"}
    if missing:
        msg = f"{len(missing)} clips have no pass-1 label (e.g. {sorted(missing)[:3]})"
        (rep.err if complete else rep.warn)("labels.csv", msg)


def usable_clips():
    """clip_id -> final instrument: the human pass-1 label, solo and confident."""
    vocab_extra = set(C.cfg("instruments")["label_extras"])
    return {r["clip_id"]: r["label"] for r in C.read_csv(C.p("labels"))
            if r["pass"] == "1" and r["label"] not in vocab_extra and r["solo"] == "y" and r["confident"] == "y"}


def check_splits(rep):
    f = C.p("splits")
    if not f.exists() or not _header_ok(rep, f, "splits"):
        return
    pc = C.cfg("pipeline")
    clips = {r["clip_id"]: r for r in C.read_csv(C.p("clips"))}
    usable = usable_clips()
    side_of_group, per = {}, defaultdict(Counter)
    seen = set()
    for n, r in enumerate(C.read_csv(f), start=2):
        w = f"splits.csv row {n} ({r['clip_id']})"
        if r["clip_id"] in seen:
            rep.err(w, "duplicate clip_id")
        seen.add(r["clip_id"])
        if r["split"] not in ("train", "test"):
            rep.err(w, "split must be train or test")
            continue
        c = clips.get(r["clip_id"])
        if c is None:
            rep.err(w, "clip_id is not in the clips manifest")
            continue
        if usable.get(r["clip_id"]) != r["instrument"]:
            rep.err(w, "instrument must equal the human pass-1 label (solo=y, confident=y)")
        if c["source_group"] != r["source_group"]:
            rep.err(w, "source_group differs from the clips manifest")
        g = r["source_group"]
        if side_of_group.setdefault(g, r["split"]) != r["split"]:
            rep.err(w, f"source group {g} appears in both train and test (leak)")
        per[r["instrument"]][r["split"]] += 1
    unused = set(usable) - seen
    if unused:
        rep.warn("splits.csv", f"{len(unused)} usable clips are not in any split")
    for ins, c in sorted(per.items()):
        if not c["train"] or not c["test"]:
            rep.err("splits.csv", f"{ins}: needs clips on both sides (train={c['train']}, test={c['test']}); "
                                  "likely all clips come from one source group")
        total = c["train"] + c["test"]
        if total < pc["min_clips_per_instrument"]:
            rep.warn("splits.csv", f"{ins}: {total} usable clips, below the minimum of {pc['min_clips_per_instrument']}")


def check_results(rep):
    d = C.p("results_dir")
    need = C.schema("results_required_keys")
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            rep.err(f.name, f"invalid JSON: {e}")
            continue
        miss = [k for k in need if k not in data]
        if miss:
            rep.err(f.name, f"missing keys {miss}")
        if "checkpoint_sha256" in data and not re.fullmatch(r"[0-9a-f]{64}", str(data["checkpoint_sha256"])):
            rep.err(f.name, "checkpoint_sha256 must be a 64-character hex digest")
        if "seed" in data and not isinstance(data["seed"], int):
            rep.err(f.name, "seed must be an integer")


CHECKS = {"candidates": check_candidates, "approved": check_approved, "clips": check_clips,
          "queue": check_queue, "labels": check_labels, "splits": check_splits, "results": check_results}


def run(stages, strict=False, labels_complete=False):
    rep = Report()
    for s in stages:
        try:
            if s == "labels":
                check_labels(rep, complete=labels_complete)
            else:
                CHECKS[s](rep)
        except KeyError as e:
            rep.err(s, f"missing column {e}")
    ok = not rep.errors and not (strict and rep.warnings)
    return ok, rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="append", choices=STAGES)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--labels-complete", action="store_true", help="every clip must have a pass-1 label")
    a = ap.parse_args(argv)
    stages = STAGES if a.all or not a.stage else a.stage
    ok, rep = run(stages, a.strict, a.labels_complete)
    for wmsg in rep.warnings:
        print(f"WARN  {wmsg}")
    for emsg in rep.errors[:200]:
        print(f"ERROR {emsg}")
    if len(rep.errors) > 200:
        print(f"... and {len(rep.errors) - 200} more errors")
    print(f"{'PASS' if ok else 'FAIL'}  stages={','.join(stages)}  errors={len(rep.errors)} warnings={len(rep.warnings)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
