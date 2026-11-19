"""Shared helpers for the evaluation code (features, Test 1, Test 2).

numpy plus the standard library only. torch, panns_inference and BEATs are imported lazily
inside src/features.py backends, so every test runs without them.
"""
import csv, hashlib, json, math, subprocess, sys, wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import common as C  # noqa: E402
import validate as V  # noqa: E402

MODELS = ("panns_cnn14", "beats")
MODEL_SAMPLE_RATE = {"panns_cnn14": 32000, "beats": 16000}
TRADITION_ORDER = ["chinese", "andean", "middle_east", "control", "western"]
Z95 = 1.959963984540054


# ---------------------------------------------------------------- audio
def load_wav(path):
    """Mono float32 in [-1, 1) and the file's sample rate. PCM WAV only (clip.py writes pcm_s16le)."""
    with wave.open(str(path), "rb") as w:
        ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
        x = v.astype(np.float32) / 8388608.0
    else:
        raise ValueError(f"{path}: unsupported sample width {width}")
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


RESAMPLER = "windowed-sinc, Blackman window, 16 zero crossings, cutoff min(sr_in, sr_out)/2 (src/eval_common.py:resample)"


def resample(x, sr_in, sr_out, zeros=16, chunk=16384):
    """Band-limited resampling by direct windowed-sinc interpolation. Same code for every model and class."""
    x = np.asarray(x, dtype=np.float64)
    if sr_in == sr_out:
        return x.astype(np.float32)
    cutoff = min(1.0, sr_out / sr_in)          # fraction of the input Nyquist
    half = int(math.ceil(zeros / cutoff))       # kernel half-width in input samples
    n_out = int(round(len(x) * sr_out / sr_in))
    xp = np.concatenate([np.zeros(half + 1), x, np.zeros(half + 2)])
    offs = np.arange(-half, half + 1)
    out = np.empty(n_out)
    for s in range(0, n_out, chunk):
        t = np.arange(s, min(s + chunk, n_out)) * (sr_in / sr_out)
        i0 = np.floor(t).astype(np.int64)
        idx = i0[:, None] + offs[None, :]
        tau = idx - t[:, None]
        win = np.where(np.abs(tau) <= half,
                       0.42 + 0.5 * np.cos(np.pi * tau / half) + 0.08 * np.cos(2 * np.pi * tau / half), 0.0)
        h = cutoff * np.sinc(cutoff * tau) * win
        out[s:s + len(t)] = (xp[idx + half + 1] * h).sum(axis=1)
    return out.astype(np.float32)


# ---------------------------------------------------------------- AudioSet classes and ontology
def load_classes(path):
    """class_labels_indices.csv -> list of (mid, display_name) in index order."""
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    rows.sort(key=lambda r: int(r["index"]))
    if [int(r["index"]) for r in rows] != list(range(len(rows))):
        raise ValueError(f"{path}: index column is not 0..n-1")
    return [(r["mid"], r["display_name"]) for r in rows]


class Ontology:
    """AudioSet ontology.json (list of {id, name, child_ids, ...}). Read from a local file only."""

    def __init__(self, path):
        nodes = json.loads(Path(path).read_text(encoding="utf-8"))
        self.name = {n["id"]: n["name"] for n in nodes}
        self.children = {n["id"]: list(n.get("child_ids", [])) for n in nodes}
        self.by_name = {}
        for n in nodes:
            self.by_name.setdefault(n["name"], []).append(n["id"])

    def id_of(self, name):
        ids = self.by_name.get(name)
        if not ids:
            raise KeyError(f"{name!r} is not a node name in the ontology")
        if len(ids) > 1:
            raise KeyError(f"{name!r} names {len(ids)} ontology nodes: {ids}")
        return ids[0]

    def descendants(self, node_id, include_self=True):
        seen, stack = set(), [node_id]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self.children.get(n, []))
        if not include_self:
            seen.discard(node_id)
        return seen


# ---------------------------------------------------------------- provenance
def sha256_file(path, block=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(block), b""):
            h.update(b)
    return h.hexdigest()


def dataset_files():
    return [C.p("clips"), C.p("labels"), C.p("splits")]


def dataset_commit():
    """Last commit touching the manifest, label and split files, and whether they differ from it."""
    root = C.root()
    paths = [str(f.relative_to(root)) for f in dataset_files()]
    try:
        commit = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%H", "--", *paths],
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", *paths],
                               capture_output=True, text=True, check=True).stdout.strip()
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"dataset_commit": "not-a-git-repo", "dataset_dirty": None, "code_commit": None}
    return {"dataset_commit": commit or "uncommitted", "dataset_dirty": bool(dirty), "code_commit": head}


def file_hashes():
    return {str(f.relative_to(C.root())): (sha256_file(f) if f.exists() else None) for f in dataset_files()}


def require_gates():
    """Labels complete and splits valid, or stop. Same checks as scripts/validate.py."""
    ok, rep = V.run(["clips", "labels", "splits"], strict=False, labels_complete=True)
    if not ok:
        raise SystemExit("gates failed; fix before any real run:\n  " + "\n  ".join(rep.errors[:20]))
    return rep.warnings


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_result(experiment, model, payload, dry_run=False):
    """results/<experiment>_<model>_<timestamp>.json. Never overwrites."""
    need = C.schema("results_required_keys")
    miss = [k for k in need if k not in payload]
    if miss:
        raise ValueError(f"result is missing required keys {miss}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = C.p("results_dir")
    f = d / f"{experiment}_{model}_{stamp}.json"
    if dry_run:
        print(f"[dry-run] would write {f}")
        return f
    d.mkdir(parents=True, exist_ok=True)
    k = 1
    while f.exists():
        f = d / f"{experiment}_{model}_{stamp}_{k}.json"
        k += 1
    with open(f, "x", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=False)
    print(f"wrote {f}")
    return f


# ---------------------------------------------------------------- dataset
def usable_labels():
    """clip_id -> human label. Reuses scripts/validate.py:usable_clips, the same rule make_splits.py uses:
    pass-1 label, not 'reject'/'unsure', solo=y, confident=y. label_desk.py's summary applies the same rule."""
    clips = {r["clip_id"] for r in C.read_csv(C.p("clips"))}
    return {c: lab for c, lab in V.usable_clips().items() if c in clips}


def manifest():
    return {r["clip_id"]: r for r in C.read_csv(C.p("clips"))}


# ---------------------------------------------------------------- statistics
def wilson(k, n, z=Z95):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def cluster_bootstrap(values, groups, rng, reps=2000):
    """Percentile 95% CI of the mean of per-clip values, resampling source groups with replacement."""
    values = np.asarray(values, dtype=float)
    ug = sorted(set(groups))
    if not len(values):
        return [None, None]
    if len(ug) == 1:
        m = float(values.mean())
        return [m, m]
    gi = {g: i for i, g in enumerate(ug)}
    idx = np.array([gi[g] for g in groups])
    s = np.bincount(idx, weights=values, minlength=len(ug))
    n = np.bincount(idx, minlength=len(ug)).astype(float)
    pick = rng.integers(0, len(ug), size=(reps, len(ug)))
    stat = s[pick].sum(1) / n[pick].sum(1)
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return [float(lo), float(hi)]
