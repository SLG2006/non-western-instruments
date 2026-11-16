#!/usr/bin/env python3
"""PostToolUse and SubagentStop hook: the real-time feedback loop.

After an Edit, Write or Bash call it re-validates every stage whose files
changed since the last check and, on failure, sends the errors back to the
agent (exit 2). On SubagentStop it runs the stages that agent owns, so an agent
cannot finish on output that fails its gate.
"""
import io, json, os, sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
os.environ.setdefault("NWI_ROOT", str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C
import validate as V

STATE = ROOT / ".claude" / ".gate_state.json"
OWNED = {"scout": ["candidates"], "curator": ["candidates", "approved"], "clipper": ["approved", "clips"],
         "label-desk": ["clips", "queue", "labels"], "eval-engineer": ["labels", "splits", "results"],
         "scribe": ["results"], "gatekeeper": []}


def stage_files(stage):
    if stage == "candidates":
        d = C.p("candidates_dir")
        return sorted(d.glob("*.csv")) if d.exists() else []
    if stage == "results":
        d = C.p("results_dir")
        return sorted(d.glob("*.json")) if d.exists() else []
    f = C.p(stage)
    return [f] if f.exists() else []


def fingerprint(stage):
    return [[f.name, f.stat().st_mtime_ns, f.stat().st_size] for f in stage_files(stage)]


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(passed):
    """Remember only stages that passed, so a failing stage is re-checked next time."""
    state = load_state()
    state.update({s: fingerprint(s) for s in passed})
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state))


def changed_stages():
    old = load_state()
    return [s for s in V.STAGES if fingerprint(s) and fingerprint(s) != old.get(s)]


def main():
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    if event.get("hook_event_name") == "SubagentStop":
        if event.get("stop_hook_active"):
            sys.exit(0)  # already blocked once; do not loop
        stages = [s for s in OWNED.get(event.get("agent_type", ""), []) if stage_files(s)]
    else:
        stages = changed_stages()
    if not stages:
        sys.exit(0)
    failed, out = [], []
    for s in stages:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = V.main(["--stage", s])
        if code != 0:
            failed.append(s)
            out.append(buf.getvalue())
    save_state([s for s in stages if s not in failed])
    if failed:
        print("GATE FAILED. Fix the stage output (do not edit the checks):\n" + "".join(out), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
