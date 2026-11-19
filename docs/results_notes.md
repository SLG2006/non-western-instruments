# Results notes (read before quoting any number)

Decided 2026-11-19. These are caveats and file pointers, not interpretation.

## Primary result files
| Test | PANNs CNN14 | BEATs |
|---|---|---|
| Test 1 (with family@1) | results/test1_panns_cnn14_20261119T065124Z.json | results/test1_beats_20261119T065131Z.json |
| Test 2 (with split composition) | results/test2_panns_cnn14_20261119T070343Z.json | results/test2_beats_20261119T070346Z.json |

Earlier files in results/ are kept and superseded: test1_*_20261119T0617/0639 (no family@1), test2_*_20261119T0651 (same probe numbers, no split composition).

Checkpoints and cited mAP: docs/model_metadata.md.

## Metric definitions (state in the report)
- Test 1 ranks instrument nodes only (descendants of "Musical instrument"); the all-527 ranking is the secondary table.
- Family hit: the top-level AudioSet family node (Plucked string instrument, Bowed string instrument, Wind instrument/woodwind, Percussion) or any descendant. One definition for all families. It is lenient: a wind clip predicted as Saxophone is a family hit.
- family@5 sits at 0.82 to 1.00 for every class in both models and does not separate classes. family@1 is the primary family metric.
- Exact label (controls and cousins) and broad label (guzheng, qanun to Zither; darbuka to Drum; bombo to Bass drum) are top-5.
- "Percussion" as a top-1 prediction counts as a family hit for the drum classes, though it names no instrument.
- Intervals: Wilson 95% in the tables. The cluster bootstrap over source groups is in the JSON; it degenerates with few groups (pipa: 3 groups gives 1.00 to 1.00), so quote it only for classes with about 8 or more source groups.
- Test 2 main probes: fixed set of 11 classes (rule: at least 10 train clips and a test clip) at k = 1, 5, 10; chance 0.09 joint. Within-family probes use the same set. Logistic regression, L2, C = 1.0 fixed, standardized on the k training clips. 10 seeded draws. Probes named supp_* use all classes at k = 1, 5, 10, 20 with classes dropping out where they run short; they hold k = 20 (acoustic_guitar, flute, violin only) and the small classes.
- k = 1 standard deviations reach 0.38. Read k = 5 and k = 10.

## Caveat: flute and dizi (Test 2)
The flute class mixes Western flute uploads with recordings uploaders called dizi that the labeler heard as flute. The uploader-disjoint split put almost all of the second kind in test:

| class | split | cut as flute | cut as dizi |
|---|---|---|---|
| flute | train | 23 | 1 |
| flute | test | 4 | 20 |
| dizi | train | 3 | 9 |
| dizi | test | 3 | 10 |

Source: split_composition_by_cut_instrument in the Test 2 files. Low flute probe recall (PANNs 0.16, BEATs 0.44 at k = 10, joint) is better explained by this train/test composition shift and by label instability (pass-2 flips among flute, dizi, ney, quena) than by the models. Flute is not a clean cousin for dizi, quena and ney in Test 2. Decision: keep this split as the primary run (no re-split after seeing results); footnote the wind rows. Test 1 does not train, so it is not affected by the split, but the flute class composition is the same.

## Other limits to list
- One labeler. Intra-rater self-agreement on a seeded 10% blind relabel: n = 92, raw 0.717, Cohen's kappa 0.65 (labels/agreement.json). Of 26 disagreements: 13 within one family (winds 7, drums 3, bowed 2, oud vs qanun 1); 3 across families (violin to ney, ney to erhu, acoustic_guitar to flute); 9 reject vs instrument; 1 instrument vs unsure. Siku has no clip in the relabel sample.
- 8 of 18 classes are below 20 usable clips: pipa 7, siku 8, bombo 5, quena 11, qanun 14, oud 15, sitar 17, tabla 19 (labels/summary.json). Report their Test 1 rows with n; they are outside the main Test 2 set.
- Middle East kept although oud and qanun fall short (CLAUDE.md fallback rule): West African searches returned fewer real candidates (ngoni 0, kora about 6, tambin 0; djembe 104).
- Few uploaders in some classes: ney 25 clips from 6 source groups; qanun 5; pipa 3.
- Padding (checked for Test 1). 75 of 434 usable clips are zero-padded to 10 s; flute has 21 of 48 (results/dataset/dataset_table.md). Test 1 rerun without them: results/test1_unpadded_panns_cnn14_20261119T071500Z.json and results/test1_unpadded_beats_20261119T071501Z.json. Shares that move outside the full-run Wilson interval: guzheng broad@5 (Zither) rises from 0.60 to 0.78 (PANNs) and 0.80 to 0.94 (BEATs) when its 7 padded clips are dropped; guzheng family@5 (BEATs) 0.96 to 1.00; siku family@1 and family@5 0.88 to 1.00 in both models (n 8 to 5; its one miss was a padded clip). Every other share, including every exact@5 row and every cousin, stays inside its interval. Report the guzheng and siku rows with both values. Test 2 has not been rerun without padded clips.
- 6 clips are stored at 16 or 22.05 kHz and are upsampled for PANNs (32 kHz).
- Freesound previews (preview-hq-ogg) for every class, not originals.
- Ceremonial recordings excluded by rule (label guide).
