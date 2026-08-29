#!/usr/bin/env python3
"""
UserPromptSubmit hook — point the agent at the IDEA MCP capabilities the shell cannot replace.

The scope is deliberately narrow, and narrower than it used to be. A 2026-08-25 measurement over
live transcripts (10 single-purpose symbol/text lookups replayed from real session history) found
the MCP search path 41% MORE expensive than the equivalent grep, not cheaper: `search_symbol`
returns coordinates without symbol names and `search_text` without line content, so the small first
response usually forces a second call. Broad symbol search does win, but only against an unbounded
grep -- against the bounded `grep ... | head -30` the agent actually writes the margin falls to
~30%, and `grep -rl` beats it outright. So this directive no longer advertises search or file
reading; it names only what has no shell equivalent: inspections, semantic rename, call graphs and
IDE run configurations.

It also states the deferred-schema prerequisite. `mcp__idea__*` tools arrive as names only and a
call without a prior ToolSearch fails outright. The previous wording ("prefer them ... they cost a
fraction of the context") assumed they were directly callable; 14 days of transcripts carry 119
ToolSearch calls and not one `select:mcp__idea__*`, i.e. the recommended path was unreachable as
written and the nudge converted at zero.

This is a NUDGE only (additionalContext) — it never blocks. The five idea enforcement guards it used
to bootstrap were deleted by ADR 0005 (they blocked read-only operations, produced false positives,
and defended nothing irreversible), so there is no longer any "activation" to trigger.

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
    "A JetBrains IDE is running, so the IDEA MCP server may be serving this project. Its schemas "
    "are deferred: load one with ToolSearch (\"select:mcp__idea__<tool>\") before calling it, or "
    "the call fails. Reach for it only where the shell has no equivalent: get_file_problems / "
    "lint_files for IDE inspections, rename_refactoring to rename across references, analyze_calls "
    "for a call graph, execute_run_configuration / build_project to run the IDE's own "
    "configurations. For text and symbol search a bounded grep measured cheaper — keep using it. "
    "Pass projectPath to skip a disambiguation round-trip. "
    "If no mcp__idea__* tools are present at all, ignore this."
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
