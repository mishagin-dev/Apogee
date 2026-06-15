#!/usr/bin/env python3
"""
UserPromptSubmit hook — bootstrap idea-first mode (break the chicken-and-egg).

The idea-mcp enforcement guards (idea-symbol/glob/bash-grep, read-gate, agent-guard) only activate
once `is_idea_active()` is true, which happens only AFTER a successful mcp__idea__ call sets the
session flag (via idea-usage-tracker.py). If the agent never voluntarily calls idea, nothing ever
activates. This hook nudges the agent to make that first idea call so the guards engage — turning the
idea-MCP setup into a context-economy replacement for an LSP-enforcement kit.

Safe by design: it only NUDGES (additionalContext), never blocks. The server is stdio (can't be
probed from a hook), so we never force-activate the flag — only a real successful idea call does that,
which means the guards can never deadlock a session where idea tools are actually absent.

Fires only while: a JetBrains IDE process is running, idea is not yet active this session, and at most
LIMIT times per session (so it never nags forever when idea genuinely isn't connected).
 Part of the apogee plugin.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from idea_symbols import is_idea_active  # noqa: E402

LIMIT = 3
_IDE_RE = r'jetbrains|intellij|phpstorm|pycharm|goland|webstorm|rubymine|clion|rider|datagrip'

DIRECTIVE = (
    "A JetBrains IDE is running, so the IDEA MCP server may be serving this project. "
    "If mcp__idea__* tools are present in your toolset, they take PRIORITY over native tools for "
    "code intelligence (this setup replaces an LSP-enforcement kit to save context): use "
    "mcp__idea__search_symbol / get_symbol_info instead of grep+reading whole files; "
    "mcp__idea__get_file_problems / get_inspections to validate edits; rename_refactoring instead of "
    "sed; execute_run_configuration / build_project instead of bare terminal build/run. "
    "ACTIVATE enforcement now by making ONE cheap mcp__idea__* call that returns real data — ANY "
    "successful idea call turns the guards on, not a specific tool. Prefer mcp__idea__get_project_modules; "
    "if it isn't offered, use any available idea tool (e.g. get_all_open_file_paths, list_directory_tree, "
    "get_project_dependencies). If the call asks which project (disambiguation), retry once with "
    "projectPath set to this repo. If NO mcp__idea__* tools are present at all, ignore this and use "
    "native tools."
)


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

    if is_idea_active(cwd, sid):
        sys.exit(0)  # guards already active -> no nudge needed
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
