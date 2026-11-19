# nonwestern-instruments

Pipeline and agent team for the Fall 2026 project "Mapping the Gap: Non-Western Instruments in
AudioSet-Trained Models" (OU NLP Lab). Project rules for agents are in `CLAUDE.md`.

## One-time setup (on the Mac)
1. `brew install ffmpeg` if you don't have it.
2. `bash setup.sh` creates `.venv`, installs numpy and pytest, creates `.env`, copies the agent team from `agent-setup/claude` to `.claude` and the CI workflow to `.github`, and runs the tests.
3. Open `.env` and paste your Freesound API key. Add an email or URL as `NWI_CONTACT`.
4. `git init && git add -A && git commit -m "Pipeline scaffold"`, then create a private GitHub repo and push.
5. On GitHub, protect `main`: require a pull request and the `gates` check.

## Daily loop
Start Claude Code in this folder (`claude`) and ask for agents by name.

| Step | Who | Command or request |
|---|---|---|
| 1 | scout | "Use the scout agent for erhu" (`scripts/scout.py --instrument erhu`) |
| 2 | curator | "Use the curator agent" (`scripts/curate.py`) |
| 3 | **you** | Decide flagged licenses: add `candidate_id,decision,note` rows to `data/human_decisions.csv`, then re-run curator |
| 4 | clipper | "Use the clipper agent for erhu" (`scripts/clip.py --instrument erhu`) |
| 5 | label-desk | "Use the label-desk agent" (builds `labels/queue.csv`) |
| 6 | **you** | `python3 scripts/label_tool.py` in your own terminal. Blind by default. Quit with `q`, resume any time |
| 7 | label-desk | Run again after pass 1 is complete: it builds the blind 10% re-label queue. Repeat step 6, then ask for agreement |
| 8 | eval-engineer | Builds and runs Test 1 and Test 2 (needs `pip install -r requirements-eval.txt` and the checkpoints) |
| 9 | scribe | Drafts `report/report.md` from `results/` |
| any | gatekeeper | "Use the gatekeeper agent" after each stage and before each merge |

## Files and who writes them
| File | Written by |
|---|---|
| `data/candidates/<instrument>.csv` | `scripts/scout.py` |
| `data/approved.csv`, `data/flags.csv`, `data/rejected.csv` | `scripts/curate.py` |
| `data/human_decisions.csv` | **you only** |
| `data/raw/` (git-ignored, immutable), `data/clips/` (git-ignored), `data/clips_manifest.csv` | `scripts/clip.py` |
| `labels/queue.csv`, `labels/agreement.json`, `labels/summary.json` | `scripts/label_desk.py` |
| `labels/labels.csv` | **you only**, through `scripts/label_tool.py` |
| `data/splits.csv` | `scripts/make_splits.py` |
| `results/*.json` | eval code in `src/` |

## Gates
`python3 scripts/validate.py --all` checks every stage. The same checks run automatically after each
agent action (`scripts/hooks/post_gate.py`) and when an agent finishes. `scripts/hooks/guard.py` blocks
agents from touching your labels, your license decisions, `.env`, raw data, and the checks themselves.
To edit a gate file inside Claude Code yourself, start it with `NWI_ALLOW_GATE_EDITS=1 claude`.

## Settings you own
- `config/licenses.json`: CC BY-SA is in `needs_human` until Dr. Cao decides. Move it to `accept` or `reject`.
- `config/instruments.json`: search terms, families, Western cousins, AudioSet labels. Items marked "Confirm" are proposals.
- `config/pipeline.json`: clip length, sample rate, caps, minimum clips, re-label fraction, seed.

## Known limits
- Clips come from Freesound HQ previews (MP3) and Commons originals, decoded to 32 kHz mono WAV.
- Recordings of 5 to 10 s are padded with silence to 10 s; `content_s` records the real length.
- An instrument whose clips all come from one uploader cannot be split and fails the splits gate.
