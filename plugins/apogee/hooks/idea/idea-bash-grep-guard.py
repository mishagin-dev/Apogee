#!/usr/bin/env python3
"""
PreToolUse hook — block shell grep on code symbols when idea MCP is active.

Matcher: Bash

Claude sometimes bypasses the Grep tool by shelling out.  This hook catches:
  grep / rg / ag / ack  in Bash commands.

Always allows:
  - Non-grep Bash commands (early exit 0 — no interference with git, npm, etc.)
  - git grep (legitimate history / object search)
  - grep on non-code paths (.task/, .claude/, node_modules/, migrations/)
  - grep with safe --include= filters (*.sql, *.md, *.json, *.yaml, *.env, etc.)
  - Any command when idea MCP is not yet proven active (fail-open)
  - Any parse error → fail-open
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from idea_symbols import (  # noqa: E402
    deny,
    extract_grep_pattern,
    is_code_symbol,
    is_idea_active,
    register_block,
)

_GREP_RE = re.compile(r'\b(grep|rg|ag|ack)\b', re.IGNORECASE)

# Paths and patterns that are explicitly not code symbols
_SAFE_PATH_RE = re.compile(
    r'(migrations?/|\.task[/\s]|\.claude[/\s]|node_modules/|knowledge-vault/|'
    r'\btest[s]?/|__tests__/|__mocks__/)',
    re.IGNORECASE,
)

# --include filters for non-code file types → safe to grep freely
_SAFE_INCLUDE_RE = re.compile(
    r'--include[= ]["\']?\*\.(sql|md|json|jsonc|yaml|yml|env|sh|txt|csv|toml|'
    r'xml|html|css|scss|lock|ini|cfg|conf|log)["\']?',
    re.IGNORECASE,
)

_DENY_TEMPLATE = """\
⛔ IDEA-MCP GUARD: shell grep blocked — use IDE semantic search instead.
Symbol detected: {symbol!r}
Command: {cmd!r}

idea MCP is active in this session. Use instead:
  mcp__idea__search_symbol(query="{symbol}", projectPath="<project path>")
    → precise symbol location without noisy output

  mcp__idea__get_symbol_info(file="<file>", line=<line>, column=<col>)
    → type, signature, docs at a specific reference

git grep is always allowed for history / object search.
grep is allowed for non-code files (SQL, config, docs).
"""


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        command = payload.get('tool_input', {}).get('command', '')
        cwd = payload.get('cwd') or os.getcwd()
        session_id = payload.get('session_id', '')
    except Exception:
        sys.exit(0)  # fail-open

    # Fast path: not a grep-family command → pass through immediately
    if not _GREP_RE.search(command):
        sys.exit(0)

    # git grep → allow (history / object search)
    if re.search(r'\bgit\s+grep\b', command, re.IGNORECASE):
        sys.exit(0)

    # Non-code path targets → allow
    if _SAFE_PATH_RE.search(command):
        sys.exit(0)

    # Non-code --include filters → allow
    if _SAFE_INCLUDE_RE.search(command):
        sys.exit(0)

    # Enforcement only when idea MCP has proven active
    if not is_idea_active(cwd, session_id):
        sys.exit(0)

    pattern = extract_grep_pattern(command)
    if pattern and is_code_symbol(pattern) and register_block(cwd, session_id):
        print(json.dumps(deny(_DENY_TEMPLATE.format(symbol=pattern, cmd=command))))

    sys.exit(0)


if __name__ == '__main__':
    main()
