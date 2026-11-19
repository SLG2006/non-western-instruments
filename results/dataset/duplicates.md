# Duplicate check on the 434 usable clips (2026-11-19)

Method: cosine similarity of BEATs and PANNs embeddings over all pairs; every pair above 0.97 (BEATs), and the
top cross-split pairs of both models, checked by waveform cross-correlation (resampled to 16 kHz when the rates
differ). A cross-correlation near 1 means the same audio.

## Same audio under two source groups (no leak: both copies on the same side of the split)
| clip A | clip B | xcorr | side | note |
|---|---|---|---|---|
| dizi_fs108242_0 (freesound:gorgoroth6669) | dizi_wc46272858_0 (commons:mx. granger) | 0.999 | test | Commons file credits Freesound user Gorgoroth6669 as author: a re-upload |
| sitar_wc88877956_0 (commons:computerhotline) | sitar_wc105114161_0 (commons:jacqke) | 0.992 | train | both are Samuel Corwin, "A Man Approaches with Bowed Sitar, Rishikesh". Both rejected by the author in v1.0.1 (bowed sitar excluded by the label guide); not in the release |

Effect: dizi test has 13 clips of which 2 are one recording. (v1.0.0 only: sitar train had 8 of which 2 were one recording.)
The dizi pair should share a split_group. Proposed for v1.1 (not applied; human decision): keep the Freesound
copy, drop the other, set split_group to the author.

## Near-identical takes from one uploader (same source group, same side)
| clip A | clip B | xcorr |
|---|---|---|
| snare_drum_fs34133_0 | snare_drum_fs34134_0 | 0.968 |
| snare_drum_fs371850_0 | snare_drum_fs371860_0 | 0.944 |
| qanun_fs115223_1 | qanun_fs115224_1 | 0.917 |

## Across the split
No pair across train and test exceeds 0.15 waveform cross-correlation among the most similar embedding pairs
(highest embedding cosine across the split: BEATs 0.966, PANNs 0.989; all checked pairs are different audio).
Same-performer-different-uploader cases with different recordings cannot be found this way.
