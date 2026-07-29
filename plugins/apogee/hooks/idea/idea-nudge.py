#!/usr/bin/env python3
"""
UserPromptSubmit hook — remind the agent to prefer IDEA MCP tools for code intelligence.

The point is context economy: `mcp__idea__search_symbol` returns a symbol and its location where
grep + reading whole files would spend thousands of tokens. This is a NUDGE only (additionalContext)
— it never blocks. The five idea enforcement guards it used to bootstrap were deleted by ADR 0005
(they blocked read-only operations, produced false positives, and defended nothing irreversible), so
there is no longer any "activation" to trigger; the reminder stands on its own.

Fires only while: this tree is a JetBrains project, a JetBrains IDE process is running, and at most
LIMIT times per session (so it never nags forever when idea genuinely isn't connected).
 Part of the apogee plugin.
"""

import json
import os
import subprocess
import sys

LIMIT = 3
_IDE_RE = r'jetbrains|intellij|phpstorm|pycharm|goland|webstorm|rubymine|clion|rider|datagrip'

DIRECTIVE = (
    "A JetBrains IDE is running, so the IDEA MCP server may be serving this project. "
    "If mcp__idea__* tools are present in your toolset, prefer them over native tools for "
    "code intelligence — they cost a fraction of the context: use "
    "mcp__idea__search_symbol / get_symbol_info instead of grep+reading whole files; "
    "mcp__idea__get_file_problems / lint_files to validate edits; rename_refactoring instead of "
    "sed; execute_run_configuration / build_project instead of bare terminal build/run. "
    "If a call asks which project (disambiguation), retry once with projectPath set to this repo. "
    "If NO mcp__idea__* tools are present at all, ignore this and use native tools."
)


def _has_idea_project(cwd: str) -> bool:
    """True if cwd is inside a JetBrains project the IDE could be serving.

    Walks up from cwd to root, checking each level for either a `.idea/` dir or a top-level `*.iml`
    module file. The `*.iml` marker covers JetBrains Gateway / remote-dev where `.idea/` lives on the
    backend but an `.iml` is present locally; checking it at every walk level (not just cwd) lets a
    subdir of such a project resolve correctly. Inlined from the deleted lib/idea_symbols.py
    (ADR 0005) -- this hook was its last user.
    """
    d = os.path.abspath(cwd)
    while True:
        if os.path.isdir(os.path.join(d, '.idea')):
            return True
        try:
            if any(name.endswith('.iml') for name in os.listdir(d)):
                return True
        except OSError:
            pass
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent


def _ide_running() -> bool:
    try:
        r = subprocess.run(["pgrep", "-fi", _IDE_RE],
                           capture_output=True, text=True, timeout=3)
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cwd = payload.get('cwd') or os.getcwd()
    sid = payload.get('session_id', '')

    if not _has_idea_project(cwd):
        sys.exit(0)  # IDE isn't serving this tree (no .idea/ or .iml) -> nudge would be futile
    if not _ide_running():
        sys.exit(0)  # no JetBrains IDE -> idea MCP can't be connected

    count_path = f"/tmp/idea-nudge-{sid or 'unknown'}.count"
    try:
        n = int(open(count_path).read().strip())
    except Exception:
        n = 0
    if n >= LIMIT:
        sys.exit(0)  # stop nagging
    try:
        with open(count_path, 'w') as f:
            f.write(str(n + 1))
    except Exception:
        pass

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": DIRECTIVE,
        }
    }))
    sys.exit(0)


if __name__ == '__main__':
    main()
