#!/usr/bin/env python3
"""
PreToolUse hook — enforce the git-commit skill path.

Allows:  git commit -F <file>          (skill's temp-file pattern)
         git commit --amend --no-edit  (no new message written)
Denies:  git commit -m / -am / --message / bare commit / --amend with message
Ignores: any Bash command that does not invoke `git commit`
Fail-open: parse errors silently exit 0 so unrelated Bash calls are never blocked.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core", "lib"))
from gate_common import strip_payloads  # noqa: E402

DENY_RESPONSE = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            "Commits must go through the git-commit skill "
            "(~/.claude/skills/git-commit/SKILL.md): "
            "run scripts/gather-context.sh, compose and validate the message "
            "with scripts/check-message.sh, then commit with "
            "`git commit -F <tempfile>`."
        ),
    }
}

# Matches `git commit` as standalone words, not inside paths like skills/git-commit/...
# Lookarounds reject word chars, hyphens, slashes, and dots as adjacent characters.
GIT_COMMIT_RE = re.compile(r"(?<![\w/.-])git(?![\w-])[^|;&\n]*(?<![\w/.-])commit(?![\w-])")


def _has_flag(command: str, *flags: str) -> bool:
    """Return True if any of the given flag strings appear in the command."""
    return any(f in command for f in flags)


def evaluate(command: str) -> bool:
    """Return True (allow) or False (deny)."""
    if not GIT_COMMIT_RE.search(command):
        return True  # not a git commit — allow

    # Skill path: commit via -F / --file (message read from a temp file).
    if _has_flag(command, " -F ", " --file ", ' -F"', " --file="):
        return True

    # Allow amend that does not rewrite the message.
    if "--amend" in command and "--no-edit" in command:
        return True

    # Everything else: -m, -am, --message, bare commit, --amend with new msg.
    return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
    except Exception:
        sys.exit(0)  # fail open

    # Strip quoted/heredoc payloads so an unrelated command mentioning `git commit` (e.g. inside an
    # `agy -p '...'` prompt) isn't mistaken for a real ad-hoc commit. See gate_common.strip_payloads.
    command = strip_payloads(command)

    if not evaluate(command):
        print(json.dumps(DENY_RESPONSE))

    sys.exit(0)


def _run_self_test() -> None:
    """Self-test: ad-hoc commits are denied, the skill path is allowed, and `git commit` mentioned
    inside an unrelated command's payload is NOT mistaken for a real commit.
    Run: python3 enforce-git-commit-skill.py --test"""
    cases = [
        # (label, command, want_evaluate)  — evaluate True = allow, False = deny
        ("real commit -m",      "git commit -m 'fix'",                              False),
        ("skill commit -F",     "git commit -F /tmp/msg",                           True),
        ("amend --no-edit",     "git commit --amend --no-edit",                     True),
        ("agy prompt mentions", "agy -p 'remember to git commit daily'",            True),
        ("heredoc body",        "agy -p 'r' <<'EOF'\nabout git commit\nEOF",         True),
        ("git-commit in path",  "cat skills/git-commit/SKILL.md",                   True),
    ]
    ok = True
    for label, cmd, want in cases:
        got = evaluate(strip_payloads(cmd))
        mark = "✓" if got == want else "✗ FAIL"
        if got != want:
            ok = False
        print(f"  {mark}  {label}: evaluate={got} (want {want})")
    print("\n" + ("All tests passed." if ok else "SOME TESTS FAILED."))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_self_test()
    else:
        main()
