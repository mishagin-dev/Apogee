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


def prefix_type(ref, prefixes):
    """Return (type_name, slug) if ref starts with a gitflow prefix, else (None, None)."""
    for type_name, prefix in prefixes.items():
        if ref.startswith(prefix):
            return type_name, ref[len(prefix):]
    return None, None


def open_work_branches(cwd, prefixes):
    """Return [(type_name, slug), ...] for existing local feature/bugfix branches.

    Used both to ASK before starting a new one (enforce-git-flow-skill.py) and to nudge the
    agent to mention them when a new user prompt arrives (unfinished-branch-nudge.py).
    """
    out = run(["git", "-C", cwd, "branch", "--format=%(refname:short)"], cwd)
    result = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        type_name, slug = prefix_type(line, prefixes)
        if type_name in ("feature", "bugfix"):
            result.append((type_name, slug))
    return result
