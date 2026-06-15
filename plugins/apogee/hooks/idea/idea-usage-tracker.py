#!/usr/bin/env python3
"""
PostToolUse hook — track successful mcp__idea__* calls to activate enforcement.

Matcher: mcp__idea__.*

Writes an evidence flag (~/.claude/state/idea-active-<md5(cwd)>) only when the
idea MCP server returns real project data.  A non-answer — disambiguation (server
lists open projects) OR an error/unreachable response — does NOT set the flag and
CLEARS any existing one, so the guards fall back to native tools ("tried idea, it
failed → use the built-in tool").

Flag JSON: {"session_id": "...", "cwd": "...", "active": true, "ts": <epoch-ms>}

Guards (idea-symbol-guard.py, idea-glob-guard.py, idea-bash-grep-guard.py) read
this flag.  Enforcement is session-scoped: a new session_id makes the flag stale
and all guards fall back to fail-open.  No SessionStart reset hook is needed.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from idea_symbols import get_flag_path, reset_denials  # noqa: E402

# Markers of a NON-answer: the call didn't actually serve project data, so idea-first mode must NOT
# turn on (and any stale flag is cleared → guards fall back to native tools). Includes the
# multi-project disambiguation response and genuine transport/tool errors. Kept specific to avoid
# false-deactivation on normal results; a structured `isError` is the most reliable signal.
_FAILURE_MARKERS = (
    'unable to determine the target project',   # multi-project disambiguation
    'failed to connect', 'connection refused', 'econnrefused', 'is not connected',
    'mcp error', 'tool not found', 'unknown tool', 'method not found',
    'no project is open', 'server is not running',
)


def _is_failure(raw, resp_str: str) -> bool:
    """True if the idea response is an error / non-answer (so the mode should not be active)."""
    if isinstance(raw, dict):
        if raw.get('isError') or raw.get('is_error') or raw.get('error'):
            return True
        if str(raw.get('status', '')).lower() == 'error':
            return True
    low = resp_str.lower()
    return any(m in low for m in _FAILURE_MARKERS)


def _clear_flag(cwd: str) -> None:
    try:
        os.unlink(get_flag_path(cwd))
    except FileNotFoundError:
        pass
    except Exception:
        pass


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cwd = payload.get('cwd') or os.getcwd()
    session_id = payload.get('session_id', '')

    # Stringify tool_response however it arrives
    raw = payload.get('tool_response', '')
    resp_str = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)

    # idea didn't actually serve (disambiguation OR error/unreachable) → deactivate so guards fall
    # back to native tools. This is the "tried idea, it failed → use the built-in tool" path.
    if _is_failure(raw, resp_str):
        _clear_flag(cwd)
        sys.exit(0)

    # Successful response → idea MCP is serving this session → CONFIRM the flag (tentative=False).
    # A confirmed flag never self-heals (its denials are legitimate "use idea"); see register_block.
    flag_path = get_flag_path(cwd)
    flag = {
        'session_id': session_id,
        'cwd':        cwd,
        'active':     True,
        'tentative':  False,
        'ts':         int(time.time() * 1000),
    }
    try:
        os.makedirs(os.path.dirname(flag_path), exist_ok=True)
        tmp = flag_path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(flag, f)
        os.replace(tmp, flag_path)
    except Exception:
        pass  # never block on tracker failure

    # idea proved live → drop the tentative self-heal counter so the (now confirmed) flag stays put.
    reset_denials(session_id)

    # Refresh the read-gate budget (idea-read-gate.py): a real idea navigation call earns the next
    # batch of surgical reads. Keeps "navigate before bulk-reading" cheap to satisfy.
    try:
        with open(f"/tmp/idea-reads-{session_id or 'unknown'}", 'w') as f:
            f.write('0')
    except Exception:
        pass

    sys.exit(0)


if __name__ == '__main__':
    main()
