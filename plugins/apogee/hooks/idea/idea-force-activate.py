#!/usr/bin/env python3
"""
SessionStart hook — fail-closed: proactively FORCE idea-first mode in JetBrains projects.

Breaks the chicken-and-egg (the agent never voluntarily calls idea, so the guards never activate) by
writing a TENTATIVE active flag at session start when this is plausibly an IDE-served project
(a JetBrains IDE process is running AND the project has a `.idea/` dir). The guards then deny native
symbol search / blind reads from turn 1, so the agent has no choice but to use mcp__idea__* — and the
first successful idea call confirms the flag (idea-usage-tracker.py).

Not a deadlock: if idea is forced on but isn't actually reachable (e.g. Claude launched outside the
IDE), the tentative flag SELF-HEALS after a couple of blocks (see register_block in idea_symbols.py)
and native tools resume. Global escape: IDEA_GATE_OFF=1 on the guards; opt-out via idea-enforce.json.

 Part of the apogee plugin.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from idea_symbols import is_idea_active, write_flag, _enforcement_enabled  # noqa: E402

ACTIVE_SOURCES = {'startup', 'clear'}
_IDE_RE = r'jetbrains|intellij|phpstorm|pycharm|goland|webstorm|rubymine|clion|rider|datagrip'

DIRECTIVE = (
    "idea-first mode is FORCED ON for this JetBrains project (context-economy): native symbol search "
    "(Grep/Glob on code symbols) and blind full-file code reads are blocked until you use the IDEA "
    "MCP tools — mcp__idea__search_symbol / get_symbol_info / get_file_problems, then Read only the "
    "needed range. Just start with an idea call (pass projectPath if asked which project). If idea "
    "tools are genuinely absent, the block self-clears after a couple of attempts → native tools."
)


def _ide_running() -> bool:
    try:
        r = subprocess.run(['pgrep', '-fi', _IDE_RE], capture_output=True, text=True, timeout=3)
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def _has_idea_dir(cwd: str) -> bool:
    d = os.path.abspath(cwd)
    while True:
        if os.path.isdir(os.path.join(d, '.idea')):
            return True
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get('source') not in ACTIVE_SOURCES:
        sys.exit(0)
    cwd = data.get('cwd') or os.getcwd()
    sid = data.get('session_id', '')
    if not os.path.isdir(cwd):
        sys.exit(0)
    if not _enforcement_enabled(cwd):
        sys.exit(0)
    if is_idea_active(cwd, sid):
        sys.exit(0)  # already active this session
    if not _has_idea_dir(cwd):
        sys.exit(0)  # not a JetBrains project -> don't force
    if not _ide_running():
        sys.exit(0)  # IDE not running -> idea MCP can't be connected

    write_flag(cwd, sid, tentative=True)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": DIRECTIVE,
        }
    }))
    sys.exit(0)


if __name__ == '__main__':
    main()
