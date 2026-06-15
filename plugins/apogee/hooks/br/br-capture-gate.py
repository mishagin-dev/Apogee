#!/usr/bin/env python3
"""
G1 — PostToolUse gate (matcher: ExitPlanMode): capture an approved plan into br.

When a plan is approved (ExitPlanMode), inject a directive telling the agent to record the plan in
beads_rust BEFORE editing code — create an epic + child steps, then claim the first. This is the
"capture" front of the br bracket; the edit gate (G2) makes it mandatory in practice (edits are
blocked until a step is in_progress).

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
    "run `br dep cycles` (must be empty). "
    "Then, IF this repo is git-flow (has `gitflow.*` config), start the work branch for this epic via "
    "the git-flow skill BEFORE claiming/editing — `git flow feature start <epicSlug>` (use `bugfix` "
    "for a bug track) — and link it to the epic: "
    "`br update <epicId> --external-ref <branch> --actor \"${BR_ACTOR:-assistant}\"` (branch name = "
    "the epic slug; one epic == one branch). "
    "Finally claim the first step (`br update <id> --claim --actor \"${BR_ACTOR:-assistant}\"`). "
    "br is the capture source of truth; the edit gate blocks code edits until a step is in_progress, "
    "and the branch gate blocks edits on a base branch or a branch not linked to the active epic."
)


def beads_root(start: str):
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
