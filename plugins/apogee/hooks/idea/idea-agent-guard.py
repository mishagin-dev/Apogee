#!/usr/bin/env python3
"""
PreToolUse hook (matcher: Agent) — nudge against delegating LOCAL code search to subagents.

Subagents cannot use the IDEA MCP tools, so a delegated "grep/find this symbol in the repo" task
falls back to grep + reading whole files inside the subagent — exactly the token waste idea-first
mode exists to prevent.

When idea-first mode is active and a delegation prompt is a clearly LOCAL code-search task, this
guard surfaces a confirmation (ask) instead of hard-blocking. A hard deny was too eager: it trapped
valid external-research delegations (e.g. "find how RealityConfig is used in upstream utls") because
the prompt shape matched a local search, AND the escape hatch IDEA_GATE_OFF does not propagate
through the Agent tool — so a legit delegation had nowhere to go. With `ask`, the user reviews each
such delegation (approve external research / non-search work; decline to resolve via idea here).

The match is deliberately narrow: a search phrase alone is ambiguous (could target an upstream
library, docs, or a CVE), so the phrase branch requires BOTH a code symbol AND a local-scope
indicator ("in src", "this repo", "the codebase", a repo-relative path). Bare grep/rg/ag/ack verbs
remain a strong local-search signal on their own.

Reads when mode is inactive (deadlock-safe), short-circuits inside subagents (nested spawn), and
honors env IDEA_GATE_OFF=1. Part of the apogee plugin.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from idea_symbols import ask, is_code_symbol, is_idea_active, is_subagent  # noqa: E402

_GREP_WORDS = re.compile(r'\b(grep|rg|ripgrep|ag|ack)\b', re.IGNORECASE)
_SEARCH_PHRASES = re.compile(
    r'\b(search for|find all|find the (definition|references|usages|implementation)|'
    r'where is|where are|locate (the )?|look for|hunt for|trace (the )?usages?)\b',
    re.IGNORECASE,
)
# Local-scope signals: their presence alongside a search phrase means the delegation targets THIS
# codebase (the case idea-first mode protects). Absent → the phrase likely refers to something
# external (an upstream library, a CVE, docs) and is out of scope for the guard.
_LOCAL_INDICATORS = re.compile(
    r'\b(?:'
    r'in (?:src|the (?:repo|codebase|project)|this (?:repo|codebase|project|code))'
    r'|our (?:code|codebase|repo|project)'
    r'|local(?:ly)?'
    r'|here in (?:the (?:repo|codebase|project)|this (?:repo|codebase|project))'
    r'|the (?:repo|codebase)'
    r')\b',
    re.IGNORECASE,
)
# A repo-relative file path (≥2 code-ish segments, optionally ./ or ../) is also a strong local
# signal — e.g. "check src/api/handlers" or "in ./lib/auth.go".
_PATH_HINT = re.compile(r'(?:^|[\s"\'(])(?:\.{0,2}/)?[A-Za-z][\w-]*(?:/[A-Za-z0-9_.-]+){1,}')

_TOKEN = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')

_ASK = """\
⚠️ IDEA-MCP AGENT-GUARD: this delegation looks like a LOCAL code search.

Subagents have no mcp__idea__ tools, so they fall back to grep + whole-file reads — the token waste
idea-first mode exists to prevent. Prefer resolving it HERE with mcp__idea__search_symbol /
get_symbol_info, then either act on the result or pass concrete file:line locations into the
subagent prompt so it doesn't search.

Approve only if this is genuinely external (an upstream library, a CVE, docs) or non-search work.
(Override: set IDEA_GATE_OFF=1.)
"""


def _is_code_search(prompt: str) -> bool:
    # An explicit search-tool verb is a strong local-search signal on its own.
    if _GREP_WORDS.search(prompt):
        return True
    if _SEARCH_PHRASES.search(prompt):
        # A bare search phrase is ambiguous — it may target an external library / docs / a CVE.
        # Require a code symbol AND a local-scope indicator so only clearly-local searches match.
        has_symbol = any(is_code_symbol(t) for t in _TOKEN.findall(prompt))
        has_local = bool(_LOCAL_INDICATORS.search(prompt) or _PATH_HINT.search(prompt))
        return has_symbol and has_local
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

    if prompt and _is_code_search(prompt):
        # `ask` (not deny): a delegation that merely looks like local code search is confirmed by
        # the user rather than hard-blocked, so legit external research isn't trapped. register_block
        # / self-heal is intentionally not used — `ask` doesn't trap, so there's nothing to heal.
        print(json.dumps(ask(_ASK)))

    sys.exit(0)


def _run_self_test() -> None:
    """Self-test: _is_code_search matches clearly-local searches but lets external research and
    ambiguous (no-local-indicator) prompts through.
    Run: python3 idea-agent-guard.py --test"""
    cases = [
        # (label, prompt, want _is_code_search)
        ("grep verb local",          "grep for UserService across the repo",                 True),
        ("rg symbol local",          "rg handleSubmit in src",                               True),
        ("find all + symbol + local","find all references to OrderItemDto in this repo",     True),
        ("trace usages + local path","trace the usages of getUserById in src/api",           True),
        ("look for + path hint",     "look for AuthProvider, check src/auth/provider.go",    True),
        ("find all + symbol, ext",   "find all usages of RealityConfig in the metacubex utls library", False),
        ("find impl + symbol, ext",  "find the implementation of UtlsTransport in upstream", False),
        ("look for + symbol, no loc","look for AuthProvider",                                False),
        ("external CVE",             "search for CVE-2024-1234 details",                     False),
        ("plain research",           "research the metacubex utls transport",                False),
        ("build task",               "run the test suite and report failures",               False),
        ("broad exploration",        "summarize the architecture of the auth module",        False),
    ]
    ok = True
    for label, prompt, want in cases:
        got = _is_code_search(prompt)
        mark = "✓" if got == want else "✗ FAIL"
        if got != want:
            ok = False
        print(f"  {mark}  {label}: _is_code_search={got} (want {want})")
    print("\n" + ("All tests passed." if ok else "SOME TESTS FAILED."))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    if '--test' in sys.argv:
        _run_self_test()
    else:
        main()
