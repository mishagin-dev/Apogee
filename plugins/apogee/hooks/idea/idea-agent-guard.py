#!/usr/bin/env python3
"""
PreToolUse hook (matcher: Agent) — don't delegate code search to subagents (they lack mcp__idea__).

Subagents cannot use the IDEA MCP tools, so a delegated "grep/find this symbol" task falls back to
grep + reading whole files inside the subagent — exactly the token waste idea-first mode exists to
prevent. Mirrors the LSP-kit "Agent blocker": when idea-first mode is active and a delegation prompt
is a raw code-search task, deny and tell the agent to resolve symbols/locations via idea here, then
pass concrete file:line context into the subagent prompt.

Allows everything else (build/test/review/general-exploration agents), reads when mode is inactive
(deadlock-safe), and env IDEA_GATE_OFF=1. Part of the apogee plugin.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from idea_symbols import deny, is_code_symbol, is_idea_active, is_subagent, register_block  # noqa: E402

_GREP_WORDS = re.compile(r'\b(grep|rg|ripgrep|ag|ack)\b', re.IGNORECASE)
_SEARCH_PHRASES = re.compile(
    r'\b(search for|find all|find the (definition|references|usages|implementation)|'
    r'where is|where are|locate (the )?|look for|hunt for|trace (the )?usages?)\b',
    re.IGNORECASE,
)
_TOKEN = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')

_DENY = """\
⛔ IDEA-MCP AGENT-GUARD: don't delegate code search to a subagent — it has no mcp__idea__ tools.
A subagent would fall back to grep + whole-file reads (the token waste idea-first mode prevents).

Resolve it HERE first with mcp__idea__search_symbol / get_symbol_info, then either act on the result
directly, or pass the concrete file:line locations into the subagent prompt so it doesn't search.
Delegating non-search work (build, tests, broad architecture writeups) is fine.
(Override: set IDEA_GATE_OFF=1.)
"""


def _is_code_search(prompt: str) -> bool:
    if _GREP_WORDS.search(prompt):
        return True
    if _SEARCH_PHRASES.search(prompt):
        # a search phrase alone is weak; require a code symbol to be the target
        return any(is_code_symbol(t) for t in _TOKEN.findall(prompt))
    return False


def main() -> None:
    if os.environ.get('IDEA_GATE_OFF') == '1':
        sys.exit(0)
    try:
        payload = json.load(sys.stdin)
        ti = payload.get('tool_input', {}) or {}
        prompt = ti.get('prompt', '') or ''
        cwd = payload.get('cwd') or os.getcwd()
        sid = payload.get('session_id', '')
    except Exception:
        sys.exit(0)

    if is_subagent(payload):
        sys.exit(0)  # subagent context (nested spawn) lacks mcp__idea__* -> deadlock-safe no-op

    if not is_idea_active(cwd, sid):
        sys.exit(0)  # mode not active -> deadlock-safe no-op

    if prompt and _is_code_search(prompt) and register_block(cwd, sid):
        print(json.dumps(deny(_DENY)))

    sys.exit(0)


if __name__ == '__main__':
    main()
