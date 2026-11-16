#!/usr/bin/env python3
"""Stage 3 (clipper): download approved recordings and cut 10-second clips.

  python3 scripts/clip.py --instrument erhu     # or 'all'

For each instrument it walks source groups round-robin (so one uploader cannot
dominate), downloads each recording once into data/raw/ (never modified
afterwards), decodes to mono WAV, and keeps up to N non-overlapping windows with
the highest energy. Recordings between the minimum length and 10 s are padded
with silence; content_s records the real audio length. Needs ffmpeg and numpy.
"""
import argparse, hashlib, subprocess, sys, tempfile, wave
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
from validate import DOWNLOAD_HOSTS


def raw_path(row):
    ext = Path(urlparse(row["download_url"]).path).suffix.lower() or ".bin"
    return C.root() / "data" / "raw" / row["source"] / (row["candidate_id"].replace(":", "") + ext)


def download(row):
    dst = raw_path(row)
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    host = urlparse(row["download_url"]).hostname
    if host not in DOWNLOAD_HOSTS[row["source"]]:
        raise RuntimeError(f"refusing to download from {host}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = Request(row["download_url"], headers={"User-Agent": "nonwestern-instruments-research/0.1 (OU NLP Lab)"})
    tmp = dst.with_suffix(dst.suffix + ".part")
    with urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    tmp.replace(dst)
    return dst


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def pick_windows(samples, sr, clip_s, max_n, floor_db):
    """Start times (s) of up to max_n non-overlapping windows, loudest first."""
    import numpy as np
    n, win, hop = len(samples), int(clip_s * sr), int(clip_s * sr / 2)
    if n <= win:
        return [0.0]
    x = samples.astype(np.float64) / 32768.0
    cs = np.concatenate([[0.0], np.cumsum(x * x)])
    starts = np.arange(0, n - win + 1, hop)
    db = 10 * np.log10(np.maximum((cs[starts + win] - cs[starts]) / win, 1e-12))
    chosen = []
    for i in np.argsort(-db):
        if db[i] < floor_db or len(chosen) == max_n:
            break
        if all(abs(starts[i] - s) >= win for s in chosen):
            chosen.append(int(starts[i]))
    return [s / sr for s in sorted(chosen)]


def cut(row, pc, tmpdir):
    """Return manifest rows for one approved recording (files written to data/clips/)."""
    import numpy as np
    sr, clip_s = pc["sample_rate"], pc["clip_seconds"]
    full = Path(tmpdir) / "full.wav"
    ffmpeg("-i", str(download(row)), "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", str(full))
    with wave.open(str(full), "rb") as wf:
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    dur = len(samples) / sr
    if dur < pc["min_source_seconds"]:
        return []
    out = []
    stem = f"{row['instrument']}_{row['candidate_id'].replace(':', '')}"
    for k, start in enumerate(pick_windows(samples, sr, clip_s, pc["max_clips_per_source"], pc["silence_floor_dbfs"])):
        rel = Path("data") / "clips" / row["instrument"] / f"{stem}_{k}.wav"
        dst = C.root() / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg("-ss", f"{start:.3f}", "-i", str(full), "-af", "apad", "-t", f"{clip_s}",
               "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", "-bitexact", str(dst))
        out.append({"clip_id": f"{stem}_{k}", "candidate_id": row["candidate_id"], "instrument": row["instrument"],
                    "source_group": row["source_group"], "license_code": row["license_code"],
                    "path": rel.as_posix(), "start_s": f"{start:.3f}", "duration_s": f"{clip_s:.1f}",
                    "content_s": f"{min(clip_s, dur - start):.2f}", "sample_rate": str(sr),
                    "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()})
    return out


def round_robin(rows):
    groups = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["candidate_id"]):
        groups[r["source_group"]].append(r)
    order = sorted(groups)
    while any(groups.values()):
        for g in order:
            if groups[g]:
                yield groups[g].pop(0)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", required=True)
    a = ap.parse_args(argv)
    pc = C.cfg("pipeline")
    manifest = C.read_csv(C.p("clips"))
    done = {r["candidate_id"] for r in manifest}
    shas = {r["sha256"] for r in manifest}
    approved = C.read_csv(C.p("approved"))
    ids = sorted({r["instrument"] for r in approved}) if a.instrument == "all" else [a.instrument]
    for ins in ids:
        n = sum(r["instrument"] == ins for r in manifest)
        per_group = Counter(r["source_group"] for r in manifest if r["instrument"] == ins)
        failed = 0
        for row in round_robin([r for r in approved if r["instrument"] == ins and r["candidate_id"] not in done]):
            if n >= pc["max_clips_per_instrument"]:
                break
            room = pc["max_clips_per_group"] - per_group[row["source_group"]]
            if room <= 0:
                continue
            try:
                with tempfile.TemporaryDirectory() as td:
                    new = cut(row, pc, td)
            except Exception as e:  # one bad file must not stop the batch
                failed += 1
                print(f"  skip {row['candidate_id']}: {type(e).__name__}: {e}")
                continue
            for c in new[:room]:
                if c["sha256"] in shas:
                    (C.root() / c["path"]).unlink(missing_ok=True)
                    continue
                shas.add(c["sha256"])
                manifest.append(c)
                per_group[row["source_group"]] += 1
                n += 1
            for c in new[room:]:
                (C.root() / c["path"]).unlink(missing_ok=True)
            C.write_csv(C.p("clips"), manifest, C.schema("clips"))  # checkpoint after every recording
        print(f"{ins}: {n} clips from {len(per_group)} source groups ({failed} downloads/decodes failed)")


if __name__ == "__main__":
    main()
