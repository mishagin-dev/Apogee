#!/usr/bin/env python3
"""
PostToolUse hook (matcher: ExitPlanMode): capture an approved plan into br, then hand off
execution to /apogee:run-plan in git-flow repos instead of the agent implementing by hand.

When a plan is approved (ExitPlanMode), inject a directive telling the agent to record the plan in
beads_rust BEFORE editing code — create an epic + child steps. This is context, not enforcement:
nothing blocks an agent that ignores it (ADR 0005 removed the edit/branch/progress gates that used
to). In a git-flow repo, the directive then hands off to /apogee:run-plan rather than telling the
agent to open the branch and claim the first step itself: approving a plan already IS the user's
go-ahead to execute it to completion, and run-plan owns that whole lifecycle (branch per epic,
claim/close each step, review/docs/test steps, finish, loop) with no per-step confirmation.

Scope: GLOBAL hook, self-gates to beads projects (a `.beads/` dir above cwd). No-op elsewhere.
Fail-open: any error → no output.
"""

import json
import os
import sys

DIRECTIVE = (
    "A plan was just approved. Before editing any code, RECORD it in beads_rust (br): "
    "create an epic (`br create \"<feature>\" -t epic --slug <id> --json`) and one child step per "
    "task (`br create \"<step>\" -t task --parent <epicId> -l <repo> [--deps blocks:<id>] --json`), "
    "then run `br dep cycles` (must be empty). "
    "IF this repo is git-flow (has `gitflow.*` config): do NOT start the branch or claim a step "
    "yourself -- invoke /apogee:run-plan instead. It owns the whole execution lifecycle (opening "
    "the branch per epic, claiming/closing each step, the review/docs/test steps, finishing into "
    "develop, looping to the next ready epic) with no per-step confirmation; only `git push` and "
    "the release/hotfix lifecycle stay manual. State briefly that you're handing off to "
    "/apogee:run-plan rather than asking permission first -- approving the plan already is that "
    "permission. "
    "IF this repo is NOT git-flow: claim the first step yourself "
    "(`br update <id> --claim --actor \"${BR_ACTOR:-assistant}\"`) and continue the normal manual "
    "work loop -- /apogee:run-plan requires git-flow and will refuse to start without it. "
    "br is the project's memory across sessions: keep it current as you work (claim a step before "
    "starting it, close it when done) so a later session can pick the work up from the tracker."
)


def _beads_root(start: str):
    """Walk up from `start` to the nearest ancestor containing a `.beads/` dir, or None.

    Inlined from the dissolved core/lib/gate_common.py (ADR 0005) -- this hook was its last user.
    """
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, ".beads")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def main() -> None:
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}
    cwd = data.get("cwd") or os.getcwd()
    if not os.path.isdir(cwd) or not _beads_root(cwd):
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": DIRECTIVE,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
