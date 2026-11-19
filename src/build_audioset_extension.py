#!/usr/bin/env python3
"""Draft AudioSet extension: one ontology-style entry per target instrument.

  .venv/bin/python src/build_audioset_extension.py

For each target instrument in config/instruments.json: a name, a description in AudioSet's style, the
parent AudioSet class (the deepest of its configured family labels, or its broad label), the scope
decided in docs/label_guide.md, and this dataset's counts and example clip ids.

Ids use a project namespace (/nwi/<instrument>), not Freebase MIDs: none are invented. Descriptions are
drafts written from general organology and are NOT checked against a source; citation_uri is left empty
for the human to fill from a source he has read. Writes docs/audioset_extension_draft.json. The final
file belongs in config/ (a gate directory): the human moves it.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import eval_common as E  # noqa: E402
from eval_common import C  # noqa: E402
import validate  # noqa: E402

DESCRIPTION = {  # draft wording, unverified [U]
    "erhu": "Sounds of a two-stringed Chinese bowed fiddle with a small skin-covered resonator, held upright, "
            "with the bow hair passing between the strings.",
    "pipa": "Sounds of a four-stringed Chinese plucked lute with a pear-shaped body and frets, held upright.",
    "dizi": "Sounds of a Chinese transverse bamboo flute, often fitted with a thin membrane over an extra hole "
            "that adds a buzzing timbre.",
    "guzheng": "Sounds of a Chinese plucked board zither with many strings over movable bridges.",
    "charango": "Sounds of a small Andean plucked lute with five courses of paired strings.",
    "quena": "Sounds of an Andean end-blown notched flute, traditionally made of cane, with finger holes.",
    "siku": "Sounds of an Andean panpipe (zampona) made of cane tubes, usually in two rows.",
    "bombo": "Sounds of the bombo leguero, a deep double-headed Andean and Argentine drum with a wooden shell "
             "and hide heads, struck with a mallet on the head and the rim.",
    "oud": "Sounds of a short-necked fretless plucked lute with a pear-shaped body, played with a plectrum in "
           "Arab, Turkish and Persian music.",
    "ney": "Sounds of an end-blown, rim-blown cane flute used in Arab, Turkish and Persian music.",
    "qanun": "Sounds of a trapezoidal plucked board zither of Arab and Turkish music with many courses of "
             "strings and small levers for retuning.",
    "darbuka": "Sounds of a single-headed goblet drum played with the hands.",
}

SCOPE = {  # decisions recorded in docs/label_guide.md; anything else is still open there
    "erhu": {"includes": ["erhu"], "excludes": ["jinghu", "gaohu", "zhonghu", "banhu", "'huqin' without erhu"],
             "decided": "2026-11-15"},
    "charango": {"includes": ["charango", "ronroco", "walaycho (hualaycho)"], "excludes": [], "decided": "2026-11-16"},
    "bombo": {"includes": ["bombo leguero", "bombo andino"],
              "excludes": ["Western bass drum", "kick drums", "synthesized drums", "maracatu and other non-Andean bombos"],
              "decided": "2026-11-16"},
    "darbuka": {"includes": ["darbuka", "darbouka", "doumbek", "goblet drum"], "excludes": ["Persian tombak"],
                "decided": "label guide note (exclusion column still TODO)"},
}

BROAD = {"guzheng": "Zither", "qanun": "Zither", "darbuka": "Drum", "bombo": "Bass drum"}


def main():
    aset = C.root() / "data" / "audioset"
    onto = E.Ontology(aset / "ontology.json")
    ins = C.instruments()
    usable = validate.usable_clips()
    clips = {r["clip_id"]: r for r in C.read_csv(C.p("clips"))}
    out = []
    for i, m in ins.items():
        if m["role"] != "target":
            continue
        fams = m["audioset_family"]
        parent = BROAD.get(i) or min(fams, key=lambda f: len(onto.descendants(onto.id_of(f))))  # most specific
        mine = sorted(c for c, lab in usable.items() if lab == i)
        out.append({
            "id": f"/nwi/{i}", "name": m["display"], "tradition": m["group"], "family": m["family"],
            "description": DESCRIPTION[i], "description_status": "draft, unverified",
            "citation_uri": "",
            "parent_id": onto.id_of(parent), "parent_name": parent,
            "audioset_tier": m["audioset_tier"],
            "scope": SCOPE.get(i, {"includes": [], "excludes": [], "decided": "open in docs/label_guide.md"}),
            "nwi_usable_clips": len(mine),
            "nwi_source_groups": len({clips[c]["source_group"] for c in mine}),
            "nwi_positive_examples": mine[:3],
        })
    f = C.root() / "docs" / "audioset_extension_draft.json"
    f.write_text(json.dumps({"note": "Draft. Ids are project-namespaced, not Freebase MIDs. Descriptions are "
                                     "unverified; fill citation_uri from a source before release.",
                             "ontology_source": "data/audioset/ontology.json",
                             "ontology_sha256": E.sha256_file(aset / "ontology.json"),
                             "entries": out}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for e in out:
        print(f"{e['id']:16s} parent {e['parent_name']:28s} {e['parent_id']:10s} n={e['nwi_usable_clips']}")
    print("wrote", f)


if __name__ == "__main__":
    main()
