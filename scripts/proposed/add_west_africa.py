"""Human-run config edit: add four West African instruments for a scouting comparison, and the tag:oud query.

Run from the repo root:  python3 scripts/proposed/add_west_africa.py
role "scouting" marks them as not yet part of the dataset. Each matches a Middle Eastern slot by family.
"""
import json

p = "config/instruments.json"
d = json.load(open(p, encoding="utf-8"))
ids = {i["id"] for i in d["instruments"]}

oud = next(i for i in d["instruments"] if i["id"] == "oud")
if not any(isinstance(q, dict) for q in oud["freesound_queries"]):
    oud["freesound_queries"].append({"query": "oud", "filter": "tag:oud"})

new = [
    {"id": "ngoni", "display": "ngoni", "group": "west_africa", "role": "scouting", "family": "plucked",
     "cousin": "acoustic_guitar", "audioset_tier": 3, "audioset_exact": None,
     "audioset_family": ["Plucked string instrument"],
     "freesound_queries": ["ngoni", "n'goni", "xalam", "kamele ngoni", "donso ngoni"],
     "commons_queries": ["ngoni", "xalam"], "commons_categories": ["Category:Ngoni"],
     "commons_title_regex": "ngoni|n'goni|xalam|khalam",
     "note": "West Africa fallback for oud (lute slot). Scouting only."},
    {"id": "kora", "display": "kora", "group": "west_africa", "role": "scouting", "family": "plucked",
     "cousin": "acoustic_guitar", "audioset_tier": 3, "audioset_exact": None,
     "audioset_family": ["Plucked string instrument"],
     "freesound_queries": ["kora harp", "kora solo", "kora mandinka", {"query": "kora", "filter": "tag:kora"}],
     "commons_queries": ["kora harp", "kora music"], "commons_categories": ["Category:Kora (instrument)"],
     "commons_title_regex": "(^|[^a-z])kora([^a-z]|$)",
     "note": "West Africa fallback for qanun (many-string plucked slot; kora is a harp-lute, not a zither). Bare 'kora' is a common word; tag filter used. Scouting only."},
    {"id": "tambin", "display": "tambin (Fula flute)", "group": "west_africa", "role": "scouting", "family": "wind",
     "cousin": "flute", "audioset_tier": 3, "audioset_exact": None,
     "audioset_family": ["Flute", "Wind instrument, woodwind instrument"],
     "freesound_queries": ["fula flute", "tambin", "peul flute", "serdu", "fulani flute"],
     "commons_queries": ["fula flute", "tambin"], "commons_categories": [],
     "commons_title_regex": "fula|tambin|peul|serdu|fulani",
     "note": "West Africa fallback for ney (flute slot). Scouting only."},
    {"id": "djembe", "display": "djembe", "group": "west_africa", "role": "scouting", "family": "drum",
     "cousin": "snare_drum", "audioset_tier": 2, "audioset_exact": None,
     "audioset_family": ["Drum", "Percussion"],
     "freesound_queries": ["djembe", "djembé", "jembe"],
     "commons_queries": ["djembe"], "commons_categories": ["Category:Djembe"],
     "commons_title_regex": "dj?embe|djembé",
     "note": "West Africa fallback for darbuka (hand-played goblet drum). Scouting only."},
]
for inst in new:
    if inst["id"] not in ids:
        d["instruments"].append(inst)

open(p, "w", encoding="utf-8").write(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
print("added:", [i["id"] for i in new if i["id"] not in ids], "| oud tag query present")
