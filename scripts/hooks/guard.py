#!/usr/bin/env python3
"""PreToolUse hook. Blocks (exit 2) tool calls that touch human-only or gate files.

Human-only: labels/labels.csv, data/human_decisions.csv, .env
Gate files: config/, schemas/, scripts/validate.py, scripts/hooks/, scripts/label_tool.py, .claude/settings.json
Immutable:  data/raw/
The human can lift the gate-file block for one session with NWI_ALLOW_GATE_EDITS=1.
"""
import json, os, re, sys
from pathlib import Path

HUMAN_ONLY = ["labels/labels.csv", "data/human_decisions.csv", ".env"]
GATE = ["config/", "schemas/", "scripts/validate.py", "scripts/hooks/", "scripts/label_tool.py",
        "scripts/common.py", ".claude/settings.json", ".github/"]
IMMUTABLE = ["data/raw/"]
BASH_BLOCK = [
    (r"labels\.csv|human_decisions\.csv|(^|[\s/'\"=])\.env(?![.\w])", "names a human-only file"),
    (r"label_tool\.py", "label_tool.py is run by the human only"),
    (r"(^|[;&|(\s])(sudo\s+)?(rm|rmdir|shred|unlink)\s", "deleting files is not allowed"),
    (r"git\s+(push|reset\s+--hard|clean)\b", "git push/reset --hard/clean is done by the human"),
    (r"(^|[;&|(\s])(curl|wget|ssh|scp|nc)\s", "network access goes through scripts/scout.py and scripts/clip.py only"),
    (r"NWI_ALLOW_GATE_EDITS", "only the human sets NWI_ALLOW_GATE_EDITS"),
    (r"(>|>>|tee\s+(-a\s+)?|sed\s+-i\S*\s.*|mv\s.*|cp\s.*)\s*\S*(config/|schemas/|scripts/validate\.py|scripts/hooks/|\.claude/settings|data/raw/)",
     "writes to a gate or immutable file"),
]


def rel(path, root):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return None


def decide(event, root):
    tool, ti = event.get("tool_name", ""), event.get("tool_input") or {}
    if tool == "Bash":
        cmd = ti.get("command", "")
        for pattern, why in BASH_BLOCK:
            if re.search(pattern, cmd):
                return f"Blocked: this command {why}."
        return None
    path = ti.get("file_path") or ti.get("notebook_path")
    if not path:
        return None
    r = rel(path if os.path.isabs(path) else os.path.join(event.get("cwd") or root, path), root)
    if r is None:
        return "Blocked: edits outside the project folder are not allowed."
    if r in HUMAN_ONLY:
        return f"Blocked: {r} is written by the human only."
    if any(r.startswith(x) for x in IMMUTABLE):
        return f"Blocked: {r} is immutable raw data."
    if any(r == x or r.startswith(x) for x in GATE) and os.environ.get("NWI_ALLOW_GATE_EDITS") != "1":
        return f"Blocked: {r} is a gate file. Report the problem to the human instead of changing the check."
    return None


def main():
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    root = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parents[2])
    msg = decide(event, root)
    if msg:
        print(msg, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
