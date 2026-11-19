"""Evaluation code on synthetic fixtures only: a tiny made-up AudioSet ontology and class list, a fake
model backend, synthetic tones and Gaussian embeddings. No torch, no checkpoints, no network."""
import csv, hashlib, json, sys, wave
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

# ---------------------------------------------------------------- fixtures: ontology and classes
# Made-up ids. Names mirror the strings used in config/instruments.json so the config check can run.
TREE = {
    "Music": ["Musical instrument", "Music genre", "Music mood"],
    "Musical instrument": ["Plucked string instrument", "Bowed string instrument", "Percussion",
                           "Wind instrument, woodwind instrument"],
    "Plucked string instrument": ["Guitar", "Sitar", "Zither"],
    "Guitar": ["Acoustic guitar"],
    "Bowed string instrument": ["Violin, fiddle"],
    "Percussion": ["Drum"],
    "Drum": ["Snare drum", "Bass drum", "Tabla"],
    "Wind instrument, woodwind instrument": ["Flute"],
    "Music genre": ["Pop music"],
    "Music mood": ["Happy music"],
    "Speech": [],
}
NOT_A_CLASS = {"Music genre", "Music mood"}  # abstract ontology nodes, like AudioSet's


def _all_names():
    names = []
    for p, ch in TREE.items():
        for n in [p, *ch]:
            if n not in names:
                names.append(n)
    return names


def _mid(name):
    return "/t/" + hashlib.md5(name.encode()).hexdigest()[:6]


def write_audioset(dirpath):
    dirpath = Path(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)
    names = _all_names()
    onto = [{"id": _mid(n), "name": n, "child_ids": [_mid(c) for c in TREE.get(n, [])]} for n in names]
    (dirpath / "ontology.json").write_text(json.dumps(onto), encoding="utf-8")
    with open(dirpath / "class_labels_indices.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "mid", "display_name"])
        for i, n in enumerate(x for x in names if x not in NOT_A_CLASS):
            w.writerow([i, _mid(n), n])
    return dirpath / "class_labels_indices.csv", dirpath / "ontology.json"


@pytest.fixture
def aset(tmp_path):
    return write_audioset(tmp_path / "audioset")


def write_tone(path, sr, freq, seconds=10.0, content=None):
    t = np.arange(int(sr * seconds)) / sr
    x = 0.5 * np.sin(2 * np.pi * freq * t)
    if content is not None:
        x[int(sr * content):] = 0.0
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


class FakeBackend:
    """Deterministic stand-in for a model: probabilities and embedding are fixed functions of the audio.
    Outputs are in reversed class order to exercise the reorder to class_labels_indices order."""

    def __init__(self, classes, name="beats", sample_rate=16000):
        self.name, self.sample_rate = name, sample_rate
        self.layer, self.pooling = "fake layer", "fake pooling"
        self.checkpoint_name = "fake.pt"
        self.checkpoint_sha256 = hashlib.sha256(b"fake checkpoint").hexdigest()
        self.output_mids = [m for m, _ in classes][::-1]
        self.seen_lengths = []

    def infer(self, wav):
        self.seen_lengths.append(len(wav))
        spec = np.abs(np.fft.rfft(wav))
        band = np.array_split(spec, 8)
        emb = np.log1p(np.array([b.sum() for b in band]))
        n = len(self.output_mids)
        p = np.linspace(0.1, 0.9, n) * (1 + 0.01 * emb[0])
        return np.clip(p, 0, 1), emb


# ---------------------------------------------------------------- audio
def test_load_wav_and_resample_keeps_frequency(tmp_path):
    import eval_common as E
    f = tmp_path / "a.wav"
    write_tone(f, 44100, 1000.0, seconds=1.0)
    x, sr = E.load_wav(f)
    assert sr == 44100 and len(x) == 44100 and abs(np.abs(x).max() - 0.5) < 1e-3
    for out_sr in (16000, 32000):
        y = E.resample(x, sr, out_sr)
        assert len(y) == out_sr
        spec = np.abs(np.fft.rfft(y[2000:-2000] * np.hanning(len(y) - 4000)))
        peak_hz = np.argmax(spec) * out_sr / (len(y) - 4000)
        assert abs(peak_hz - 1000) < 5
        assert abs(np.abs(y[2000:-2000]).max() - 0.5) < 0.01


def test_resample_suppresses_aliasing(tmp_path):
    import eval_common as E
    sr = 44100
    t = np.arange(sr) / sr
    x = 0.5 * np.sin(2 * np.pi * 12000 * t)       # above the 8 kHz Nyquist of 16 kHz
    y = E.resample(x, sr, 16000)
    assert np.sqrt(np.mean(y[1000:-1000] ** 2)) < 0.5 / np.sqrt(2) * 0.01   # at least 40 dB down


def test_resample_upsamples_and_identity():
    import eval_common as E
    x = np.random.default_rng(0).standard_normal(1600).astype(np.float32)
    assert np.array_equal(E.resample(x, 16000, 16000), x)
    assert len(E.resample(x, 16000, 32000)) == 3200


# ---------------------------------------------------------------- statistics
def test_wilson_known_values():
    import eval_common as E
    lo, hi = E.wilson(0, 10)
    assert lo == 0.0 and abs(hi - 0.2775) < 1e-3
    lo, hi = E.wilson(5, 10)
    assert abs(lo - 0.2366) < 1e-3 and abs(hi - 0.7634) < 1e-3
    assert E.wilson(0, 0) == [None, None]


def test_cluster_bootstrap_resamples_groups():
    import eval_common as E
    rng = np.random.default_rng(0)
    assert E.cluster_bootstrap([1, 0, 1], ["a", "a", "a"], rng) == [2 / 3, 2 / 3]
    # one big group all hits, three small groups all misses: the group bootstrap must be wide
    vals = [1] * 20 + [0, 0, 0]
    groups = ["big"] * 20 + ["x", "y", "z"]
    lo, hi = E.cluster_bootstrap(vals, groups, np.random.default_rng(1))
    assert lo < 0.2 and hi > 0.95


def test_ontology_descendants(aset):
    import eval_common as E
    onto = E.Ontology(aset[1])
    d = {onto.name[m] for m in onto.descendants(onto.id_of("Plucked string instrument"))}
    assert d == {"Plucked string instrument", "Guitar", "Acoustic guitar", "Sitar", "Zither"}
    with pytest.raises(KeyError):
        onto.id_of("Erhu")


# ---------------------------------------------------------------- features
def _fake_project_clips(proj, rows):
    import common as C
    cols = C.schema("clips")
    full = []
    for r in rows:
        p = proj / r["path"]
        write_tone(p, r["sr"], r["freq"], content=r.get("content"))
        full.append({"clip_id": r["clip_id"], "candidate_id": "fs:1", "instrument": r["instrument"],
                     "source_group": r["group"], "license_code": "by", "path": r["path"], "start_s": "0",
                     "duration_s": "10.0", "content_s": f"{r.get('content') or 10.0:.2f}", "sample_rate": str(r["sr"]),
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    C.write_csv(C.p("clips"), full, cols)
    return full


def test_extract_resamples_reorders_and_caches(proj, aset):
    import eval_common as E, features as F
    classes = E.load_classes(aset[0])
    rows = _fake_project_clips(proj, [
        {"clip_id": "erhu_a", "instrument": "erhu", "group": "freesound:a", "path": "data/clips/erhu/erhu_a.wav", "sr": 44100, "freq": 440},
        {"clip_id": "erhu_b", "instrument": "erhu", "group": "freesound:b", "path": "data/clips/erhu/erhu_b.wav", "sr": 48000, "freq": 660, "content": 6.0},
    ])
    be = FakeBackend(classes)
    out = F.extract(be, classes, "csvsha", log=lambda *a: None)
    assert be.seen_lengths == [160000, 160000]          # 10 s at 16 kHz from 44.1 and 48 kHz files
    meta, P, X, cs = F.load_features(out, ["erhu_a", "erhu_b"])
    assert meta["sample_rate"] == 16000 and meta["layer"] == "fake layer" and meta["resampler"] == E.RESAMPLER
    assert P.shape == (2, len(classes)) and X.shape == (2, 8)
    # fake output j is class n-1-j with increasing probability; in class-list order it must decrease
    assert np.all(np.diff(P[0]) < 0)
    assert cs.tolist() == [10.0, 6.0]
    assert out == proj / "data" / "features" / "beats" / be.checkpoint_sha256[:16]
    # rerun is a no-op
    F.extract(be, classes, "csvsha", log=lambda *a: None)
    assert len(be.seen_lengths) == 2
    # different class list hash for the same cache directory stops the run
    with pytest.raises(SystemExit):
        F.extract(be, classes, "othersha", log=lambda *a: None)


def test_extract_refuses_stale_cache(proj, aset):
    import common as C, eval_common as E, features as F
    classes = E.load_classes(aset[0])
    rows = _fake_project_clips(proj, [
        {"clip_id": "oud_a", "instrument": "oud", "group": "freesound:a", "path": "data/clips/oud/oud_a.wav", "sr": 32000, "freq": 300}])
    be = FakeBackend(classes)
    F.extract(be, classes, "s", log=lambda *a: None)
    rows[0]["sha256"] = "0" * 64
    C.write_csv(C.p("clips"), rows, C.schema("clips"))
    with pytest.raises(SystemExit, match="different clip"):
        F.extract(be, classes, "s", log=lambda *a: None)


def test_extract_rejects_mismatched_outputs(proj, aset):
    import eval_common as E, features as F
    classes = E.load_classes(aset[0])
    be = FakeBackend(classes)
    be.output_mids = be.output_mids[:-1]
    with pytest.raises(SystemExit, match="do not match"):
        F.extract(be, classes, "s", clips=[], log=lambda *a: None)


def test_beats_label_dict_both_directions():
    import features as F
    assert F.Beats._mids_from({"/m/b": 1, "/m/a": 0}) == ["/m/a", "/m/b"]
    assert F.Beats._mids_from({1: "/m/b", 0: "/m/a"}) == ["/m/a", "/m/b"]
    with pytest.raises(SystemExit):
        F.Beats._mids_from(None)


def test_backends_import_lazily():
    import subprocess
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import features, test1, test2_probe; "
            "bad = [m for m in ('torch', 'torchaudio', 'panns_inference', 'BEATs') if m in sys.modules]; "
            "sys.exit(f'imported at module load: {bad}' if bad else 0)")
    r = subprocess.run([sys.executable, "-c", code, str(REPO / "src")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------- Test 1
def _probs_for(classes, ranking):
    """A probability vector whose order is `ranking` (names), everything else lower."""
    names = [n for _, n in classes]
    p = np.full(len(names), 0.01)
    for r, n in enumerate(ranking):
        p[names.index(n)] = 0.99 - 0.05 * r
    return p


def test_config_labels_checked_against_fixture(proj, aset):
    import eval_common as E, test1
    rows = test1.check_config(E.load_classes(aset[0]), E.Ontology(aset[1]))
    assert rows and all(r["ok"] for r in rows), [r for r in rows if not r["ok"]]
    assert any(r["label"] == "Zither" and r["kind"] == "broad (proposed)" for r in rows)


def test_config_check_flags_unknown_label(tmp_path, proj):
    import eval_common as E, test1
    TREE_BAK = dict(TREE)
    try:
        TREE["Bowed string instrument"] = ["Violin"]       # wrong display name
        csvp, ontp = write_audioset(tmp_path / "bad")
    finally:
        TREE.clear()
        TREE.update(TREE_BAK)
    rows = test1.check_config(E.load_classes(csvp), E.Ontology(ontp))
    bad = {(r["instrument"], r["label"]) for r in rows if not r["ok"]}
    assert ("violin", "Violin, fiddle") in bad


def test_instrument_mask_excludes_music_genre_mood(proj, aset):
    import eval_common as E, test1
    classes, onto = E.load_classes(aset[0]), E.Ontology(aset[1])
    m = test1.instrument_mask(classes, onto)
    kept = {n for (_, n), k in zip(classes, m) if k}
    assert "Music" not in kept and "Musical instrument" not in kept and "Pop music" not in kept
    assert "Happy music" not in kept and "Speech" not in kept
    assert {"Sitar", "Violin, fiddle", "Plucked string instrument", "Drum"} <= kept
    with pytest.raises(SystemExit):
        test1.instrument_mask(classes, onto, excluded=("Not a label",))


def test_score_family_descendants_exact_broad_and_filter(proj, aset):
    import eval_common as E, test1
    classes, onto = E.load_classes(aset[0]), E.Ontology(aset[1])
    generic = ["Music", "Musical instrument", "Pop music", "Happy music", "Speech"]
    P = np.array([
        _probs_for(classes, generic + ["Sitar"]),                 # pipa 1: family hit only via descendant Sitar
        _probs_for(classes, generic + ["Snare drum", "Bass drum", "Tabla", "Drum", "Percussion"]),  # pipa 2: miss
        _probs_for(classes, ["Violin, fiddle", "Music"]),         # violin 1: exact + family (child only)
        _probs_for(classes, ["Music", "Flute", "Tabla", "Snare drum", "Bass drum", "Drum"]),     # violin 2: miss
        _probs_for(classes, ["Tabla", "Zither"]),                 # guzheng: broad Zither hit
    ])
    ids = ["p1", "p2", "v1", "v2", "g1"]
    labels = {"p1": "pipa", "p2": "pipa", "v1": "violin", "v2": "violin", "g1": "guzheng"}
    groups = {"p1": "a", "p2": "b", "v1": "c", "v2": "c", "g1": "d"}
    content = {c: 10.0 for c in ids}
    content["p2"] = 7.5
    imask = test1.instrument_mask(classes, onto)
    t, per = test1.score(ids, labels, groups, P, classes, onto, imask, 5, 13, content)
    assert per["p1"][0] == "Sitar"                                 # generic labels filtered out
    assert t["pipa"]["family_topk"]["hits"] == 1
    assert t["pipa"]["n_padded"] == 1 and t["pipa"]["n_source_groups"] == 2
    assert t["violin"]["exact_topk"]["hits"] == 1 and t["violin"]["family_topk"]["hits"] == 1
    assert t["guzheng"]["broad_topk"]["hits"] == 1 and t["guzheng"]["top1_mode"]["label"] == "Tabla"
    assert "exact_topk" not in t["pipa"] and "broad_topk" not in t["pipa"]
    # family@1: pipa p1 top-1 Sitar (hit), p2 top-1 Snare drum (miss); violin v1 hit, v2 top-1 Flute (miss);
    # guzheng top-1 Tabla misses at 1 though Zither is in the top 5
    assert t["pipa"]["family_top1"]["hits"] == 1 and t["violin"]["family_top1"]["hits"] == 1
    assert t["guzheng"]["family_top1"]["hits"] == 0 and t["guzheng"]["family_topk"]["hits"] == 1
    # unfiltered: generic labels fill the top 5 for pipa
    full = np.ones(len(classes), dtype=bool)
    t2, per2 = test1.score(ids, labels, groups, P, classes, onto, full, 5, 13, content)
    assert t2["pipa"]["family_topk"]["hits"] == 0 and t2["pipa"]["top1_mode"]["label"] == "Music"
    assert t2["violin"]["exact_topk"]["hits"] == 1
    assert t2["violin"]["exact_topk"]["boot95_groups"] == [0.5, 0.5]   # one source group: degenerate CI
    # no pooled "non-Western" key anywhere
    assert not any("western" in k.lower() for k in t)
    md = test1.render(t, "x")
    assert md.index("**chinese**") < md.index("**western**")


# ---------------------------------------------------------------- Test 2
def _synthetic_splits(n_train, n_test, classes=("erhu", "violin", "pipa"), sep=6.0, d=16, seed=0):
    rng = np.random.default_rng(seed)
    centers = {c: rng.standard_normal(d) * sep for c in classes}
    rows, emb = [], {}
    for c in classes:
        for side, n in (("train", n_train.get(c, 0)), ("test", n_test.get(c, 0))):
            for j in range(n):
                cid = f"{c}_{side}_{j}"
                g = f"{side}:{c}:{j // 2}"        # two clips per source group
                rows.append({"clip_id": cid, "instrument": c, "source_group": g, "split": side})
                emb[cid] = centers[c] + rng.standard_normal(d)
    return rows, emb


def test_numpy_logreg_separates_and_is_deterministic():
    import test2_probe as T
    rng = np.random.default_rng(0)
    X = np.vstack([rng.standard_normal((20, 5)) + 4, rng.standard_normal((20, 5)) - 4, rng.standard_normal((20, 5)) + [4, -4, 0, 0, 0]])
    y = np.repeat([0, 1, 2], 20)
    p1, impl = T.fit_predict(X, y, X, 3, impl="numpy")
    p2, _ = T.fit_predict(X, y, X, 3, impl="numpy")
    assert (p1 == y).mean() > 0.95 and np.array_equal(p1, p2) and impl.startswith("numpy")


def test_numpy_logreg_matches_sklearn_when_available():
    pytest.importorskip("sklearn")
    import test2_probe as T
    rng = np.random.default_rng(1)
    X = rng.standard_normal((60, 10))
    y = np.repeat([0, 1, 2], 20)
    X[y == 1] += 1.0
    X[y == 2] -= 1.0
    Xte = rng.standard_normal((200, 10))
    a, _ = T.fit_predict(X, y, Xte, 3, impl="numpy")
    b, _ = T.fit_predict(X, y, Xte, 3, impl="sklearn")
    assert (a == b).mean() > 0.97


def test_probe_missing_classes_and_counts(proj):
    import test2_probe as T
    rows, emb = _synthetic_splits({"erhu": 6, "violin": 25, "pipa": 25}, {"erhu": 4, "violin": 4, "pipa": 0})
    m = T.evaluate(rows, emb, seed=13, ks=(1, 5, 20), draws=3, impl="numpy")
    j = m["results"]["joint"]
    assert j["1"]["classes"] == ["erhu", "violin"] and j["1"]["missing"] == {"pipa": "no test clips"}
    assert "erhu" in j["20"]["missing"] and j["20"]["skipped"]
    assert m["split_counts"]["erhu"] == {"train_clips": 6, "test_clips": 4, "train_source_groups": 3, "test_source_groups": 2}
    r = j["5"]["per_class"]["erhu"]
    assert len(r["recall_per_draw"]) == 3 and r["n_test"] == 4 and r["recall_sd"] is not None
    assert m["probes"]["within_bowed"]["classes"] == ["erhu", "violin"]
    assert "within_plucked" not in m["probes"]          # pipa alone: its cousin has no clips here


def test_probe_fixed_main_class_set(proj):
    import test2_probe as T
    rows, emb = _synthetic_splits({"erhu": 12, "violin": 12, "pipa": 3}, {"erhu": 3, "violin": 3, "pipa": 2})
    m = T.evaluate(rows, emb, seed=13, ks=(1, 5, 10, 20), draws=2, impl="numpy", main_k=10)
    assert m["main_class_set"]["classes"] == ["erhu", "violin"]
    assert list(m["results"]["joint"]) == ["1", "5", "10"]                 # no k above main_k
    for k in ("1", "5", "10"):                                              # same classes at every k
        assert m["results"]["joint"][k]["classes"] == ["erhu", "violin"] and not m["results"]["joint"][k]["missing"]
    assert m["results"]["supp_joint"]["1"]["classes"] == ["erhu", "pipa", "violin"]
    assert "pipa" in m["results"]["supp_joint"]["5"]["missing"]
    assert list(m["results"]["supp_joint"]) == ["1", "5", "10", "20"]


def test_probe_separable_data_triggers_leakage_flag(proj):
    import test2_probe as T
    rows, emb = _synthetic_splits({c: 10 for c in ("erhu", "violin", "pipa")}, {c: 6 for c in ("erhu", "violin", "pipa")}, sep=20)
    m = T.evaluate(rows, emb, seed=13, ks=(1,), draws=3, impl="numpy")
    assert m["results"]["joint"]["1"]["per_class"]["erhu"]["recall_mean"] == 1.0
    assert any("joint k=1 erhu" in f for f in m["leakage_flags"])


def test_probe_noise_is_near_chance(proj):
    import test2_probe as T
    rows, emb = _synthetic_splits({c: 20 for c in ("erhu", "violin", "pipa")}, {c: 60 for c in ("erhu", "violin", "pipa")}, sep=0.0)
    m = T.evaluate(rows, emb, seed=13, ks=(5,), draws=5, impl="numpy")
    for c in ("erhu", "violin", "pipa"):
        assert m["results"]["joint"]["5"]["per_class"][c]["recall_mean"] < 0.7
    assert not m["leakage_flags"]


def test_draws_are_seeded_and_independent_of_class_set(proj):
    import test2_probe as T
    rows, _ = _synthetic_splits({"erhu": 12, "violin": 12}, {"erhu": 2, "violin": 2})
    from collections import defaultdict
    train = defaultdict(list)
    for r in rows:
        if r["split"] == "train":
            train[r["instrument"]].append(r["clip_id"])
    a = T.draw_train(train, "erhu", 5, 13, 0)
    assert a == T.draw_train(train, "erhu", 5, 13, 0)
    assert a != T.draw_train(train, "erhu", 5, 13, 1)
    assert len(set(a)) == 5 and all(x.startswith("erhu_train") for x in a)


def test_probe_refuses_group_on_both_sides(proj):
    import test2_probe as T
    rows, emb = _synthetic_splits({"erhu": 4, "violin": 4}, {"erhu": 2, "violin": 2})
    rows[-1]["source_group"] = rows[0]["source_group"]
    with pytest.raises(SystemExit, match="both sides"):
        T.evaluate(rows, emb, seed=13, ks=(1,), draws=2, impl="numpy")


def test_family_probes_add_cousins(proj):
    import test2_probe as T
    fp = T.family_probes(["erhu", "violin", "pipa", "oud", "charango", "acoustic_guitar", "guzheng", "qanun", "flute"])
    assert fp["within_bowed"] == ["erhu", "violin"]
    assert fp["within_plucked"] == ["acoustic_guitar", "charango", "oud", "pipa"]
    assert fp["within_zither"] == ["acoustic_guitar", "guzheng", "qanun"]
    assert "within_wind" not in fp


# ---------------------------------------------------------------- end to end on the pipeline fixture
def test_end_to_end_on_built_pipeline(built, aset):
    import common as C, eval_common as E, features as F, test1, test2_probe as T, validate
    classes = E.load_classes(aset[0])
    be = FakeBackend(classes)
    F.extract(be, classes, E.sha256_file(aset[0]), log=lambda *a: None)
    f1 = test1.run("beats", aset[0], aset[1])
    f2 = T.run("beats", impl="numpy")
    r1, r2 = json.loads(f1.read_text()), json.loads(f2.read_text())
    need = C.schema("results_required_keys")
    assert all(k in r1 for k in need) and all(k in r2 for k in need)
    assert r1["checkpoint_sha256"] == be.checkpoint_sha256 and r1["n_clips"] == len(E.usable_labels()) > 0
    assert set(r1["metrics"]["primary_instrument_nodes_only"]) == {"erhu", "violin"}
    assert r2["metrics"]["results"]["supp_joint"]["1"]["classes"] == ["erhu", "violin"]
    ok, rep = validate.run(["results"])
    assert ok, rep.errors
    # a second run writes a new file; nothing is overwritten
    f1b = test1.run("beats", aset[0], aset[1])
    assert f1b != f1 and f1.exists()
