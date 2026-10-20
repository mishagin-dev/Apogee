#!/usr/bin/env python3
"""
UserPromptSubmit hook — remind about unfinished feature/bugfix branches.

The one reminder about branch hygiene left after ADR 0005 removed the one-branch-at-a-time
gate. It fires at the moment -- a new user message arrives while an open branch
already exists (e.g. work was left mid-flight in a prior session) -- so the agent surfaces it to
the user before deciding what to do next, rather than silently starting fresh work on top.

Safe by design: it only NUDGES (additionalContext), never blocks. Capped at LIMIT times per
session so it never nags forever once the agent has acknowledged it. Part of the apogee plugin.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from gitflow_common import is_gitflow_repo, get_prefixes, open_work_branches  # noqa: E402

LIMIT = 3


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    sid = payload.get("session_id", "unknown")

    if not is_gitflow_repo(cwd):
        sys.exit(0)

    prefixes = get_prefixes(cwd)
    open_branches = open_work_branches(cwd, prefixes)
    if not open_branches:
        sys.exit(0)

    count_path = f"/tmp/gitflow-nudge-{sid}.count"
    try:
        n = int(open(count_path).read().strip())
    except Exception:
        n = 0
    if n >= LIMIT:
        sys.exit(0)  # stop nagging
    try:
        with open(count_path, "w") as f:
            f.write(str(n + 1))
    except Exception:
        pass

    merged = [(t, s) for t, s, m in open_branches if m]
    unfinished = [(t, s) for t, s, m in open_branches if not m]

    parts = []
    if merged:
        names = ", ".join(f"{t}/{s}" for t, s in merged)
        parts.append(
            f"Branch(es) candidate for cleanup (fully merged into develop already, likely via a "
            f"manual merge rather than `git flow ... finish`): {names}. Close them with /apogee:finish (it sees there is nothing left to merge and just deletes the branch)."
        )
    if unfinished:
        names = ", ".join(f"{t}/{s}" for t, s in unfinished)
        parts.append(
            f"Unfinished branch(es) still open: {names}. Close it first with /apogee:finish."
        )
    directive = (
        " ".join(parts)
        + " Mention this to the user before starting new work -- unless the user's new request "
        "is genuinely more urgent or higher-priority than what's open, in which case proceed but "
        "say so explicitly."
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": directive,
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
