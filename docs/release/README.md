# NWI solo instrument clips, v1.0.1

Human-labeled 10-second solo clips of 12 instruments from three traditions, two control instruments and four Western cousins, built to measure how AudioSet-trained audio models handle instruments that AudioSet does not name.

| Tradition | Instruments |
|---|---|
| Chinese | erhu, pipa, dizi, guzheng |
| Andean | charango, quena, siku, bombo legüero |
| Middle Eastern | oud, ney, qanun, darbuka |
| Controls (own AudioSet label) | sitar, tabla |
| Western cousins | violin, flute, acoustic guitar, snare drum |

432 clips from 368 recordings and 159 uploaders (Freesound and Wikimedia Commons). Per-instrument counts, splits, licenses and sources are in `dataset_table.md`. Eight classes have fewer than 20 clips (pipa 7, bombo 5, siku 8, quena 11, qanun 14, oud 15, sitar 15, tabla 19). Report results per instrument and per tradition; do not average the traditions into one "non-Western" number.

## Files
| File | What it holds |
|---|---|
| `audio/<instrument>/<clip_id>.wav` | the clips: mono, 16-bit WAV, 10 s, at the source sample rate |
| `metadata.csv` | one row per clip: label, tradition, family, split, source, author, license, excerpt window, padding, checksum, the uploader's Freesound generative-AI preference, credit line |
| `credits.csv`, `CREDITS.md` | the credit line for every clip |
| `labels_pass1.csv` | the label for every clip that was cut (806), including rejected clips whose audio is not released |
| `labels_pass2.csv` | the blind relabel of a seeded 10% sample, for self-agreement |
| `agreement.json` | intra-rater agreement: n = 92, raw 0.717, Cohen's kappa 0.65 |
| `splits.csv` | train and test split; no uploader is on both sides |
| `audioset_extension.json` | one AudioSet-style entry per target instrument, with its AudioSet parent class |
| `LABEL_GUIDE.md` | accepted names, exclusions and labeling decisions |
| `DATASHEET.md` | sources, selection, labeling, licenses, known limits |
| `duplicates.md` | duplicate audio found in the release and its effect |
| `SHA256SUMS` | checksums of every file |

## How the labels were made
One labeler (the author) labeled every clip by ear in a blind queue that hid the instrument the clip was searched under. A clip's label is the instrument heard. 74 labels differ from the searched instrument; for example, 21 clips found as dizi were heard as Western flute. `searched_as` in `metadata.csv` keeps the search instrument. No audio model created or checked a label.

## Known limits
One labeler. Solo recordings only. Few uploaders for several classes. Freesound audio comes from the lossy preview. Wind and hand-drum labels are the least stable. The flute class mixes Western flute uploads with recordings uploaded as dizi. 75 clips are short recordings zero-padded to 10 s (`padded`, `content_s`). One recording appears twice under different uploaders (`duplicates.md`). See `DATASHEET.md`.

## Changes from v1.0.0
The two clips of a bowed sitar recording (sitar_wc88877956_0, sitar_wc105114161_0) were rejected under the label guide, which excludes bowed sitar: 434 to 432 clips, sitar 17 to 15. The label guide's exclusions were confirmed and its ney and siku notes reworded. Every other clip, label and split is unchanged.

## Uploader preferences
Freesound lets uploaders state a preference on generative-AI use. Uploads marked `no-gen-ai` were excluded. 10 clips come from uploaders who allow only noncommercial open-source models and 9 from uploaders who allow open-source models (`gen_ai_preference` in `metadata.csv`); respect these if you train generative models.

## License
See `LICENSE.md`. Labels, metadata and splits: CC BY-NC 4.0. Each audio clip keeps the license its author chose (CC0 1.0, public domain, CC BY 3.0 or 4.0, CC BY-NC 3.0 or 4.0) and must be credited with its line in `credits.csv`.

## AI-use statement
Data retrieval, preprocessing and evaluation code were developed with AI agents under author review. All labels were assigned by the author by listening. No audio model was used to create or check labels.

## Code
https://github.com/SLG2006/non-western-instruments

## Cite
León Garavito, S. (2026). NWI solo instrument clips (v1.0.1) [Data set]. Zenodo. DOI: to be added on deposit.
