#!/usr/bin/env python3
"""
PostToolUse hook (matcher: Skill) — record that an end-of-task skill ran this session.

When the agent invokes the `Skill` tool for `/review-work` or `/update-docs`, drop a per-session
marker file that the Stop gate (review-docs-gate.sh) checks to enforce the review->docs pipeline:
  /tmp/claude-review-<sid>.done   <- review-work ran
  /tmp/claude-docs-<sid>.done     <- update-docs ran

 Part of the apogee plugin. (same pattern as apogee-session-start.py).
Name match is tolerant (plugin-namespaced `foo:review-work` etc.). Fail-open: never blocks a tool.
Set SKILL_TRACKER_DEBUG=1 to log every observed skill name to hooks/logs/skill-run-tracker.log
(useful to confirm the Skill tool's tool_input shape in a live session).
"""

import json
import os
import sys
import time

MARKERS = {
    "review-work": "/tmp/claude-review-{sid}.done",
    "update-docs": "/tmp/claude-docs-{sid}.done",
}


def _log(line: str) -> None:
    if os.environ.get("SKILL_TRACKER_DEBUG") != "1":
        return
    try:
        d = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "skill-run-tracker.log"), "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _touch(path: str) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(str(int(time.time() * 1000)))
        os.replace(tmp, path)
    except Exception:
        pass


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    sid = payload.get("session_id") or "unknown"
    ti = payload.get("tool_input") or {}

    # Primary: the explicit skill name field. Fallback: scan the serialized tool_input.
    name = ""
    if isinstance(ti, dict):
        name = ti.get("skill") or ti.get("command") or ti.get("name") or ""
    haystack = (name or "").lower()
    if not haystack:
        try:
            haystack = json.dumps(ti, ensure_ascii=False).lower()
        except Exception:
            haystack = ""

    _log(f"{sid}\tname={name!r}\thay={haystack[:200]!r}")

    for key, tmpl in MARKERS.items():
        if key in haystack:
            _touch(tmpl.format(sid=sid))
            _log(f"{sid}\tMARK {key}")

    sys.exit(0)


if __name__ == "__main__":
    main()
