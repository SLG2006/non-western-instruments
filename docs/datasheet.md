# Datasheet: solo instrument clips, v1 (draft, 2026-11-19)

**What it is.** 10-second mono clips of solo playing for 12 instruments from three traditions (Chinese: erhu, pipa, dizi, guzheng; Andean: charango, quena, siku, bombo legüero; Middle Eastern: oud, ney, qanun, darbuka), two controls with their own AudioSet labels (sitar, tabla) and four Western cousins (violin, flute, acoustic guitar, snare drum). Built to measure frozen AudioSet models per instrument, not to train them.

**Size.** 806 clips cut; 432 usable (labeled solo and confident by ear) from 368 recordings and 159 uploaders. Per-instrument counts, splits, licenses and sources: `results/dataset/dataset_table.md`. 8 of 18 classes have fewer than 20 usable clips (pipa 7, bombo 5, siku 8, quena 11, qanun 14, oud 15, sitar 15, tabla 19).

**Sources.** Freesound (430 usable clips) and Wikimedia Commons (4). Search metadata retrieved 2026-11-16 (UTC). Freesound audio is the `preview-hq-ogg` preview for every class, not the original upload; Commons audio is the original file. Clips are stored at the source sample rate.

**Selection.** Searches by instrument name and variants (`config/instruments.json`). Kept only accepted licenses; dropped uploads whose Freesound `gen_ai_preference` is `no-gen-ai`; dropped recordings tagged as loops. Clip rule (`docs/label_guide.md`): the loudest 10 s windows, one per recording first, rotating across uploaders, at most 3 per recording, 12 per uploader, 60 per instrument. Recordings of 5 to 10 s are zero-padded to 10 s (75 usable clips; `content_s` gives real length).

**Labels.** One labeler (the author), by ear, in a blind queue that hides the searched instrument, grouped with up to three similar instruments. A clip's class is the instrument heard, which differs from the searched one for 74 pass-1 labels, 62 of them usable (e.g. 21 clips found as dizi were heard as Western flute). No audio model created or checked a label. Scope decisions (erhu excludes other huqin; ronroco and walaycho count as charango; bombo legüero only; Persian tombak excluded from darbuka; funeral and other rites rejected) are in `docs/label_guide.md`. Intra-rater self-agreement on a seeded 10% blind relabel: n = 92, raw 0.717, Cohen's kappa 0.65 (`labels/agreement.json`).

**Splits.** Train and test never share a source group (uploader), `data/splits.csv`.

**Licenses.** Usable clips: CC0 151, public domain 1, CC BY 191, CC BY-NC 91. Rejected by rule: ShareAlike, NoDerivatives, Sampling+. Each clip keeps its original license and needs a credit line noting that it was trimmed. Proposed release: metadata and labels under CC BY-NC. To confirm with the OU library.

**Known limits.** One labeler; solo recordings only; small n and few uploaders for several classes (ney: 25 clips from 6 uploaders); Freesound previews are lossy; uploaders are often not the performers, so one performer can appear under two uploaders; wind and hand-drum labels are the least stable (most pass-2 disagreements); the flute class mixes Western flute uploads with recordings uploaded as dizi, unevenly across the split (`docs/results_notes.md`); some recordings are amateur or practice material; tradition labels name where an instrument comes from, not the performer.

**Not included.** Polyphonic music, emotion or role annotations, CCMusic or any NoDerivatives audio. Audio files are not in the git repository.
