import csv, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "hooks"))


@pytest.fixture
def proj(tmp_path, monkeypatch):
    """An empty project folder with the real config and schemas."""
    for d in ("config", "schemas"):
        shutil.copytree(REPO / d, tmp_path / d)
    monkeypatch.setenv("NWI_ROOT", str(tmp_path))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


def cand(i, instrument="erhu", uploader="alice", lic="https://creativecommons.org/licenses/by/4.0/", dur=40.0, source="freesound"):
    import common as C
    fs = source == "freesound"
    return {"candidate_id": f"{'fs' if fs else 'wc'}:{i}", "source": source,
            "source_url": f"https://freesound.org/s/{i}/" if fs else f"https://commons.wikimedia.org/wiki/File:x{i}.ogg",
            "title": f"clip {i}", "uploader": uploader, "license_raw": lic, "license_code": C.normalize_license(lic),
            "duration_s": f"{dur:.2f}", "instrument": instrument, "query": instrument, "tags": "", "description": "",
            "download_url": f"https://cdn.freesound.org/previews/{i}.mp3" if fs else f"https://upload.wikimedia.org/x{i}.ogg",
            "retrieved_at": "2026-11-15T00:00:00Z"}


def write_candidates(proj, rows):
    import common as C
    by = {}
    for r in rows:
        by.setdefault(r["instrument"], []).append(r)
    for ins, rs in by.items():
        C.write_csv(proj / "data" / "candidates" / f"{ins}.csv", rs, C.schema("candidates"))


def make_raw(proj, row, freq, seconds):
    """Put a synthetic tone where clip.py expects the downloaded file, so no network is used."""
    import clip
    dst = clip.raw_path(row)
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:duration={seconds}", "-f", "mp3" if dst.suffix == ".mp3" else "ogg", str(dst)], check=True)


@pytest.fixture
def built(proj):
    """Run the whole pipeline on synthetic audio: 2 instruments x 4 uploaders."""
    import common as C, curate, clip, label_desk, make_splits
    rows, n = [], 100
    for ins in ("erhu", "violin"):
        for u in ("alice", "bob", "carol", "dave"):
            for _ in range(2):
                n += 1
                rows.append(cand(n, ins, u))
    write_candidates(proj, rows)
    curate.main()
    for k, r in enumerate(C.read_csv(C.p("approved"))):
        make_raw(proj, r, 220 + 37 * k, 12 if k % 2 else 7)
    clip.main(["--instrument", "all"])
    label_desk.queue()
    clips = C.read_csv(C.p("clips"))
    C.write_csv(C.p("labels"), [{"clip_id": c["clip_id"], "pass": "1", "label": c["instrument"], "solo": "y",
                                 "confident": "y", "note": "", "labeled_at": "t"} for c in clips], C.schema("labels"))
    make_splits.main()
    return proj
