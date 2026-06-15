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
import re
import sys

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

    if not evaluate(command):
        print(json.dumps(DENY_RESPONSE))

    sys.exit(0)


if __name__ == "__main__":
    main()
