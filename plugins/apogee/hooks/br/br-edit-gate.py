#!/usr/bin/env python3
"""
G2 — PreToolUse gate (Edit|Write|MultiEdit|NotebookEdit): no CODE edit without an active br step.

Part of the br-enforcement "bracket": all work must flow through beads_rust (br). This denies a code
edit in a beads project when there is NO in_progress br issue — forcing the agent to claim/create a
step first (`br update <id> --claim` / `br create … --json`). Once a step is in_progress, edits pass.

Scope: GLOBAL hook, but self-gates to beads projects (a `.beads/` dir above cwd). No-op elsewhere.
Exempt paths (meta/docs): `.beads/`, `workflow/`, `conductor/`, `.claude/`, and edits outside the
beads root. Escape hatch: env `BR_GATE_OFF=1`.
Fail-open: any error / missing `br` → allow (the Stop gate is the backstop; never trap on infra).
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core", "lib"))
from gate_common import beads_root, deny  # noqa: E402

EXEMPT_TOP = {".beads", "workflow", "conductor", ".claude"}

DENY_REASON = (
    "No active beads_rust step. Every code change must belong to a br step. "
    "Claim or create one first: `br update <id> --claim --actor \"${BR_ACTOR:-assistant}\"` "
    "or `br create \"<title>\" -t task --parent <epic> --json`, then retry the edit. "
    "(Ad-hoc escape: set BR_GATE_OFF=1.)"
)


def main() -> None:
    if os.environ.get("BR_GATE_OFF") == "1":
        return
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}

    cwd = data.get("cwd") or os.getcwd()
    if not os.path.isdir(cwd):
        return
    root = beads_root(cwd)
    if not root:
        return  # not a beads project -> no-op

    # Exempt meta/doc paths and edits outside the beads root.
    fp = (data.get("tool_input") or {}).get("file_path") or ""
    if fp:
        rel = os.path.relpath(os.path.abspath(fp), root)
        if rel.startswith(".."):
            return
        if rel.split(os.sep)[0] in EXEMPT_TOP:
            return

    # Is there an in_progress br step?
    try:
        res = subprocess.run(
            ["br", "-q", "list", "--status", "in_progress", "--json", "--no-color"],
            capture_output=True, text=True, timeout=10, cwd=root,
        )
        obj = json.loads(res.stdout or "{}")
    except Exception:
        return  # fail-open on any br/parse error
    total = obj.get("total", len(obj.get("issues", [])))
    if total and total > 0:
        return  # an active step exists -> allow

    deny(DENY_REASON)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail-open
    sys.exit(0)
