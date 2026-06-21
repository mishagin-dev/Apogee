"""
Shared helpers for the Apogee hook gates.

Cross-group primitives reused by the br/* and git/* gates. Kept in `core/lib/` (a deliberate exception
to the "helpers in their own group dir" rule — same rationale as `idea/lib/`) because more than one
hook group depends on them. Importers anchor `sys.path` on their own `__file__`, never on CWD or
`${CLAUDE_PLUGIN_ROOT}`.
"""

import json
import os
import subprocess

# Top-level dirs whose edits never count as trackable code (meta / docs / config).
EXEMPT_TOP = {".beads", "workflow", "conductor", ".claude"}


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


def git_ignored(root, rel):
    """True if `rel` (path relative to `root`) is git-ignored within `root`.

    Tracked files return False even if a matching ignore rule exists. Works on
    not-yet-created paths (matches ignore rules, not the filesystem) so a Write of a
    fresh `docs/apogee/...` file is recognized. Fail-open: any error -> not ignored."""
    try:
        r = subprocess.run(["git", "-C", root, "check-ignore", "-q", rel],
                           capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def path_exempt(root, fp):
    """Should an edit to `fp` skip the br edit gates?

    Exempt = the edit can never be trackable code under the branch/step discipline:
      - no file path (e.g. NotebookEdit without one) -> not exempt, let the gate run;
      - edits outside the beads root;
      - meta/doc/config top-level dirs (`EXEMPT_TOP`);
      - git-ignored working files (Apogee working memory: `docs/apogee/**`, `.claude/*`);
      - any `CLAUDE.md` (project / submodule instructions) -> bootstrap content, and the
        commit gate still enforces where it lands.
    """
    if not fp:
        return False
    abs_fp = os.path.abspath(fp)
    rel = os.path.relpath(abs_fp, root)
    if rel.startswith(".."):
        return True
    if rel.split(os.sep)[0] in EXEMPT_TOP:
        return True
    if os.path.basename(abs_fp) == "CLAUDE.md":
        return True
    return git_ignored(root, rel)


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
