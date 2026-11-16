"""Shared helpers. Standard library only, so hooks run on any python3."""
import csv, json, os, re
from pathlib import Path


def root() -> Path:
    env = os.environ.get("NWI_ROOT")
    return Path(env).resolve() if env else Path(__file__).resolve().parents[1]


def cfg(name: str) -> dict:
    return json.loads((root() / "config" / f"{name}.json").read_text(encoding="utf-8"))


def schema(stage: str) -> list:
    return json.loads((root() / "schemas" / "stages.json").read_text(encoding="utf-8"))[stage]


def instruments() -> dict:
    return {i["id"]: i for i in cfg("instruments")["instruments"]}


def label_vocab() -> set:
    c = cfg("instruments")
    return {i["id"] for i in c["instruments"]} | set(c["label_extras"])


PATHS = {
    "candidates_dir": "data/candidates",
    "approved": "data/approved.csv",
    "flags": "data/flags.csv",
    "rejected": "data/rejected.csv",
    "human_decisions": "data/human_decisions.csv",
    "clips": "data/clips_manifest.csv",
    "queue": "labels/queue.csv",
    "labels": "labels/labels.csv",
    "splits": "data/splits.csv",
    "results_dir": "results",
}


def p(key: str) -> Path:
    return root() / PATHS[key]


def read_csv(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def csv_header(path) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return next(csv.reader(f), [])


def write_csv(path, rows, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})
    tmp.replace(path)


def load_env():
    """Read KEY=VALUE lines from .env into os.environ (without overriding)."""
    f = root() / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def clean(text, limit=300) -> str:
    """Metadata from Freesound/Commons is untrusted data: flatten and truncate it."""
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def normalize_license(raw: str) -> str:
    s = str(raw or "").lower().strip()
    if not s:
        return "unknown"
    if "sampling" in s:
        return "sampling+"
    if "publicdomain/zero" in s or re.match(r"^cc[ -]?0", s) or "creative commons 0" in s:
        return "cc0"
    if "public domain" in s or "publicdomain/mark" in s or re.match(r"^pd([ -]|$)", s):
        return "pd"
    m = re.search(r"(?:licenses/|cc[ -])(by(?:-nc)?(?:-sa|-nd)?)(?:[/ ]|$)", s)
    if m:
        return m.group(1)
    if s.startswith("attribution"):
        t = s.replace("-", "").replace(" ", "")
        code = "by"
        if "noncommercial" in t:
            code += "-nc"
        if "sharealike" in t:
            code += "-sa"
        if "noderiv" in t:
            code += "-nd"
        return code
    return "other"
