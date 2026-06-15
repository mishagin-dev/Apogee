#!/usr/bin/env python3
"""
PreToolUse hook — enforce full gitflow discipline in gitflow-enabled repos.

Active only when the current repo has gitflow config (`git config gitflow.branch.*`).
In all other repos the hook is completely inert — fail-open.

Rules enforced (in evaluation order):

1. ASK — git flow release|hotfix finish
   These merge into the production branch; require explicit user confirmation.

2. DENY — git commit outside a gitflow branch
   Commits are only allowed on feature/bugfix/release/hotfix/support branches.

3. DENY — manual git merge while ON the production branch
   The production branch only receives merges via `git flow release/hotfix finish`.

4. DENY — manual branch creation on a gitflow-prefixed name
   git checkout -b feature/..., git switch -c release/..., git branch hotfix/...

5. DENY — manual git merge of a gitflow-prefixed ref
   git merge feature/..., git merge release/...

Allows:
  - git flow <anything except release|hotfix finish>
  - git commit -F <file> on a gitflow branch
  - git merge <non-gitflow-ref> on a non-production branch
  - any non-git Bash call
  - everything in non-gitflow repos
"""

import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def _deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def _ask(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run(args, cwd):
    """Run a command and return stripped stdout, or '' on any failure."""
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _is_gitflow_repo(cwd):
    return bool(_run(["git", "-C", cwd, "config", "--get-regexp", r"^gitflow\.branch\."], cwd))


def _get_prefixes(cwd):
    """Return {type_name: prefix_string} for this repo, falling back to AVH defaults."""
    prefixes = {
        "feature": "feature/",
        "bugfix":  "bugfix/",
        "release": "release/",
        "hotfix":  "hotfix/",
        "support": "support/",
    }
    out = _run(["git", "-C", cwd, "config", "--get-regexp", r"^gitflow\.prefix\."], cwd)
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            prefixes[parts[0].rsplit(".", 1)[-1]] = parts[1]
    return prefixes


def _current_branch(cwd):
    return _run(["git", "-C", cwd, "branch", "--show-current"], cwd)


def _production_branch(cwd):
    # AVH stores the production branch under gitflow.branch.master regardless of its name.
    return _run(["git", "-C", cwd, "config", "gitflow.branch.master"], cwd) or "main"


def _prefix_type(ref, prefixes):
    """Return (type_name, slug) if ref starts with a gitflow prefix, else (None, None)."""
    for type_name, prefix in prefixes.items():
        if ref.startswith(prefix):
            return type_name, ref[len(prefix):]
    return None, None


# ---------------------------------------------------------------------------
# Regexes (hardened: no false-positives on paths containing "git-commit", etc.)
# ---------------------------------------------------------------------------

# Matches standalone `git flow release|hotfix finish ...`
_FLOW_FINISH_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])\s+flow\s+(release|hotfix)\s+finish\b"
)

# Matches any `git flow ...` command (used to short-circuit rules 2-5).
_FLOW_RE = re.compile(r"(?<![\w/.-])git(?![\w-])\s+flow\b")

# Matches a `git commit` invocation (not inside a path like skills/git-commit/...).
_COMMIT_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])[^|;&\n]*(?<![\w/.-])commit(?![\w-])"
)

# Matches a `git merge` invocation; capture group 1 = the merged ref.
_MERGE_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])[^|;&\n]*\bmerge\b[^|;&\n]*\s(\S+)\s*$"
)

# Matches manual branch creation on a gitflow-prefixed name.
_CREATE_RE = re.compile(
    r"""
    (?<![\w/.-])git(?![\w-])[^|;&\n]*
    (?:
        checkout\s[^|;&\n]*-[bcCB]\s+(?:\S+\s+)*(\S+)   # git checkout -b/-B NAME
      | switch\s[^|;&\n]*-[cC]\s+(?:\S+\s+)*(\S+)       # git switch -c/-C NAME
      | branch\s+(?!-[dD])(\S+)                          # git branch NAME (not delete)
    )
    """,
    re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        cwd = payload.get("cwd") or os.getcwd()
    except Exception:
        sys.exit(0)  # fail open

    if "git" not in command:
        sys.exit(0)

    if not _is_gitflow_repo(cwd):
        sys.exit(0)

    prefixes = _get_prefixes(cwd)

    # ── Rule 1: ASK before release/hotfix finish (touches production branch) ──
    if _FLOW_FINISH_RE.search(command):
        _ask(
            "This command merges into the production branch and creates a release tag. "
            "It must only run on explicit user request — please confirm."
        )
        sys.exit(0)

    # ── All other `git flow` commands are allowed ──
    if _FLOW_RE.search(command):
        sys.exit(0)

    # ── Rule 2: DENY git commit outside a gitflow branch ──
    if _COMMIT_RE.search(command):
        branch = _current_branch(cwd)
        if branch:  # empty = detached HEAD / mid-rebase → fail-open
            type_name, _ = _prefix_type(branch, prefixes)
            if not type_name:
                _deny(
                    f"In gitflow repos, commits are only allowed on gitflow branches "
                    f"(feature/bugfix/release/hotfix/support). "
                    f"Current branch '{branch}' is not a gitflow branch. "
                    f"Start one first: `git flow <type> start <name>`."
                )
        sys.exit(0)

    # ── Rule 3: DENY manual git merge while ON the production branch ──
    if _MERGE_RE.search(command):
        branch = _current_branch(cwd)
        production = _production_branch(cwd)
        if branch and branch == production:
            _deny(
                f"The production branch '{production}' only receives merges via "
                "`git flow release finish` or `git flow hotfix finish` "
                "(both require user confirmation). Manual `git merge` here is not allowed."
            )
            sys.exit(0)

        # Rule 5: DENY merge of a gitflow-prefixed ref on any branch
        m = _MERGE_RE.search(command)
        if m:
            ref = m.group(1)
            type_name, slug = _prefix_type(ref, prefixes)
            if type_name:
                _deny(
                    f"Use the git-flow skill (~/.claude/skills/git-flow/SKILL.md) instead: "
                    f"`git flow {type_name} finish {slug}`. "
                    f"Manual `git merge {ref}` on gitflow-prefixed branches is not allowed."
                )
        sys.exit(0)

    # ── Rule 4: DENY manual branch creation on gitflow-prefixed names ──
    m = _CREATE_RE.search(command)
    if m:
        ref = next(g for g in m.groups() if g is not None)
        type_name, slug = _prefix_type(ref, prefixes)
        if type_name:
            _deny(
                f"Use the git-flow skill (~/.claude/skills/git-flow/SKILL.md) instead: "
                f"`git flow {type_name} start {slug}`. "
                f"Manual branch creation of `{ref}` is not allowed."
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
