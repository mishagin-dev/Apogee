#!/usr/bin/env python3
"""
G1 — PostToolUse gate (matcher: ExitPlanMode): capture an approved plan into br, then hand off
execution to /apogee:run-plan in git-flow repos instead of the agent implementing by hand.

When a plan is approved (ExitPlanMode), inject a directive telling the agent to record the plan in
beads_rust BEFORE editing code — create an epic + child steps. This is the "capture" front of the
br bracket; the edit gate (G2) makes it mandatory in practice (edits are blocked until a step is
in_progress). In a git-flow repo, the directive then hands off to /apogee:run-plan rather than
telling the agent to open the branch and claim the first step itself: approving a plan already IS
the user's go-ahead to execute it to completion, and run-plan owns that whole lifecycle (branch
per epic, claim/close each step, review/docs/test gates, finish, loop) with no per-step
confirmation -- duplicating that here as "start the branch, claim step 1, then implement manually"
was the exact ad-hoc loop /apogee:run-plan was built to replace, and left every ExitPlanMode
defaulting right back to it since nothing else pointed at run-plan.

Scope: GLOBAL hook, self-gates to beads projects (a `.beads/` dir above cwd). No-op elsewhere.
Fail-open: any error → no output.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core", "lib"))
from gate_common import beads_root  # noqa: E402

DIRECTIVE = (
    "A plan was just approved. Before editing any code, RECORD it in beads_rust (br): "
    "create an epic (`br create \"<feature>\" -t epic --slug <id> --json`) and one child step per "
    "task (`br create \"<step>\" -t task --parent <epicId> -l <repo> [--deps blocks:<id>] --json`), "
    "then run `br dep cycles` (must be empty). "
    "IF this repo is git-flow (has `gitflow.*` config): do NOT start the branch or claim a step "
    "yourself -- invoke /apogee:run-plan instead. It owns the whole execution lifecycle (opening "
    "the branch per epic, claiming/closing each step, the review/docs/test gates, finishing into "
    "develop, looping to the next ready epic) with no per-step confirmation; only `git push` and "
    "the release/hotfix lifecycle stay manual. State briefly that you're handing off to "
    "/apogee:run-plan rather than asking permission first -- approving the plan already is that "
    "permission. "
    "IF this repo is NOT git-flow: claim the first step yourself "
    "(`br update <id> --claim --actor \"${BR_ACTOR:-assistant}\"`) and continue the normal manual "
    "work loop -- /apogee:run-plan requires git-flow and will refuse to start without it. "
    "br is the capture source of truth; the edit gate blocks code edits until a step is in_progress, "
    "and the branch gate blocks edits on a base branch or a branch not linked to the active epic."
)


def main() -> None:
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}
    cwd = data.get("cwd") or os.getcwd()
    if not os.path.isdir(cwd) or not beads_root(cwd):
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
