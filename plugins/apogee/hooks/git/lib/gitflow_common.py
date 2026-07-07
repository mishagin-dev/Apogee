"""Shared git-flow helpers for hooks/git/*.py scripts. Part of the apogee plugin."""

import subprocess

DEFAULT_PREFIXES = {
    "feature": "feature/",
    "bugfix":  "bugfix/",
    "release": "release/",
    "hotfix":  "hotfix/",
    "support": "support/",
}


def run(args, cwd):
    """Run a command and return stripped stdout, or '' on any failure."""
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def is_gitflow_repo(cwd):
    return bool(run(["git", "-C", cwd, "config", "--get-regexp", r"^gitflow\.branch\."], cwd))


def get_prefixes(cwd):
    """Return {type_name: prefix_string} for this repo, falling back to AVH defaults."""
    prefixes = dict(DEFAULT_PREFIXES)
    out = run(["git", "-C", cwd, "config", "--get-regexp", r"^gitflow\.prefix\."], cwd)
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            prefixes[parts[0].rsplit(".", 1)[-1]] = parts[1]
    return prefixes


def current_branch(cwd):
    return run(["git", "-C", cwd, "branch", "--show-current"], cwd)


def production_branch(cwd):
    # AVH stores the production branch under gitflow.branch.master regardless of its name.
    return run(["git", "-C", cwd, "config", "gitflow.branch.master"], cwd) or "main"


def develop_branch(cwd):
    return run(["git", "-C", cwd, "config", "gitflow.branch.develop"], cwd) or "develop"


def is_fully_merged(cwd, branch, base):
    """True if `branch` has no commits `base` doesn't already have.

    Signals a branch whose content already landed on `base` by some means OTHER than `git flow
    ... finish` (a manual merge, cherry-pick, etc.) -- `finish` would have deleted it. Checks the
    exit code explicitly (unlike `run()`) so a failed/erroring git call can never be mistaken for
    "no commits" -- fails open (False) on any error.
    """
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "log", f"{base}..{branch}", "--oneline"],
            capture_output=True, text=True, timeout=3,
        )
        return r.returncode == 0 and r.stdout.strip() == ""
    except Exception:
        return False


def prefix_type(ref, prefixes):
    """Return (type_name, slug) if ref starts with a gitflow prefix, else (None, None)."""
    for type_name, prefix in prefixes.items():
        if ref.startswith(prefix):
            return type_name, ref[len(prefix):]
    return None, None


def open_work_branches(cwd, prefixes):
    """Return [(type_name, slug, merged_into_develop), ...] for existing local feature/bugfix
    branches. `merged_into_develop` is True when the branch's content already landed on develop
    by some means other than `git flow ... finish` (that would have deleted it) -- a stale
    candidate for cleanup, distinct from genuinely unfinished work.

    Used both to ASK before starting a new one (enforce-git-flow-skill.py) and to nudge the
    agent to mention them when a new user prompt arrives (unfinished-branch-nudge.py).
    """
    out = run(["git", "-C", cwd, "branch", "--format=%(refname:short)"], cwd)
    base = develop_branch(cwd)
    result = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        type_name, slug = prefix_type(line, prefixes)
        if type_name in ("feature", "bugfix"):
            result.append((type_name, slug, is_fully_merged(cwd, line, base)))
    return result
