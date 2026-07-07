#!/usr/bin/env python3
"""
G2b — PreToolUse gate (Edit|Write|MultiEdit|NotebookEdit): no CODE edit off the linked git-flow branch.

Companion to br-edit-gate (G2). Where G2 enforces "an in_progress br step exists", this enforces
"the work happens on the right git-flow branch". Two rules:

  A. DENY a code edit on a base branch (gitflow production / develop). Work must move to a
     feature/bugfix branch first.
  B. DENY a code edit on a feature/bugfix branch that is NOT linked to the active step's epic via
     `external_ref` (the strict task<->branch link the br bracket was missing). One epic == one
     work branch; the branch name is recorded on the epic as `external_ref`.

Scope: GLOBAL hook; self-gates to beads projects (a `.beads/` dir above cwd) that are ALSO git-flow
initialized (`gitflow.branch.*` config present). No-op everywhere else — existing non-gitflow beads
repos stay untouched.
Submodule-aware: the branch/git-flow state checked is whichever repo actually CONTAINS the edited
file (via `gate_common.git_root_for`), not the beads workspace root. A file inside a git submodule
has its own independent branch/HEAD, nested under (but separate from) the outer/super-repo that
holds `.beads/` — checking the super-repo's branch there would be enforcing discipline on the wrong
repo, and force pointless "umbrella" branches in the super-repo just to unblock submodule edits.
Exempt paths (see `gate_common.path_exempt`): meta/doc dirs (`.beads/`, `workflow/`, `conductor/`,
`.claude/`), edits outside the beads root, git-ignored working files (e.g. `docs/apogee/**`), and any
`CLAUDE.md` — so bootstrap commands like `/apogee:init` are never blocked on a base branch. Code-only:
a non-code file (docs, configs, images — see `gate_common.is_code_file`) is never branch-scoped work,
so service commands (`/apogee:update-docs`, `/apogee:readme`, `/apogee:doc`, image-*) and ordinary
doc/config edits pass on any branch. Escape hatch: env `BR_GATE_OFF=1`.
Fail-open: any error / missing `br`/`git` / detached HEAD → allow (the Stop gate is the backstop;
never trap on infra).
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core", "lib"))
from gate_common import beads_root, deny, git_root_for, is_code_file, path_exempt  # noqa: E402


def _git(root, args):
    """Run a git command in `root`, return stripped stdout or '' on any failure."""
    try:
        r = subprocess.run(["git", "-C", root] + args,
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _br_show(root, issue_id):
    """`br show <id> --json` → the issue dict, or None on any error."""
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


def _epic_id(issue):
    """Resolve the parent-child epic id of an issue dict (direct field → dep edge → id prefix)."""
    pid = issue.get("parent")
    if pid:
        return pid
    for dep in (issue.get("dependencies") or []):
        if dep.get("dependency_type") == "parent-child" and dep.get("id"):
            return dep["id"]
    iid = issue.get("id") or ""
    if "." in iid:  # beads hierarchical child id: <epic>.N
        return iid.rsplit(".", 1)[0]
    return None


def main() -> None:
    if os.environ.get("BR_GATE_OFF") == "1":
        return
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}

    cwd = data.get("cwd") or os.getcwd()
    if not os.path.isdir(cwd):
        return
    root = beads_root(cwd)
    if not root:
        return  # not a beads project -> no-op

    # Exempt meta/doc paths, git-ignored working files, CLAUDE.md, edits outside the beads root.
    fp = (data.get("tool_input") or {}).get("file_path") or ""
    if path_exempt(root, fp):
        return

    # Code-only: non-code files aren't branch-scoped work, so service commands and doc/config edits
    # pass on any branch (incl. base branches).
    if not is_code_file(fp):
        return

    # The repo whose branch/git-flow state actually matters is whichever one CONTAINS `fp` -- a
    # submodule nested under the beads root has its own independent branch/HEAD, distinct from the
    # outer/super-repo `root` points at. Checking `root` here for a submodule-contained edit would
    # enforce discipline on the wrong repo (see module docstring).
    git_root = git_root_for(fp, root)

    # Only enforce in git-flow-initialized repos (decision: never brick non-gitflow beads repos).
    if not _git(git_root, ["config", "--get-regexp", r"^gitflow\.branch\."]):
        return

    branch = _git(git_root, ["branch", "--show-current"])
    if not branch:
        return  # detached HEAD / mid-rebase -> fail-open

    production = _git(git_root, ["config", "gitflow.branch.master"]) or "main"
    develop = _git(git_root, ["config", "gitflow.branch.develop"]) or "develop"
    base = {production, develop, "main", "master", "develop"}

    feat_prefix = _git(git_root, ["config", "gitflow.prefix.feature"]) or "feature/"
    bugfix_prefix = _git(git_root, ["config", "gitflow.prefix.bugfix"]) or "bugfix/"

    # realpath both sides before comparing/relpath-ing: git_root comes from `git rev-parse
    # --show-toplevel` (symlink-resolved), root from os.path.abspath (not resolved) -- on macOS
    # (/tmp -> /private/tmp, /var -> /private/var) that mismatch alone would make them compare
    # unequal and produce a nonsense "../../../.." relative path.
    real_git_root, real_root = os.path.realpath(git_root), os.path.realpath(root)
    where = ("" if real_git_root == real_root
             else f" (submodule at {os.path.relpath(real_git_root, real_root)})")

    # ── Rule A: no code edits on a base branch ──
    if branch in base:
        deny(
            f"On base branch '{branch}'{where}. Code changes must happen on a git-flow work "
            f"branch, never on {branch}. Start one for the active track via the git-flow skill "
            f"(`git flow feature start <epic-slug>`, or `bugfix` for a bug track), then link it: "
            f"`br update <epicId> --external-ref {feat_prefix}<epic-slug> "
            f"--actor \"${{BR_ACTOR:-assistant}}\"`. (Ad-hoc escape: set BR_GATE_OFF=1.)"
        )
        return

    # Link enforcement applies to feature/bugfix branches only; release/hotfix/support pass through.
    if not (branch.startswith(feat_prefix) or branch.startswith(bugfix_prefix)):
        return

    # ── Rule B: the work branch must be linked to the active step's epic via external_ref ──
    try:
        r = subprocess.run(
            ["br", "-q", "list", "--status", "in_progress", "--json", "--no-color"],
            capture_output=True, text=True, timeout=10, cwd=root,
        )
        obj = json.loads(r.stdout or "{}")
    except Exception:
        return  # fail-open on any br/parse error
    issues = obj.get("issues", [])
    if not issues:
        return  # no active step -> let br-edit-gate (G2) own that denial; don't double-deny

    epic_hint = None
    for issue in issues:
        show = _br_show(root, issue.get("id", ""))
        if not show:
            continue
        if show.get("external_ref") == branch:
            return  # the in_progress issue itself is linked to this branch -> allow
        epic = _epic_id(show)
        if epic:
            if epic_hint is None:
                epic_hint = epic
            eshow = _br_show(root, epic)
            if eshow and eshow.get("external_ref") == branch:
                return  # the issue's epic is linked to this branch -> allow

    target = epic_hint or "<epicId>"
    deny(
        f"Branch '{branch}'{where} is not linked to the active step's epic. Every git-flow work "
        f"branch must map 1:1 to a br epic via external_ref. Link it: "
        f"`br update {target} --external-ref '{branch}' --actor \"${{BR_ACTOR:-assistant}}\"`, "
        f"or checkout the branch already linked to this epic. (Ad-hoc escape: set BR_GATE_OFF=1.)"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail-open
    sys.exit(0)
