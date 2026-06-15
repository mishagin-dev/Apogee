#!/usr/bin/env python3
"""
SessionStart hook — auto-prime Apogee-managed projects.

For projects the user manages with Apogee, every session should begin with the
`/apogee:prime` slash command (which loads docs/apogee and the beads tracker
state). A hook cannot literally run a slash command, so this injects an
additionalContext directive telling the agent to run /apogee:prime first.

Trigger (the scaffold's invariant): a project is Apogee-managed iff it has BOTH a
`.beads/` directory AND a `docs/apogee/` directory, at the same repo root.

Scope: only `startup` and `clear` sessions — re-priming a resumed or compacted
session is redundant and noisy.

Fail-open: any parse/IO error exits 0 with no output, so session start is never
blocked.
"""

import json
import os
import sys

PRIME_DIRECTIVE = (
    "This is an Apogee-managed project (beads tracker detected). "
    "Before doing anything else, run the /apogee:prime command to load project "
    "context (docs/apogee and the beads tracker state)."
)

# Only auto-prime fresh sessions, not resumed/compacted ones.
ACTIVE_SOURCES = {"startup", "clear"}


def find_apogee_root(start: str) -> bool:
    """True if `start` or any ancestor is a Apogee project root."""
    dir_ = os.path.abspath(start)
    while True:
        beads = os.path.isdir(os.path.join(dir_, ".beads"))
        aictx = os.path.isdir(os.path.join(dir_, "docs", "apogee"))
        if beads and aictx:
            return True
        parent = os.path.dirname(dir_)
        if parent == dir_:
            return False
        dir_ = parent


def main() -> None:
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}

    source = data.get("source", "")
    if source not in ACTIVE_SOURCES:
        return

    cwd = data.get("cwd") or os.getcwd()
    if not os.path.isdir(cwd):
        return

    if not find_apogee_root(cwd):
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": PRIME_DIRECTIVE,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail-open: never block session start.
        pass
    sys.exit(0)
