#!/usr/bin/env python3
"""Frozen-model features: full 527-way AudioSet probabilities and one pooled embedding per clip.

  .venv/bin/python src/features.py --model panns_cnn14 --checkpoint checkpoints/<file>.pth \
      --class-labels data/audioset/class_labels_indices.csv [--dry-run] [--limit N]
  .venv/bin/python src/features.py --model beats --checkpoint checkpoints/<file>.pt \
      --beats-src third_party/beats --class-labels data/audioset/class_labels_indices.csv

Every clip in data/clips_manifest.csv is processed (features do not depend on labels). Clips are read
at their stored sample rate and resampled at load time to the model's rate (PANNs CNN14 32 kHz,
BEATs 16 kHz) with the same resampler for every class. Zero padding in short clips is kept as is;
content_s is carried into the cache. Output: data/features/<model>/<checkpoint sha256[:16]>/
  meta.json         model, checkpoint, layer, pooling, resampler, class list hash
  <clip_id>.npz     probs (527, class_labels_indices order), embedding, provenance fields
A cached file is reused only if its clip sha256 and checkpoint match; a mismatch stops the run
(nothing is overwritten or deleted). No weights are updated: models run in eval mode under no_grad.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_common as E  # noqa: E402
from eval_common import C  # noqa: E402


class Backend:
    """Interface. infer() takes mono float32 at self.sample_rate and returns (probs, embedding);
    probs are in the order of self.output_mids."""
    name = ""
    sample_rate = 0
    layer = ""
    pooling = ""
    checkpoint_name = ""
    checkpoint_sha256 = ""
    output_mids = []

    def infer(self, wave):
        raise NotImplementedError


class PannsCnn14(Backend):
    name = "panns_cnn14"
    sample_rate = 32000
    layer = "Cnn14 'embedding' output of panns_inference.AudioTagging.inference (fc1 after ReLU, 2048-d, penultimate)"
    pooling = "the model's own clip-level pooling over time and frequency (Cnn14 forward); no extra pooling"

    def __init__(self, checkpoint, class_mids, device="cpu"):
        # panns_inference reads ~/panns_data/class_labels_indices.csv at import and tries to download it if
        # missing; the human copies the CSV there first so this stays offline.
        from panns_inference import AudioTagging
        self.checkpoint_name = Path(checkpoint).name
        self.checkpoint_sha256 = E.sha256_file(checkpoint)
        self.model = AudioTagging(checkpoint_path=str(checkpoint), device=device)
        # Cnn14's 527 outputs follow class_labels_indices.csv index order (the CSV the model was trained with).
        self.output_mids = list(class_mids)

    def infer(self, wave):
        probs, emb = self.model.inference(wave[None, :].astype(np.float32))
        return np.asarray(probs)[0], np.asarray(emb)[0]


class Beats(Backend):
    name = "beats"
    sample_rate = 16000
    layer = "BEATs final Transformer encoder layer output (input to the AudioSet predictor head), 768-d per frame"
    pooling = "mean over all time frames, padded frames included (no padding_mask; zero padding kept as audio)"

    def __init__(self, checkpoint, beats_src, device="cpu", trust_pickle=False):
        import torch
        sys.path.insert(0, str(Path(beats_src).resolve()))
        from BEATs import BEATs, BEATsConfig  # unilm/beats source, placed by the human
        self.torch, self.device = torch, device
        self.checkpoint_name = Path(checkpoint).name
        self.checkpoint_sha256 = E.sha256_file(checkpoint)
        try:
            ck = torch.load(str(checkpoint), map_location="cpu", weights_only=True)
        except Exception as e:  # noqa: BLE001
            if not trust_pickle:
                raise SystemExit(f"torch.load(weights_only=True) failed ({e}). If the checkpoint came from the "
                                 "official BEATs release, rerun with --trust-checkpoint-pickle.")
            ck = torch.load(str(checkpoint), map_location="cpu", weights_only=False)
        model = BEATs(BEATsConfig(ck["cfg"]))
        model.load_state_dict(ck["model"])
        model.eval().to(device)
        if getattr(model, "predictor", None) is None:
            raise SystemExit("this BEATs checkpoint has no AudioSet predictor head; use an AS2M fine-tuned checkpoint")
        self.model = model
        self._feat = None
        model.predictor.register_forward_hook(lambda m, inp, out: setattr(self, "_feat", inp[0].detach()))
        self.output_mids = self._mids_from(ck.get("label_dict"))

    @staticmethod
    def _mids_from(label_dict):
        if not label_dict:
            raise SystemExit("checkpoint has no 'label_dict'; cannot map BEATs outputs to AudioSet classes")
        items = list(label_dict.items())
        if all(str(k).startswith("/") for k, _ in items):          # mid -> index
            order = sorted(items, key=lambda kv: int(kv[1]))
            mids = [k for k, _ in order]
            idx = [int(v) for _, v in order]
        else:                                                    # index -> mid
            order = sorted(items, key=lambda kv: int(kv[0]))
            mids = [v for _, v in order]
            idx = [int(k) for k, _ in order]
        if idx != list(range(len(mids))):
            raise SystemExit("label_dict indices are not 0..n-1")
        return mids

    def infer(self, wave):
        t = self.torch
        with t.no_grad():
            x = t.from_numpy(wave[None, :].astype(np.float32)).to(self.device)
            pad = t.zeros_like(x, dtype=t.bool)
            probs = self.model.extract_features(x, padding_mask=pad)[0]
            emb = self._feat.mean(dim=1)
        return probs[0].cpu().numpy(), emb[0].cpu().numpy()


# ---------------------------------------------------------------- extraction
def features_dir(model, checkpoint_sha256):
    return C.root() / "data" / "features" / model / checkpoint_sha256[:16]


def _meta(backend, classes_sha, n_classes):
    return {"model": backend.name, "checkpoint_name": backend.checkpoint_name,
            "checkpoint_sha256": backend.checkpoint_sha256, "sample_rate": backend.sample_rate,
            "layer": backend.layer, "pooling": backend.pooling, "resampler": E.RESAMPLER,
            "class_labels_sha256": classes_sha, "n_classes": n_classes,
            "padding": "zero padding to 10 s kept as audio; per-clip content_s stored"}


def extract(backend, classes, classes_sha, clips=None, limit=None, dry_run=False, log=print):
    """Compute and cache features for manifest clips. Returns the cache directory."""
    mids = [m for m, _ in classes]
    pos = {m: i for i, m in enumerate(mids)}
    missing = [m for m in backend.output_mids if m not in pos]
    if missing or len(backend.output_mids) != len(mids):
        raise SystemExit(f"model outputs do not match the class list ({len(backend.output_mids)} vs {len(mids)}; "
                         f"unknown mids {missing[:5]})")
    perm = np.array([pos[m] for m in backend.output_mids])  # model output j -> canonical index perm[j]
    out = features_dir(backend.name, backend.checkpoint_sha256)
    meta = _meta(backend, classes_sha, len(mids))
    rows = list(clips if clips is not None else C.read_csv(C.p("clips")))
    if limit:
        rows = rows[:limit]
    if dry_run:
        log(f"[dry-run] {len(rows)} clips -> {out}")
        return out
    out.mkdir(parents=True, exist_ok=True)
    mf = out / "meta.json"
    if mf.exists():
        old = json.loads(mf.read_text(encoding="utf-8"))
        diff = {k for k in meta if old.get(k) != meta[k]}
        if diff:
            raise SystemExit(f"{mf} differs from this run in {sorted(diff)}; use a new cache directory")
    else:
        mf.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    t0, done = time.time(), 0
    for n, r in enumerate(rows, 1):
        f = out / f"{r['clip_id']}.npz"
        if f.exists():
            with np.load(f) as z:
                if str(z["clip_sha256"]) != r["sha256"]:
                    raise SystemExit(f"{f}: cached for a different clip file (sha256 mismatch); not overwriting")
            continue
        wav_path = C.root() / r["path"]
        if E.sha256_file(wav_path) != r["sha256"]:
            raise SystemExit(f"{wav_path}: sha256 differs from the clips manifest")
        x, sr = E.load_wav(wav_path)
        y = E.resample(x, sr, backend.sample_rate)
        p, e = backend.infer(y)
        p, e = np.asarray(p, dtype=np.float32), np.asarray(e, dtype=np.float32).ravel()
        if p.shape != (len(mids),):
            raise SystemExit(f"{r['clip_id']}: probabilities have shape {p.shape}")
        canon = np.empty_like(p)
        canon[perm] = p
        tmp = out / f".{r['clip_id']}.tmp.npz"
        np.savez(tmp, probs=canon, embedding=e, clip_sha256=r["sha256"], sr_in=sr,
                 sr_model=backend.sample_rate, content_s=float(r.get("content_s") or "nan"),
                 checkpoint_sha256=backend.checkpoint_sha256)
        tmp.replace(f)
        done += 1
        if done in (5, 50) or n == len(rows):
            rate = (time.time() - t0) / done
            log(f"{n}/{len(rows)} clips, {rate:.2f} s/clip, about {rate * (len(rows) - n) / 60:.1f} min left")
    return out


def load_features(fdir, clip_ids):
    """(meta, probs [n,527], embeddings [n,d], content_s [n]) for clip_ids, in that order."""
    fdir = Path(fdir)
    meta = json.loads((fdir / "meta.json").read_text(encoding="utf-8"))
    P, X, cs = [], [], []
    for c in clip_ids:
        f = fdir / f"{c}.npz"
        if not f.exists():
            raise SystemExit(f"no cached features for {c} in {fdir}; run src/features.py first")
        with np.load(f) as z:
            if str(z["checkpoint_sha256"]) != meta["checkpoint_sha256"]:
                raise SystemExit(f"{f}: checkpoint differs from {fdir / 'meta.json'}")
            P.append(z["probs"])
            X.append(z["embedding"])
            cs.append(float(z["content_s"]))
    return meta, np.array(P), np.array(X), np.array(cs)


def find_features_dir(model, given=None):
    if given:
        return Path(given)
    base = C.root() / "data" / "features" / model
    subs = sorted(d for d in base.iterdir() if d.is_dir()) if base.exists() else []
    if len(subs) != 1:
        raise SystemExit(f"{base}: expected exactly one checkpoint directory, found {len(subs)}; pass --features")
    return subs[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=E.MODELS)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--class-labels", required=True, help="AudioSet class_labels_indices.csv (local file)")
    ap.add_argument("--beats-src", help="folder with BEATs.py from microsoft/unilm/beats")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--trust-checkpoint-pickle", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    classes = E.load_classes(a.class_labels)
    if not Path(a.checkpoint).exists():
        raise SystemExit(f"{a.checkpoint} not found; the human downloads checkpoints")
    if a.model == "panns_cnn14":
        be = PannsCnn14(a.checkpoint, [m for m, _ in classes], a.device)
    else:
        if not a.beats_src:
            raise SystemExit("--beats-src is required for BEATs")
        be = Beats(a.checkpoint, a.beats_src, a.device, a.trust_checkpoint_pickle)
    print(f"{be.name}: checkpoint {be.checkpoint_name} sha256 {be.checkpoint_sha256}")
    extract(be, classes, E.sha256_file(a.class_labels), limit=a.limit, dry_run=a.dry_run)


if __name__ == "__main__":
    main()
