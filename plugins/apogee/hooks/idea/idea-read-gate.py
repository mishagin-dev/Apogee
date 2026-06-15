#!/usr/bin/env python3
"""
PreToolUse hook (matcher: Read) — progressive read-gate for context economy.

Mirrors the LSP-enforcement-kit "read gate": once idea-first mode is active, force IDE navigation
(search_symbol / get_symbol_info / get_file_problems) BEFORE bulk-reading code files, so the agent
reads surgically instead of dumping whole files. After BUDGET full-file code reads with no intervening
idea call, the next full-file code read is denied until an idea call resets the budget (the reset
happens in idea-usage-tracker.py).

Always allows (no friction on legitimate reads):
  - Reads with offset/limit (already surgical)
  - Non-code files (docs/config/data)
  - Meta/vendor paths (.beads/, .claude/, conductor/, workflow/, node_modules/, .git/, vendor/, dist/, plans)
  - Anything when idea-first mode is NOT active (deadlock-safe) or env IDEA_GATE_OFF=1

 Part of the apogee plugin.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from idea_symbols import deny, is_idea_active, register_block  # noqa: E402

BUDGET = 2

CODE_EXT = {
    'ts', 'tsx', 'js', 'jsx', 'mjs', 'cjs', 'php', 'py', 'go', 'rs', 'java', 'kt', 'kts',
    'swift', 'vue', 'svelte', 'rb', 'cs', 'cpp', 'cc', 'c', 'h', 'hpp', 'scala', 'm', 'mm',
}
EXEMPT_PARTS = {
    '.beads', '.claude', 'conductor', 'workflow', 'node_modules', '.git', 'vendor',
    'dist', 'build', '__pycache__',
}

_DENY = """\
⛔ IDEA-MCP READ-GATE: {n} code files read without IDE navigation — read surgically instead.
File: {fp}

idea-first mode is active. Before reading another whole file, locate precisely with:
  mcp__idea__search_symbol(query="<symbol>", projectPath="<project path>")
  mcp__idea__get_symbol_info(file="<file>", line=<line>, column=<col>)
  mcp__idea__get_file_problems(...)   → diagnostics without reading the file
then Read only the relevant range (Read with offset/limit). An idea call refreshes the read budget.
(Override: set IDEA_GATE_OFF=1. Reads with offset/limit and non-code/doc files are never gated.)
"""


def main() -> None:
    if os.environ.get('IDEA_GATE_OFF') == '1':
        sys.exit(0)
    try:
        payload = json.load(sys.stdin)
        ti = payload.get('tool_input', {}) or {}
        fp = ti.get('file_path', '') or ''
        cwd = payload.get('cwd') or os.getcwd()
        sid = payload.get('session_id', '')
    except Exception:
        sys.exit(0)

    if not is_idea_active(cwd, sid):
        sys.exit(0)  # mode not active -> deadlock-safe no-op

    # Surgical read already -> allow.
    if ti.get('offset') is not None or ti.get('limit') is not None:
        sys.exit(0)
    if not fp:
        sys.exit(0)

    parts = set(os.path.normpath(fp).split(os.sep))
    if parts & EXEMPT_PARTS:
        sys.exit(0)
    base = os.path.basename(fp)
    if base.startswith('plan') or 'plans' in parts:
        sys.exit(0)

    ext = base.rsplit('.', 1)[-1].lower() if '.' in base else ''
    if ext not in CODE_EXT:
        sys.exit(0)  # docs/config/data -> not gated

    count_path = f"/tmp/idea-reads-{sid or 'unknown'}"
    try:
        n = int(open(count_path).read().strip())
    except Exception:
        n = 0

    if n >= BUDGET:
        if register_block(cwd, sid):
            print(json.dumps(deny(_DENY.format(n=n, fp=fp))))
        sys.exit(0)

    try:
        with open(count_path, 'w') as f:
            f.write(str(n + 1))
    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
