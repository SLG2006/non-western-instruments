# Model metadata (results notes)

Checkpoints live in `checkpoints/` (not tracked). Each results file in `results/` records the sha256 below.

| Model | File | Bytes | sha256 |
|---|---|---|---|
| BEATs | BEATs_iter3_plus_AS2M_finetuned_on_AS2M_cpt2.pt | 363145291 | e5815275a04b6885e7b8af63d120b29bffae2cd2225cf4915e1ec6d819d3022c |
| PANNs CNN14 | Cnn14_mAP=0.431.pth | 327428481 | 0dc499e40e9761ef5ea061ffc77697697f277f6a960894903df3ada000e34b31 |

## BEATs (primary)
- Checkpoint (as written in the README table): Fine-tuned BEATs_iter3+ (AS2M) (cpt2)
- Source row, README "Comparing with the SOTA Single Models" image (= Table 1, Chen et al., ICML 2023, arXiv:2212.09058):

  | Model         | # Param | Data | AS-2M | AS-20K | ESC-50 | KS1  | KS2  | ER   |
  |---------------|---------|------|-------|--------|--------|------|------|------|
  | BEATs_iter3+  | 90M     | AS   | 48.6  | 38.9   | 98.1*  | 98.1*| 98.1*| 65.0*|

  *greyed out in the source table (additional supervised training on external data); not used here.

- Cite: 48.6 mAP on AudioSet-2M, best single-model result reported for BEATs_iter3+.
- Not cpt2-specific: the README and paper report one single-model number per iteration and do not score cpt1 and cpt2 separately.
- Ensemble rows (Table 3), NOT to be cited for our model: BEATs (5 models) 50.4; BEATs (10 models) 50.6.
- The 50.6 on the lab slide is the 10-model ensemble. Do not reuse it for this checkpoint.
- [V] checked against the unilm/beats README on 2026-11-19

## PANNs CNN14 (secondary)
- Checkpoint: Cnn14_mAP=0.431.pth (Zenodo record 3987831, linked from the README)
- Source row, README "Performance of different systems" table image (AudioSet tagging, Kong et al., IEEE/ACM TASLP 2020, arXiv:1912.10211):

  | Model | mAP   | AUC   | d-prime |
  |-------|-------|-------|---------|
  | CNN14 | 0.431 | 0.973 | 2.732   |

- README text: "Our CNN14 achieves an mAP of 0.431, and Wavegram-Logmel-CNN achieves an mAP of 0.439."
- Cite: 0.431 mAP on the AudioSet evaluation set (single model, 32 kHz CNN14).
- Do not confuse with Cnn14_16k_mAP=0.438.pth, which the README says was "Trained by a later code version, achieves higher mAP than the paper."
- [V] checked against the qiuqiangkong/audioset_tagging_cnn README on 2026-11-19

## Feature settings (from data/features/<model>/<sha>/meta.json)
- Both models: clips resampled at load time with one windowed-sinc resampler (src/eval_common.py); zero padding to 10 s kept as audio.
- PANNs CNN14: 32 kHz; embedding = 2048-d fc1 output after ReLU (penultimate); the model's own clip-level pooling.
- BEATs: 16 kHz; embedding = 768-d final-layer features, mean over all frames (padded frames included).
