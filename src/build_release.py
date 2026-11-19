#!/usr/bin/env python3
"""Build the dataset v1 release folder and zip (local only; the human uploads).

  .venv/bin/python src/build_release.py [--version 1.0.0] [--dry-run]

Release content (decided 2026-11-19): audio for the usable clips only (human pass-1 label, solo, confident);
labels for all cut clips; split licensing (labels, metadata and splits under CC BY-NC 4.0; each clip keeps
its original license and carries a credit line that says it was changed). Output:

  data/release/nwi-solo-v<version>/   audio/<instrument>/<clip_id>.wav, metadata.csv, credits.csv, CREDITS.md,
                                      labels_pass1.csv, labels_pass2.csv, splits.csv, README.md, DATASHEET.md,
                                      LABEL_GUIDE.md, LICENSE.md, audioset_extension.json, agreement.json,
                                      duplicates.md, SHA256SUMS
  data/release/nwi-solo-v<version>.zip and .zip.sha256
  data/release/zenodo_metadata.json   draft deposit metadata

Never writes outside data/release/. Refuses to overwrite an existing version folder.
"""
import argparse, csv, glob, hashlib, json, shutil, sys, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from eval_common import C  # noqa: E402
import validate  # noqa: E402

PADDED_BELOW = 9.995
LICENSE_BY_URL = {  # license_raw (Freesound URL or Commons short name) -> (name, canonical URL)
    "creativecommons.org/licenses/by/4.0": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "creativecommons.org/licenses/by/3.0": ("CC BY 3.0", "https://creativecommons.org/licenses/by/3.0/"),
    "creativecommons.org/licenses/by-nc/4.0": ("CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/"),
    "creativecommons.org/licenses/by-nc/3.0": ("CC BY-NC 3.0", "https://creativecommons.org/licenses/by-nc/3.0/"),
    "creativecommons.org/publicdomain/zero/1.0": ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
}
LICENSE_BY_NAME = {"CC BY 4.0": LICENSE_BY_URL["creativecommons.org/licenses/by/4.0"],
                   "CC0": LICENSE_BY_URL["creativecommons.org/publicdomain/zero/1.0"],
                   "Public domain": ("Public domain", "")}


def license_of(raw):
    key = raw.split("://", 1)[-1].rstrip("/")
    if key in LICENSE_BY_URL:
        return LICENSE_BY_URL[key]
    if raw in LICENSE_BY_NAME:
        return LICENSE_BY_NAME[raw]
    raise SystemExit(f"unmapped license {raw!r}: add it to LICENSE_BY_URL before releasing")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def credit_line(r):
    changes = (f"Changed: {r['content_s']} s excerpt from {r['start_s']} s"
               + (", zero-padded to 10 s" if r["padded"] == "yes" else "")
               + f", mixed to mono, saved as 16-bit WAV"
               + (" (decoded from the Freesound preview, lossy OGG)" if r["source"] == "freesound" else "") + ".")
    if r["license_name"] == "CC0 1.0":
        lic_text = f"dedicated to the public domain under CC0 1.0 ({r['license_url']})"
    elif r["license_name"] == "Public domain":
        lic_text = "in the public domain"
    else:
        lic_text = f"licensed under {r['license_name']} ({r['license_url']})"
    return f"\"{r['title']}\" by {r['author']} ({r['source_url']}), {lic_text}. {changes}"


def build(version, dry_run=False):
    root = C.root()
    out = root / "data" / "release" / f"nwi-solo-v{version}"
    if out.exists():
        raise SystemExit(f"{out} exists; pick a new --version (releases are never overwritten)")
    ins = C.instruments()
    usable = validate.usable_clips()
    clips = {r["clip_id"]: r for r in C.read_csv(C.p("clips"))}
    split = {r["clip_id"]: r for r in C.read_csv(C.p("splits"))}
    cand = {}
    for f in sorted(glob.glob(str(root / "data" / "candidates" / "*.csv"))):
        for r in C.read_csv(f):
            cand.setdefault(r["candidate_id"], r)
    wc = {r["candidate_id"]: r for r in C.read_csv(root / "data" / "commons_authors.csv")}
    missing_wc = sorted({clips[c]["candidate_id"] for c in usable if clips[c]["candidate_id"].startswith("wc:")} - set(wc))
    if missing_wc:
        raise SystemExit(f"Commons author metadata missing for {missing_wc}: run scripts/scout.py --commons-authors")
    if set(usable) != set(split):
        raise SystemExit("data/splits.csv does not match the usable labels")

    rows = []
    for c in sorted(usable):
        m, k = clips[c], cand[clips[c]["candidate_id"]]
        src = "freesound" if m["candidate_id"].startswith("fs:") else "commons"
        if src == "commons":
            a = wc[m["candidate_id"]]
            author = a["artist"] or a["uploader"]
            name, url = license_of(a["license_short"] or k["license_raw"])
            if a["license_url"]:
                url = a["license_url"]
        else:
            author = k["uploader"]
            name, url = license_of(k["license_raw"])
        lab = usable[c]
        start, content = float(m["start_s"]), float(m["content_s"])
        r = {"clip_id": c, "file": f"audio/{lab}/{c}.wav", "instrument": lab, "tradition": ins[lab]["group"],
             "role": ins[lab]["role"], "family": ins[lab]["family"], "searched_as": m["instrument"],
             "split": split[c]["split"], "split_group": m["source_group"],
             "source": src, "source_id": m["candidate_id"], "source_url": k["source_url"], "title": k["title"],
             "author": author, "uploader": k["uploader"], "license_code": m["license_code"],
             "license_name": name, "license_url": url, "start_s": f"{start:.3f}",
             "end_s": f"{start + content:.3f}", "content_s": f"{content:.2f}",
             "padded": "yes" if content < PADDED_BELOW else "no", "sample_rate": m["sample_rate"],
             "channels": "1", "format": "WAV PCM 16-bit", "sha256": m["sha256"],
             "gen_ai_preference": k.get("gen_ai_preference", "")}
        r["attribution"] = credit_line(r)
        rows.append(r)

    lic_count = {}
    for r in rows:
        lic_count[r["license_name"]] = lic_count.get(r["license_name"], 0) + 1
    print(f"{len(rows)} clips; licenses {lic_count}")
    if dry_run:
        print(f"[dry-run] would write {out}")
        return
    (out / "audio").mkdir(parents=True)
    for r in rows:
        dst = out / r["file"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / clips[r["clip_id"]]["path"], dst)
        if sha256(dst) != r["sha256"]:
            raise SystemExit(f"checksum mismatch after copy: {r['clip_id']}")

    def write(name, rs, cols):
        with open(out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rs)

    write("metadata.csv", rows, list(rows[0]))
    write("credits.csv", rows, ["clip_id", "file", "title", "author", "source_url", "license_name", "license_url",
                                 "attribution"])
    labels = C.read_csv(C.p("labels"))
    lab_cols = ["clip_id", "searched_as", "pass", "label", "solo", "confident", "labeled_at", "audio_released"]
    for ps in ("1", "2"):
        write(f"labels_pass{ps}.csv",
              [{**l, "searched_as": clips[l["clip_id"]]["instrument"],
                "audio_released": "yes" if l["clip_id"] in usable else "no"}
               for l in sorted(labels, key=lambda x: x["clip_id"]) if l["pass"] == ps], lab_cols)
    write("splits.csv", sorted(C.read_csv(C.p("splits")), key=lambda x: x["clip_id"]),
          ["clip_id", "instrument", "source_group", "split"])
    with open(out / "CREDITS.md", "w", encoding="utf-8") as f:
        f.write("# Credits\n\nEvery clip is an excerpt of a recording by the author named below. The clips were "
                "changed as stated in each line.\n\n")
        for r in rows:
            f.write(f"- `{r['clip_id']}`: {r['attribution']}\n")
    for src, dst in [("docs/datasheet.md", "DATASHEET.md"), ("docs/label_guide.md", "LABEL_GUIDE.md"),
                     ("docs/audioset_extension_draft.json", "audioset_extension.json"),
                     ("labels/agreement.json", "agreement.json"), ("results/dataset/duplicates.md", "duplicates.md"),
                     ("results/dataset/dataset_table.md", "dataset_table.md")]:
        shutil.copy2(root / src, out / dst)
    for name in ("README.md", "LICENSE.md"):
        shutil.copy2(root / "docs" / "release" / name, out / name)
    sums = sorted(p for p in out.rglob("*") if p.is_file())
    (out / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.relative_to(out)}\n" for p in sums), encoding="utf-8")
    z = out.parent / (out.name + ".zip")  # not with_suffix: the version has dots
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                zf.write(p, Path(out.name) / p.relative_to(out))
    (z.parent / (z.name + ".sha256")).write_text(f"{sha256(z)}  {z.name}\n", encoding="utf-8")
    shutil.copy2(root / "docs" / "release" / "zenodo_metadata.json", out.parent / "zenodo_metadata.json")
    print(f"wrote {out} ({len(sums)} files) and {z} ({z.stat().st_size / 1e6:.1f} MB)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    build(a.version, a.dry_run)


if __name__ == "__main__":
    main()
