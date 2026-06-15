#!/usr/bin/env python3
"""
PreToolUse hook (matcher: Bash) — keep external-AI handoffs in English.

The /second-opinion skill shells out to an external model CLI — now `agy`
(antigravity-cli), historically `gemini`. The skill says nothing about language,
so in a Russian conversation the agent tends to write the question/context in
Russian. But the external model is a tool, not the user — per the global rule
only user-facing dialogue is Russian; everything sent to a tool must be English.
This denies an `agy`/`gemini` invocation whose command (the prompt and/or any
piped heredoc body — all of tool_input.command) contains Cyrillic, telling the
agent to rewrite it in English.

Scope: only `agy` / `gemini` commands. Other Bash is untouched.
Escape: env TOOL_LANG_OFF=1 (also honors the legacy GEMINI_LANG_OFF=1) for the
rare legit case — e.g. asking the model to review genuinely Russian text.
Fail-open on any parse error.
"""

import json
import os
import re
import sys

# `agy` or `gemini` as the invoked command word (not inside a path/identifier
# like /usr/bin/gemini-x or agy-helper).
_TOOL_RE = re.compile(r'(?<![\w/.-])(agy|gemini)(?![\w-])')
# Cyrillic + Cyrillic Supplement (covers Russian).
_CYRILLIC_RE = re.compile(r'[Ѐ-ӿԀ-ԯ]')

DENY_REASON = (
    "The external model (agy/gemini) is a tool, not the user. Per the language rule, only "
    "user-facing dialogue is Russian — the prompt and any context you send to it must be ENGLISH. "
    "Rewrite the question (`-p '...'`) and any piped/heredoc context in English. Prefer referencing "
    "file paths over pasting Russian content — the model reads project files itself. "
    "(Rare legit exception, e.g. reviewing genuinely Russian text: set TOOL_LANG_OFF=1.)"
)


def main() -> None:
    if os.environ.get('TOOL_LANG_OFF') == '1' or os.environ.get('GEMINI_LANG_OFF') == '1':
        sys.exit(0)
    try:
        payload = json.load(sys.stdin)
        command = payload.get('tool_input', {}).get('command', '')
    except Exception:
        sys.exit(0)  # fail-open

    if not command or not _TOOL_RE.search(command):
        sys.exit(0)  # not an external-model call

    if _CYRILLIC_RE.search(command):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": DENY_REASON,
            }
        }))

    sys.exit(0)


if __name__ == '__main__':
    main()
