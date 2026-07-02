#!/usr/bin/env python3
"""
PreToolUse hook — block symbol-shaped Glob patterns when idea MCP is active.

Matcher: Glob

Blocks Glob when:
  1. idea MCP has proven active in the current session, AND
  2. the glob pattern encodes a symbol-by-name search
     (e.g. *UserService*, **/AuthProvider.tsx, *createOrder*, *get_user_sessions*).

Allows:
  - Extension / path globs: *.ts, src/**/*.php, **/*.json
  - Lowercase concept globs: *service*, *auth*, **/middleware*
  - Config filenames: tsconfig.json, next.config.ts, package.json
  - Any glob when idea MCP is not yet proven active (fail-open)
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from idea_symbols import deny, glob_contains_symbol, is_idea_active, is_subagent, register_block  # noqa: E402

_DENY_TEMPLATE = """\
⛔ IDEA-MCP GUARD: Glob blocked — symbol-shaped pattern detected.
Pattern: {pattern!r}

idea MCP is active in this session. Use instead:
  mcp__idea__search_symbol(query="<symbol>", projectPath="<project path>")
    → finds files, classes, methods, functions by name — no scanning needed

Glob is for path/extension discovery (src/**/*.php, *.json).
"""


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        pattern = payload.get('tool_input', {}).get('pattern', '')
        cwd = payload.get('cwd') or os.getcwd()
        session_id = payload.get('session_id', '')
    except Exception:
        sys.exit(0)  # fail-open

    if is_subagent(payload):
        sys.exit(0)  # subagents lack mcp__idea__* -> enforcing here can only deadlock

    if not is_idea_active(cwd, session_id):
        sys.exit(0)

    if glob_contains_symbol(pattern) and register_block(cwd, session_id):
        print(json.dumps(deny(_DENY_TEMPLATE.format(pattern=pattern))))

    sys.exit(0)


if __name__ == '__main__':
    main()
