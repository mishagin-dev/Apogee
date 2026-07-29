"""Shared git-flow helpers for hooks/git/*.py scripts. Part of the apogee plugin.

Also carries the few generic hook primitives the git group still needs (`ask`, `strip_payloads`)
and the `br` queries Rule 2b uses. These lived in `hooks/core/lib/gate_common.py` until ADR 0005
deleted the gates that were its other consumers -- with no cross-group users left, `core/lib/` was
dissolved and its survivors moved into the group that actually uses them.
"""

import json
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


# A leading `cd <dir>` before the git command (`cd sub && git commit`, `cd sub; git ...`, or
# `cd sub` on its own line followed by `git ...` on the next -- a real multi-line Bash tool call
# executes newline-separated commands sequentially exactly like `;`, so `\n` must be a boundary
# token too; a bare `\s*` alone doesn't count as one on its own, only literally following one of
# these tokens does). Anchored to start-of-string or a shell chain operator so an inner `... cd
# ...` inside an argument is not mistaken for the shell's working-directory change.
_CD_RE = re.compile(r"(?:^|&&|\|\||;|&|\n)\s*cd\s+(?P<dir>[^\s;&|]+)")

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


# ── Generic hook primitives (relocated from the dissolved core/lib/gate_common.py) ────────────

def ask(reason):
    """Emit a PreToolUse ask decision (surfaces a confirmation prompt)."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))


def deny(reason):
    """Emit a PreToolUse deny decision."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def strip_payloads(cmd: str) -> str:
    """Remove quoted-string and heredoc payloads so git-op regexes only see real commands, not git
    mentions inside another command's arguments.

    Without this, `agy -p 'remember to git flow release finish'` would false-match and ASK on an
    unrelated tool call -- the reported symptom of `/apogee:second-opinion` being blocked. Real git
    commands keep their operative verb outside quotes, so detection is preserved.
    """
    # Heredoc bodies: <<MARK ... MARK (also <<-MARK and quoted markers), across newlines.
    cmd = re.sub(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?.*?\n\1(?![\w-])", " ", cmd, flags=re.DOTALL)
    cmd = re.sub(r'"[^"]*"', " ", cmd)   # double-quoted strings
    cmd = re.sub(r"'[^']*'", " ", cmd)   # single-quoted strings
    return cmd


# ── br queries (Rule 2b only -- the autonomous open-children check) ───────────────────────────

def br_show(root, issue_id):
    """`br show <id> --json` -> the issue dict, or None on any error."""
    try:
        r = subprocess.run(["br", "-q", "show", issue_id, "--json", "--no-color"],
                           capture_output=True, text=True, timeout=10, cwd=root)
        obj = json.loads(r.stdout or "null")
    except Exception:
        return None
    if isinstance(obj, list):
        return obj[0] if obj else None
    if isinstance(obj, dict) and "error" not in obj:
        return obj
    return None


def _br_list_all(root):
    """`br list --all --json` -> the issues array (summary objects: no `parent`/`external_ref`,
    those appear only in `br show`), or None on any br/parse error."""
    try:
        r = subprocess.run(["br", "-q", "list", "--all", "--json", "--no-color"],
                           capture_output=True, text=True, timeout=10, cwd=root)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout or "{}").get("issues", [])
    except Exception:
        return None


def br_find_by_external_ref(root, ref):
    """Find the issue whose `external_ref` equals `ref`.

    Returns (issue_dict_or_None, query_ok). `br list` omits `external_ref`, so this lists candidate
    ids then calls `br_show` per candidate. `query_ok` is False on any br/parse error -- distinct
    from "found nothing", so a fail-closed caller can tell "couldn't check" from "checked, no match".
    """
    candidates = _br_list_all(root)
    if candidates is None:
        return None, False
    for candidate in candidates:
        show = br_show(root, candidate.get("id", ""))
        if show and show.get("external_ref") == ref:
            return show, True
    return None, True


def br_open_children(root, epic_id):
    """Ids of `epic_id`'s children not in status "closed". Returns (ids, query_ok).

    `status` IS in the list summary, so closed candidates are skipped without a `show` call;
    `parent` is not, so every still-open candidate needs one to check parentage.
    """
    candidates = _br_list_all(root)
    if candidates is None:
        return None, False
    ids = []
    for candidate in candidates:
        if candidate.get("status") == "closed":
            continue
        cid = candidate.get("id")
        if not cid:
            continue
        show = br_show(root, cid)
        # Use the list view's own id, not show.get("id") -- a malformed `show` response must not
        # poison the caller's ", ".join(...).
        if show and show.get("parent") == epic_id:
            ids.append(cid)
    return ids, True
