"""Human-run gate edit: copy the AudioSet extension into config/ (agents cannot write config/).

Run from the repo root:  python3 scripts/proposed/install_audioset_extension.py

Copies docs/audioset_extension_draft.json to config/audioset_extension.json. Refuses to overwrite.
Descriptions were checked against their citation_uri (Wikipedia) on 2026-11-19; read them once before running.
"""
import json
from pathlib import Path

src, dst = Path("docs/audioset_extension_draft.json"), Path("config/audioset_extension.json")
if dst.exists():
    raise SystemExit(f"{dst} exists; not overwritten")
d = json.loads(src.read_text(encoding="utf-8"))
assert len(d["entries"]) == 12 and all(e["citation_uri"] for e in d["entries"]), "expected 12 entries with citations"
dst.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {dst}: {len(d['entries'])} entries")
