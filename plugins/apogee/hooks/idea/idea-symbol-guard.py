#!/usr/bin/env python3
"""
PreToolUse hook — enforce mcp__idea__search_symbol over Grep for code symbols.

Matcher: Grep

Blocks Grep when:
  1. idea MCP has proven active in the current session (evidence flag present), AND
  2. the search pattern looks like a naked code symbol
     (PascalCase / camelCase / snake_case-3-parts / PHP-namespace / dotted-method).

Falls through silently (exit 0) when:
  - No evidence flag → idea MCP not yet proven active → fail-open
  - Pattern is a deliberate regex (contains strong metacharacters)
  - Pattern is a keyword, env-var constant, CSS class, or too short
  - Any parse error → fail-open
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from idea_symbols import deny, is_code_symbol, is_idea_active, is_subagent, register_block  # noqa: E402

_DENY_TEMPLATE = """\
⛔ IDEA-MCP GUARD: Grep blocked — use IDE semantic search instead.
Symbol detected: {symbol!r}

idea MCP is active in this session. Use:
  mcp__idea__search_symbol(query="{symbol}", projectPath="<project path>")
    → finds class / method / function / interface definitions with full body excerpt

  mcp__idea__get_symbol_info(file="<file>", line=<line>, column=<col>)
    → type, signature, docs, inheritance chain at a specific reference

Grep is reserved for non-symbol searches (config values, SQL, docs, comments).
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
        sys.exit(0)  # enforcement not yet activated

    if is_code_symbol(pattern) and register_block(cwd, session_id):
        print(json.dumps(deny(_DENY_TEMPLATE.format(symbol=pattern))))

    sys.exit(0)


if __name__ == '__main__':
    main()
