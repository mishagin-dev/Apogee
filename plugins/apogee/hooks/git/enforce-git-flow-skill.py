#!/usr/bin/env python3
"""
PreToolUse hook — enforce full gitflow discipline in gitflow-enabled repos.

Active only when the current repo has gitflow config (`git config gitflow.branch.*`).
In all other repos the hook is completely inert — fail-open.

Rules enforced (in evaluation order):

1. ASK — git flow release|hotfix finish
   These merge into the production branch; require explicit user confirmation.

2. ASK — git flow feature|bugfix start while another feature/bugfix branch is still open
   One logical change per branch, finished before the next starts (see CLAUDE.md "Decompose
   complex work"). The user confirms whether the new work is genuinely more urgent.

3. DENY — git commit outside a gitflow branch
   Commits are only allowed on feature/bugfix/release/hotfix/support branches.

4. DENY — manual git merge while ON the production branch
   The production branch only receives merges via `git flow release/hotfix finish`.

5. DENY — manual branch creation on a gitflow-prefixed name
   git checkout -b feature/..., git switch -c release/..., git branch hotfix/...

6. DENY — manual git merge of a gitflow-prefixed ref
   git merge feature/..., git merge release/...

Allows:
  - git flow <anything except release|hotfix finish, feature|bugfix start>
  - git commit -F <file> on a gitflow branch
  - git merge <non-gitflow-ref> on a non-production branch
  - any non-git Bash call
  - everything in non-gitflow repos
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core", "lib"))
from gate_common import deny, ask, strip_payloads  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from gitflow_common import (  # noqa: E402
    run as _run,
    is_gitflow_repo as _is_gitflow_repo,
    get_prefixes as _get_prefixes,
    current_branch as _current_branch,
    production_branch as _production_branch,
    prefix_type as _prefix_type,
    open_work_branches as _open_work_branches,
    effective_repo as _effective_repo,
)


# ---------------------------------------------------------------------------
# Regexes (hardened: no false-positives on paths containing "git-commit", etc.)
# ---------------------------------------------------------------------------

# Matches standalone `git flow release|hotfix finish ...`
_FLOW_FINISH_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])\s+flow\s+(release|hotfix)\s+finish\b"
)

# Matches any `git flow ...` command (used to short-circuit rules 3-6).
_FLOW_RE = re.compile(r"(?<![\w/.-])git(?![\w-])\s+flow\b")

# Matches standalone `git flow feature|bugfix start ...`; capture group 1 = the type.
_FLOW_START_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])\s+flow\s+(feature|bugfix)\s+start\b"
)

# Matches a `git commit` invocation (not inside a path like skills/git-commit/...).
_COMMIT_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])[^|;&\n]*(?<![\w/.-])commit(?![\w-])"
)

# Matches a `git merge` invocation; named group "rest" = everything after the `merge` keyword.
_MERGE_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])[^|;&\n]*\bmerge\b(?P<rest>[^|;&\n]*)"
)


def _merged_gitflow_ref(rest, prefixes):
    """Scan the args following `merge` for a token matching a gitflow prefix.

    A real merge command carries flags before AND/OR after the ref (`--no-ff`, `-m <msg>`), so
    the ref is not reliably the first or last whitespace token -- e.g. `git merge feature/x
    --no-ff -m "..."` (this repo's own merge.md template) has `-m` as the last token once the
    quoted message is stripped. Check every token instead of assuming a fixed position.
    """
    for tok in rest.split():
        type_name, slug = _prefix_type(tok, prefixes)
        if type_name:
            return tok, type_name, slug
    return None, None, None

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

    # Drop quoted/heredoc payloads so git-op regexes don't false-match inside another command's
    # arguments (e.g. `agy -p '...git commit...'` is not a git commit). See _strip_payloads.
    command = strip_payloads(command)

    if "git" not in command:
        sys.exit(0)

    # Judge the repo the git command actually TARGETS, not the session cwd: `git -C sub commit`
    # or `cd sub && git commit` operates on a submodule with its own branch/HEAD. Checking the
    # super-repo's branch there wrongly denied submodule commits on a base super-repo branch and
    # forced pointless "umbrella" branches -- the same trap the br-branch-gate already avoids.
    cwd = _effective_repo(command, cwd)

    if not _is_gitflow_repo(cwd):
        sys.exit(0)

    prefixes = _get_prefixes(cwd)

    # ── Rule 1: ASK before release/hotfix finish (touches production branch) ──
    if _FLOW_FINISH_RE.search(command):
        ask(
            "This command merges into the production branch and creates a release tag. "
            "It must only run on explicit user request — please confirm."
        )
        sys.exit(0)

    # ── Rule 2: ASK before starting a new feature/bugfix while another is still open ──
    m = _FLOW_START_RE.search(command)
    if m:
        new_type = m.group(1)
        open_branches = _open_work_branches(cwd, prefixes)
        if open_branches:
            names = ", ".join(
                f"{t}/{s}" + (" (already merged into develop -- just needs `git flow "
                              f"{t} finish {s}` to clean it up)" if merged else "")
                for t, s, merged in open_branches
            )
            ask(
                f"Starting a new {new_type} branch while {names} is still open. "
                f"Finish it first via /apogee:merge (or the git-flow skill) before starting the "
                f"next one -- unless this new work is genuinely more urgent or higher-priority "
                f"than what's open. Confirm to proceed anyway."
            )
        sys.exit(0)

    # ── All other `git flow` commands are allowed ──
    if _FLOW_RE.search(command):
        sys.exit(0)

    # ── Rule 3: DENY git commit outside a gitflow branch ──
    if _COMMIT_RE.search(command):
        branch = _current_branch(cwd)
        if branch:  # empty = detached HEAD / mid-rebase → fail-open
            type_name, _ = _prefix_type(branch, prefixes)
            if not type_name:
                deny(
                    f"In gitflow repos, commits are only allowed on gitflow branches "
                    f"(feature/bugfix/release/hotfix/support). "
                    f"Current branch '{branch}' is not a gitflow branch. "
                    f"Start one first: `git flow <type> start <name>`."
                )
        sys.exit(0)

    # ── Rule 4: DENY manual git merge while ON the production branch ──
    if _MERGE_RE.search(command):
        branch = _current_branch(cwd)
        production = _production_branch(cwd)
        if branch and branch == production:
            deny(
                f"The production branch '{production}' only receives merges via "
                "`git flow release finish` or `git flow hotfix finish` "
                "(both require user confirmation). Manual `git merge` here is not allowed."
            )
            sys.exit(0)

        # Rule 6: DENY merge of a gitflow-prefixed ref on any branch
        m = _MERGE_RE.search(command)
        if m:
            ref, type_name, slug = _merged_gitflow_ref(m.group("rest"), prefixes)
            if type_name:
                deny(
                    f"Use the git-flow skill (plugins/apogee/skills/git-flow/SKILL.md) instead: "
                    f"`git flow {type_name} finish {slug}`. "
                    f"Manual `git merge {ref}` on gitflow-prefixed branches is not allowed."
                )
        sys.exit(0)

    # ── Rule 5: DENY manual branch creation on gitflow-prefixed names ──
    m = _CREATE_RE.search(command)
    if m:
        ref = next(g for g in m.groups() if g is not None)
        type_name, slug = _prefix_type(ref, prefixes)
        if type_name:
            deny(
                f"Use the git-flow skill (plugins/apogee/skills/git-flow/SKILL.md) instead: "
                f"`git flow {type_name} start {slug}`. "
                f"Manual branch creation of `{ref}` is not allowed."
            )

    sys.exit(0)


def _run_self_test() -> None:
    """Self-test: git-op regexes must NOT false-match inside quoted/heredoc payloads.
    Run: python3 enforce-git-flow-skill.py --test"""
    cases = [
        # (label, command, should _COMMIT_RE match after _strip_payloads?)
        ("real commit -m",        "git commit -m 'fix'",                              True),
        ("real commit -F",        "git commit -F /tmp/msg",                           True),
        ("chained commit",        "git add . && git commit",                          True),
        ("agy prompt mentions",   "agy -p 'remember to git commit daily'",            False),
        ("agy merge in prompt",   "agy -p 'then git merge feature/x'",                False),
        ("heredoc body mentions", "agy -p 'r' <<'EOF'\nthink about git commit\nEOF",  False),
        ("git-commit in path",    "cat skills/git-commit/SKILL.md",                   False),
    ]
    ok = True
    for label, cmd, want in cases:
        got = bool(_COMMIT_RE.search(strip_payloads(cmd)))
        mark = "✓" if got == want else "✗ FAIL"
        if got != want:
            ok = False
        print(f"  {mark}  {label}: _COMMIT_RE match={got} (want {want})")
    if _MERGE_RE.search(strip_payloads("agy -p 'git merge feature/x now'")):
        print("  ✗ FAIL  _MERGE_RE saw a ref inside an agy prompt")
        ok = False
    else:
        print("  ✓  _MERGE_RE ignores git-merge inside a quoted payload")

    # Rule 6 must catch the ref even when flags follow it (--no-ff, -m "msg") -- not just when
    # the ref happens to be the last token. This is the exact shape merge.md's own template uses.
    test_prefixes = {"feature": "feature/", "bugfix": "bugfix/", "release": "release/",
                      "hotfix": "hotfix/", "support": "support/"}
    merge_cases = [
        ("ref then --no-ff",       "git merge feature/x --no-ff",                             "feature/x"),
        ("ref then -m message",    'git merge feature/x --no-ff -m "Merge branch feature/x"', "feature/x"),
        ("--no-ff then ref",       "git merge --no-ff feature/x",                             "feature/x"),
        ("non-gitflow ref",        "git merge some-other-branch --no-ff",                     None),
    ]
    for label, cmd, want_ref in merge_cases:
        m = _MERGE_RE.search(strip_payloads(cmd))
        got_ref = None
        if m:
            got_ref, _, _ = _merged_gitflow_ref(m.group("rest"), test_prefixes)
        mark = "✓" if got_ref == want_ref else "✗ FAIL"
        if got_ref != want_ref:
            ok = False
        print(f"  {mark}  {label}: detected ref={got_ref} (want {want_ref})")

    # effective_repo must retarget submodule git ops (`-C sub`, `cd sub && ...`) to the submodule
    # dir, ignore the message-reuse `git commit -C <commit>`, and fall back to cwd otherwise.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sub = os.path.normpath(os.path.join(tmp, "sub"))
        os.makedirs(sub)
        repo_cases = [
            ("git -C sub commit",          "git -C sub commit -m x",  sub),
            ("cd sub && git commit",       "cd sub && git commit -m x", sub),
            ("cd sub; git commit",         "cd sub; git commit",      sub),
            ("commit -C HEAD (not a dir)", "git commit -C HEAD",      tmp),
            ("plain commit → cwd",         "git commit -m x",         tmp),
            ("nonexistent -C dir → cwd",   "git -C nope commit",      tmp),
            ("-C sub overrides -C HEAD",   "git -C sub commit -C HEAD", sub),
        ]
        for label, cmd, want_dir in repo_cases:
            got_dir = _effective_repo(cmd, tmp)
            mark = "✓" if got_dir == want_dir else "✗ FAIL"
            if got_dir != want_dir:
                ok = False
            print(f"  {mark}  {label}: effective_repo={got_dir!r} (want {want_dir!r})")

    print("\n" + ("All tests passed." if ok else "SOME TESTS FAILED."))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_self_test()
    else:
        main()
