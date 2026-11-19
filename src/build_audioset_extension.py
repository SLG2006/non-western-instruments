#!/usr/bin/env python3
"""Draft AudioSet extension: one ontology-style entry per target instrument.

  .venv/bin/python src/build_audioset_extension.py

For each target instrument in config/instruments.json: a name, a description in AudioSet's style, the
parent AudioSet class (the deepest of its configured family labels, or its broad label), the scope
decided in docs/label_guide.md, and this dataset's counts and example clip ids.

Ids use a project namespace (/nwi/<instrument>), not Freebase MIDs: none are invented. Descriptions are
checked claim by claim against the Wikipedia page given as citation_uri (2026-11-19). Scope comes from the
label guide table. Writes docs/audioset_extension_draft.json. The final
file belongs in config/ (a gate directory): the human moves it.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import eval_common as E  # noqa: E402
from eval_common import C  # noqa: E402
import validate  # noqa: E402

WIKI = "https://en.wikipedia.org/wiki/"
# Descriptions checked claim by claim against citation_uri on 2026-11-19 [V]; wording adjusted where the
# page did not support a claim (ney: no "rim-blown"; bombo: Argentine; siku: bamboo or cane; qanun: box zither,
# levers change pitch during playing; guzheng: no "board zither").
DESCRIPTION = {
    "erhu": ("Sounds of a two-stringed Chinese bowed fiddle with a small resonator covered in python skin, held "
             "upright, with the bow hair passing between the strings.", "Erhu"),
    "pipa": ("Sounds of a four-stringed Chinese plucked lute with a pear-shaped body and frets, held upright.", "Pipa"),
    "dizi": ("Sounds of a Chinese transverse flute, usually of bamboo, often fitted with a thin membrane over an "
             "extra hole that gives a buzzing timbre.", "Dizi_(instrument)"),
    "guzheng": ("Sounds of a Chinese plucked zither with many strings over movable bridges.", "Guzheng"),
    "charango": ("Sounds of a small Andean plucked instrument of the lute family with five courses of paired "
                 "strings.", "Charango"),
    "quena": ("Sounds of an Andean end-blown flute with a notch cut into the end, traditionally of cane or wood, "
              "with finger holes.", "Quena"),
    "siku": ("Sounds of an Andean panpipe (zampona) of bamboo or cane pipes, split across two rows played in "
             "alternation.", "Siku_(instrument)"),
    "bombo": ("Sounds of the bombo leguero, a double-headed Argentine folk drum traditionally made of a hollowed "
              "tree trunk with animal-skin heads, struck on the head and the wooden rim.", "Bombo_leg%C3%BCero"),
    "oud": ("Sounds of a short-necked, fretless, pear-shaped lute played with a plectrum, in Arab, Turkish and "
            "Persian music.", "Oud"),
    "ney": ("Sounds of an end-blown flute made of cane or giant reed, used in Arab, Turkish and Persian music.", "Ney"),
    "qanun": ("Sounds of a large trapezoidal box zither of Arab and Turkish music, plucked, with many courses of "
              "strings and small levers (mandals) that change a course's pitch during playing.", "Qanun_(instrument)"),
    "darbuka": ("Sounds of a single-headed goblet drum played with the fingertips and palms.", "Goblet_drum"),
}


def guide_rows():
    """instrument -> (accepted names, excludes) from the table in docs/label_guide.md."""
    out = {}
    for ln in (C.root() / "docs" / "label_guide.md").read_text(encoding="utf-8").split("\n"):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 7 and cells[0].isdigit():
            out[cells[1]] = (cells[4], cells[5])
    return out


BROAD = {"guzheng": "Zither", "qanun": "Zither", "darbuka": "Drum", "bombo": "Bass drum"}


def main():
    aset = C.root() / "data" / "audioset"
    onto = E.Ontology(aset / "ontology.json")
    ins = C.instruments()
    usable = validate.usable_clips()
    clips = {r["clip_id"]: r for r in C.read_csv(C.p("clips"))}
    guide = guide_rows()
    out = []
    for i, m in ins.items():
        if m["role"] != "target":
            continue
        fams = m["audioset_family"]
        parent = BROAD.get(i) or min(fams, key=lambda f: len(onto.descendants(onto.id_of(f))))  # most specific
        mine = sorted(c for c, lab in usable.items() if lab == i)
        out.append({
            "id": f"/nwi/{i}", "name": m["display"], "tradition": m["group"], "family": m["family"],
            "description": DESCRIPTION[i][0], "description_status": "checked against citation_uri 2026-11-19",
            "citation_uri": WIKI + DESCRIPTION[i][1],
            "parent_id": onto.id_of(parent), "parent_name": parent,
            "audioset_tier": m["audioset_tier"],
            "scope": {"accepted_names": guide[i][0], "excludes": guide[i][1], "source": "docs/label_guide.md"},
            "nwi_usable_clips": len(mine),
            "nwi_source_groups": len({clips[c]["source_group"] for c in mine}),
            "nwi_positive_examples": mine[:3],
        })
    f = C.root() / "docs" / "audioset_extension_draft.json"
    f.write_text(json.dumps({"note": "Ids are project-namespaced, not Freebase MIDs. Descriptions checked against "
                                     "citation_uri on 2026-11-19.",
                             "ontology_source": "data/audioset/ontology.json",
                             "ontology_sha256": E.sha256_file(aset / "ontology.json"),
                             "entries": out}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for e in out:
        print(f"{e['id']:16s} parent {e['parent_name']:28s} {e['parent_id']:10s} n={e['nwi_usable_clips']}")
    print("wrote", f)


if __name__ == "__main__":
    main()
