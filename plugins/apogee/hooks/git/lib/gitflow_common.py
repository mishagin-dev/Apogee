"""Shared git-flow helpers for hooks/git/*.py scripts. Part of the apogee plugin."""

import os
import re
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


# A leading `cd <dir>` before the git command (`cd sub && git commit`, `cd sub; git ...`).
# Anchored to start-of-string or a shell chain operator so an inner `... cd ...` inside an
# argument is not mistaken for the shell's working-directory change.
_CD_RE = re.compile(r"(?:^|&&|\|\||;|&)\s*cd\s+(?P<dir>[^\s;&|]+)")

# git's GLOBAL `-C <dir>` option (`git -C sub commit`). Non-greedy up to the FIRST `-C` after
# `git` so `git -C sub commit -C HEAD` grabs `sub`, not the commit-message-reuse `-C HEAD`; the
# isdir() backstop in effective_repo() discards any `-C` value (a sha, HEAD, a branch) that is
# not an actual directory. The `(?![\w-])` after git avoids matching `git-foo`.
_DASH_C_RE = re.compile(r"(?<![\w/.-])git(?![\w-])[^|;&\n]*?\s-C\s+(?P<dir>[^\s;&|]+)")


def _resolve_dir(raw, base):
    """Resolve a raw `cd`/`-C` argument against `base`; return the dir if it exists, else None."""
    raw = (raw or "").strip("'\"")
    if not raw or raw == ".":
        return None  # no-op: keep `base`
    path = raw if os.path.isabs(raw) else os.path.join(base, raw)
    path = os.path.normpath(path)
    return path if os.path.isdir(path) else None


def effective_repo(command, cwd):
    """Return the directory the git command actually targets, so branch/gitflow checks run
    against the RIGHT repo -- a submodule commit (`git -C sub commit`, `cd sub && git commit`)
    must be judged by the submodule's own branch, not the session's super-repo (mirrors the
    submodule-aware br-branch-gate). Applies a leading `cd`, then git's global `-C`, mirroring
    shell + git semantics; falls back to `cwd` when neither is present or resolvable.
    """
    d = cwd
    m = _CD_RE.search(command)
    if m:
        d = _resolve_dir(m.group("dir"), d) or d
    m = _DASH_C_RE.search(command)
    if m:
        d = _resolve_dir(m.group("dir"), d) or d
    return d


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
