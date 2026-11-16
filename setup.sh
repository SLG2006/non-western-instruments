#!/usr/bin/env bash
# One-time setup on your Mac. Run from the project folder:  bash setup.sh
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "python3 not found. Install it from python.org or with Homebrew."; exit 1; }
command -v ffmpeg  >/dev/null || { echo "ffmpeg not found. Install it with:  brew install ffmpeg"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
[ -f .env ] || cp .env.example .env
# Install the agent team and CI config (kept in agent-setup/ until you run this).
[ -d .claude ] || cp -R agent-setup/claude .claude
[ -d .github ] || cp -R agent-setup/github .github
mkdir -p data/candidates labels results report src checkpoints
.venv/bin/pytest -q
echo
echo "Setup done. Next: open .env and paste your Freesound API key after FREESOUND_API_KEY="
