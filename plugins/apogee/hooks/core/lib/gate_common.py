"""
Shared helpers for the Apogee hook gates.

Cross-group primitives reused by the br/* and git/* gates. Kept in `core/lib/` (a deliberate exception
to the "helpers in their own group dir" rule — same rationale as `idea/lib/`) because more than one
hook group depends on them. Importers anchor `sys.path` on their own `__file__`, never on CWD or
`${CLAUDE_PLUGIN_ROOT}`.
"""

import json
import os


def beads_root(start: str):
    """Walk up from `start` to the nearest ancestor containing a `.beads/` dir, or None."""
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, ".beads")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def deny(reason):
    """Emit a PreToolUse deny decision."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def ask(reason):
    """Emit a PreToolUse ask decision (surfaces a confirmation prompt)."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))
