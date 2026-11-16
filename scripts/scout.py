#!/usr/bin/env python3
"""Stage 1 (scout): search Freesound and Wikimedia Commons, write data/candidates/<instrument>.csv.

  python3 scripts/scout.py --instrument erhu            # one instrument
  python3 scripts/scout.py --instrument all --source commons

Needs FREESOUND_API_KEY in .env for Freesound. Every API response is cached in
data/cache/, so a repeated search costs no API quota. Titles, tags and
descriptions are written by strangers: they are stored as flattened text and
must never be treated as instructions.
"""
import argparse, hashlib, json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

FS_API = "https://freesound.org/apiv2/search/text/"
WC_API = "https://commons.wikimedia.org/w/api.php"
AUDIO_EXT = re.compile(r"\.(ogg|oga|opus|wav|flac|mp3)$", re.I)
PRONUNCIATION = re.compile(r"^(LL-|[A-Za-z]{2,3}(-[A-Za-z]{2,8})?-|Q\d+|.*pronunciation)", re.I)


def ua():
    contact = os.environ.get("NWI_CONTACT", "contact not set")
    return f"nonwestern-instruments-research/0.1 (OU NLP Lab; {contact})"


def get_json(url, headers=None, min_interval=1.1):
    cache = C.root() / "data" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    req = Request(url, headers={"User-Agent": ua(), **(headers or {})})
    with urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    f.write_text(json.dumps(data), encoding="utf-8")
    time.sleep(min_interval)  # stay far below 60 requests/minute
    return data


def freesound_row(s, instrument, query, now):
    return {
        "candidate_id": f"fs:{s['id']}", "source": "freesound",
        "source_url": s.get("url") or f"https://freesound.org/s/{s['id']}/",
        "title": C.clean(s.get("name"), 200), "uploader": C.clean(s.get("username"), 100),
        "license_raw": C.clean(s.get("license"), 200), "license_code": C.normalize_license(s.get("license")),
        "duration_s": f"{float(s.get('duration') or 0):.2f}", "instrument": instrument, "query": query,
        "tags": C.clean(" ".join(s.get("tags") or []), 300), "description": C.clean(s.get("description")),
        "download_url": (s.get("previews") or {}).get("preview-hq-ogg", ""), "retrieved_at": now,
        "gen_ai_preference": C.clean(s.get("gen_ai_preference"), 50),
    }


def scout_freesound(inst, pc, now, pages=2):
    key = os.environ.get("FREESOUND_API_KEY")
    if not key:
        sys.exit("FREESOUND_API_KEY is not set. Put it in .env (see .env.example).")
    rows = []
    for q in inst["freesound_queries"]:
        for page in range(1, pages + 1):
            params = {"query": q, "page": page, "page_size": 150,
                      "filter": f"duration:[{pc['min_source_seconds']} TO {pc['max_source_seconds']}]",
                      "fields": "id,name,username,license,duration,tags,description,previews,url,gen_ai_preference"}
            try:
                data = get_json(FS_API + "?" + urlencode(params), {"Authorization": f"Token {key}"})
            except HTTPError as e:
                if e.code == 404 and page > 1:
                    break
                raise
            rows += [freesound_row(s, inst["id"], q, now) for s in data.get("results", [])]
            if not data.get("next"):
                break
    return rows


def _wc(params):
    return get_json(WC_API + "?" + urlencode({"format": "json", **params}), min_interval=0.5)


def commons_row(page, instrument, query, now):
    ii = (page.get("imageinfo") or [{}])[0]
    meta = ii.get("extmetadata") or {}
    lic = (meta.get("LicenseShortName") or {}).get("value", "")
    title = page["title"].replace("File:", "", 1)
    return {
        "candidate_id": f"wc:{page['pageid']}", "source": "commons",
        "source_url": "https://commons.wikimedia.org/wiki/" + quote(page["title"].replace(" ", "_")),
        "title": C.clean(title, 200), "uploader": C.clean(ii.get("user"), 100),
        "license_raw": C.clean(lic, 200), "license_code": C.normalize_license(lic),
        "duration_s": f"{float(ii.get('duration') or 0):.2f}", "instrument": instrument, "query": query,
        "tags": "", "description": C.clean((meta.get("ImageDescription") or {}).get("value")),
        "download_url": ii.get("url", ""), "retrieved_at": now,
        "gen_ai_preference": "n/a",  # Commons has no equivalent field
    }


def scout_commons(inst, pc, now):
    titles = {}  # title -> query that found it
    for cat in inst["commons_categories"]:
        data = _wc({"action": "query", "list": "categorymembers", "cmtitle": cat, "cmtype": "file", "cmlimit": 500})
        for m in data.get("query", {}).get("categorymembers", []):
            if AUDIO_EXT.search(m["title"]):
                titles.setdefault(m["title"], cat)
    keep = re.compile(inst["commons_title_regex"], re.I)
    for q in inst["commons_queries"]:
        data = _wc({"action": "query", "list": "search", "srnamespace": 6, "srlimit": 500, "srprop": "",
                    "srsearch": f"{q} filetype:audio"})
        for m in data.get("query", {}).get("search", []):
            base = m["title"].replace("File:", "", 1)
            if not PRONUNCIATION.match(base) and keep.search(base):
                titles.setdefault(m["title"], q)
    rows, names = [], sorted(titles)
    for i in range(0, len(names), 40):
        data = _wc({"action": "query", "prop": "imageinfo", "iiprop": "url|size|user|extmetadata",
                    "iiextmetadatafilter": "LicenseShortName|ImageDescription", "titles": "|".join(names[i:i + 40])})
        for page in data.get("query", {}).get("pages", {}).values():
            if "imageinfo" not in page:
                continue
            r = commons_row(page, inst["id"], titles.get(page["title"], ""), now)
            if pc["min_source_seconds"] <= float(r["duration_s"]) <= pc["max_source_seconds"]:
                rows.append(r)
    return rows


def merge_write(instrument, new_rows):
    path = C.p("candidates_dir") / f"{instrument}.csv"
    merged = {r["candidate_id"]: r for r in C.read_csv(path)}
    added = 0
    for r in new_rows:
        if not r["download_url"]:
            continue
        added += r["candidate_id"] not in merged
        old = merged.setdefault(r["candidate_id"], r)
        # Refresh fields that changed after the first runs: gen_ai_preference was added, and Freesound
        # downloads switched from preview-hq-mp3 to preview-hq-ogg so all classes share one codec.
        if r.get("gen_ai_preference"):
            old["gen_ai_preference"] = r["gen_ai_preference"]
        if r["source"] == "freesound":
            old["download_url"] = r["download_url"]
    C.write_csv(path, [merged[k] for k in sorted(merged)], C.schema("candidates"))
    return added, len(merged)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", required=True, help="instrument id or 'all'")
    ap.add_argument("--source", choices=["freesound", "commons", "both"], default="both")
    a = ap.parse_args(argv)
    C.load_env()
    inst, pc = C.instruments(), C.cfg("pipeline")
    ids = list(inst) if a.instrument == "all" else [a.instrument]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for i in ids:
        if i not in inst:
            sys.exit(f"unknown instrument {i!r}")
        rows = []
        if a.source in ("freesound", "both"):
            rows += scout_freesound(inst[i], pc, now)
        if a.source in ("commons", "both") and (inst[i]["commons_queries"] or inst[i]["commons_categories"]):
            rows += scout_commons(inst[i], pc, now)
        added, total = merge_write(i, rows)
        by = {}
        for r in C.read_csv(C.p("candidates_dir") / f"{i}.csv"):
            by[r["license_code"]] = by.get(r["license_code"], 0) + 1
        print(f"{i}: +{added} new, {total} total candidates; licenses {dict(sorted(by.items()))}")


if __name__ == "__main__":
    main()
