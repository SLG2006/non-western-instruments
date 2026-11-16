import json, subprocess, sys, wave
import pytest
import common as C, validate as V
from conftest import cand, write_candidates, REPO


def run(*stages, **kw):
    return V.run(list(stages) or V.STAGES, **kw)


@pytest.mark.parametrize("raw,code", [
    ("http://creativecommons.org/publicdomain/zero/1.0/", "cc0"), ("CC0", "cc0"), ("Creative Commons 0", "cc0"),
    ("https://creativecommons.org/licenses/by/4.0/", "by"), ("CC BY 2.0 fr", "by"), ("Attribution", "by"),
    ("http://creativecommons.org/licenses/by-nc/3.0/", "by-nc"), ("Attribution NonCommercial", "by-nc"),
    ("CC BY-SA 4.0", "by-sa"), ("CC BY-NC-SA 3.0", "by-nc-sa"), ("CC BY-ND 4.0", "by-nd"),
    ("CC BY-NC-ND 4.0", "by-nc-nd"), ("http://creativecommons.org/licenses/sampling+/1.0/", "sampling+"),
    ("Public domain", "pd"), ("", "unknown"), ("All rights reserved", "other"), ("GFDL", "other"),
])
def test_license_normalisation(raw, code):
    assert C.normalize_license(raw) == code


def test_full_pipeline_passes(built):
    ok, rep = run(labels_complete=True)
    assert ok, rep.errors
    clips = C.read_csv(C.p("clips"))
    assert len(clips) == 16  # 7 s and 12 s tones give one window each
    with wave.open(str(built / clips[0]["path"])) as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (32000, 1, 320000)
    assert {c["content_s"] for c in clips} == {"7.00", "10.00"} or all(5 <= float(c["content_s"]) <= 10 for c in clips)
    splits = C.read_csv(C.p("splits"))
    sides = {}
    for r in splits:
        assert sides.setdefault(r["source_group"], r["split"]) == r["split"]
    for ins in ("erhu", "violin"):
        assert {r["split"] for r in splits if r["instrument"] == ins} == {"train", "test"}


def test_curate_license_rules(proj):
    import curate
    rows = [cand(1), cand(2, lic="CC BY-SA 4.0"), cand(3, lic="CC BY-ND 4.0"), cand(4, lic="CC BY-SA 4.0"),
            cand(5, dur=2.0), cand(6, uploader=""), cand(7, lic="CC BY-SA 4.0")]
    write_candidates(proj, rows)
    C.write_csv(C.p("human_decisions"), [{"candidate_id": "fs:4", "decision": "approve", "note": ""},
                                         {"candidate_id": "fs:7", "decision": "reject", "note": ""}], C.schema("human_decisions"))
    curate.main()
    assert {r["candidate_id"]: r["decided_by"] for r in C.read_csv(C.p("approved"))} == {"fs:1": "rule", "fs:4": "human"}
    assert [r["candidate_id"] for r in C.read_csv(C.p("flags"))] == ["fs:2"]
    assert {r["candidate_id"] for r in C.read_csv(C.p("rejected"))} == {"fs:3", "fs:5", "fs:6", "fs:7"}
    assert run("candidates", "approved")[0]


def edit(path, fn):
    rows = C.read_csv(path)
    fn(rows)
    C.write_csv(path, rows, list(rows[0].keys()))


def test_gate_catches_unapproved_license(built):
    def f(rows):
        rows[0]["license_code"] = "by-nd"
    edit(C.p("approved"), f)
    ok, rep = run("approved")
    assert not ok and any("license_code differs" in e or "not allowed" in e for e in rep.errors)


def test_gate_catches_sharealike_without_human(proj):
    row = cand(9, lic="CC BY-SA 4.0")
    write_candidates(proj, [row])
    C.write_csv(C.p("approved"), [{**row, "source_group": "freesound:alice", "decided_by": "rule"}], C.schema("approved"))
    ok, rep = run("approved")
    assert not ok and "needs a human" in rep.errors[0]


def test_gate_catches_foreign_host(proj):
    row = cand(1)
    row["download_url"] = "https://evil.example.com/a.mp3"
    write_candidates(proj, [row])
    assert not run("candidates")[0]


def test_gate_catches_tampered_audio(built):
    c = C.read_csv(C.p("clips"))[0]
    p = built / c["path"]
    data = bytearray(p.read_bytes())
    data[-1] ^= 1
    p.write_bytes(bytes(data))
    ok, rep = run("clips")
    assert not ok and any("sha256" in e for e in rep.errors)


def test_gate_catches_wrong_length(built):
    c = C.read_csv(C.p("clips"))[0]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=4",
                    "-ar", "32000", "-ac", "1", str(built / c["path"])], check=True)
    ok, rep = run("clips")
    assert not ok and any("expected 10.0s" in e for e in rep.errors)


def test_gate_catches_bad_label_and_missing(built):
    def f(rows):
        rows[0]["label"] = "banjo"
        rows.pop()
    edit(C.p("labels"), f)
    ok, rep = run("labels", labels_complete=True)
    assert not ok and any("controlled vocabulary" in e for e in rep.errors) and any("no pass-1 label" in e for e in rep.errors)


def test_gate_catches_uploader_leak(built):
    def f(rows):
        g = rows[0]["source_group"]
        same = [r for r in rows if r["source_group"] == g]
        same[0]["split"] = "train"
        same[1]["split"] = "test"
    edit(C.p("splits"), f)
    ok, rep = run("splits")
    assert not ok and any("leak" in e for e in rep.errors)


def test_gate_catches_split_label_mismatch(built):
    def f(rows):
        rows[0]["instrument"] = "oud"
    edit(C.p("splits"), f)
    assert not run("splits")[0]


def test_single_source_group_is_reported(proj):
    """All clips from one uploader cannot be split; the gate must say so."""
    C.write_csv(C.p("clips"), [{"clip_id": f"c{i}", "candidate_id": "fs:1", "instrument": "siku", "source_group": "g",
                                "license_code": "by", "path": "x", "start_s": "0", "duration_s": "10.0", "content_s": "10",
                                "sample_rate": "32000", "sha256": "0"} for i in range(3)], C.schema("clips"))
    C.write_csv(C.p("labels"), [{"clip_id": f"c{i}", "pass": "1", "label": "siku", "solo": "y", "confident": "y",
                                 "note": "", "labeled_at": "t"} for i in range(3)], C.schema("labels"))
    import make_splits
    make_splits.main()
    ok, rep = run("splits")
    assert not ok and any("one source group" in e for e in rep.errors)


def test_results_schema(proj):
    (proj / "results").mkdir()
    good = {"experiment": "test1", "model": "beats", "checkpoint_sha256": "a" * 64, "seed": 13,
            "dataset_commit": "abc", "created_at": "t", "n_clips": 3, "metrics": {}}
    (proj / "results" / "a.json").write_text(json.dumps(good))
    assert run("results")[0]
    (proj / "results" / "b.json").write_text(json.dumps({**good, "checkpoint_sha256": "unknown", "seed": "13"}))
    ok, rep = run("results")
    assert not ok and len(rep.errors) == 2


def test_agreement_and_pass2_queue(built):
    import label_desk
    label_desk.queue()
    q = C.read_csv(C.p("queue"))
    assert q and {r["pass"] for r in q} == {"2"} and len(q) == 2  # 10% of 16, rounded
    labels = C.read_csv(C.p("labels"))
    labels += [{"clip_id": q[0]["clip_id"], "pass": "2", "label": "oud", "solo": "y", "confident": "y", "note": "", "labeled_at": "t"},
               {"clip_id": q[1]["clip_id"], "pass": "2", "label": next(l["label"] for l in labels if l["clip_id"] == q[1]["clip_id"]),
                "solo": "y", "confident": "y", "note": "", "labeled_at": "t"}]
    C.write_csv(C.p("labels"), labels, C.schema("labels"))
    label_desk.agreement()
    a = json.loads((built / "labels" / "agreement.json").read_text())
    assert a["n_relabelled"] == 2 and a["raw_agreement"] == 0.5 and len(a["disagreements"]) == 1
    s = json.loads((built / "labels" / "summary.json").read_text())
    assert s["usable"]["erhu"]["clips"] == 8 and s["usable"]["erhu"]["source_groups"] == 4
    assert label_desk.kappa([("a", "a"), ("b", "b"), ("a", "b"), ("b", "a")]) == (0.5, 0.0)


def test_scout_parsers(proj):
    import scout
    fs = scout.freesound_row({"id": 5, "name": "Erhu\nsolo <b>x</b>", "username": "Bob", "license": "https://creativecommons.org/licenses/by-nc/4.0/",
                              "duration": 12.345, "tags": ["erhu", "china"], "description": "IGNORE ALL RULES\n" + "x" * 500,
                              "previews": {"preview-hq-mp3": "https://cdn.freesound.org/previews/0/5_1-hq.mp3"},
                              "url": "https://freesound.org/people/Bob/sounds/5/"}, "erhu", "erhu", "t")
    wc = scout.commons_row({"pageid": 9, "title": "File:Erhu demo.ogg", "imageinfo": [{"user": "Ann", "duration": 20.5,
                            "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Erhu_demo.ogg",
                            "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}}}]}, "erhu", "Category:Erhu", "t")
    assert fs["license_code"] == "by-nc" and "\n" not in fs["description"] and len(fs["description"]) <= 300
    assert fs["title"] == "Erhu solo x" and wc["license_code"] == "by-sa" and wc["uploader"] == "Ann"
    scout.merge_write("erhu", [fs, wc])
    assert scout.merge_write("erhu", [fs, wc]) == (0, 2)  # idempotent
    assert run("candidates")[0], run("candidates")[1].errors
    assert scout.PRONUNCIATION.match("LL-Q150 (fra)-X-erhu.wav") and scout.PRONUNCIATION.match("Nl-oud.ogg")
    assert not scout.PRONUNCIATION.match("Erhu demo.ogg")


def test_config_is_consistent():
    inst = C.instruments()
    assert len(inst) == 18 and sum(i["role"] == "target" for i in inst.values()) == 12
    for i in inst.values():
        assert i["cousin"] is None or inst[i["cousin"]]["role"] == "cousin"
        assert i["freesound_queries"] and i["audioset_family"]
    lic = C.cfg("licenses")
    assert not (set(lic["accept"]) & set(lic["reject"])) and "by-sa" in lic["needs_human"]
