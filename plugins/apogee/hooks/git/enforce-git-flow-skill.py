#!/usr/bin/env python3
"""
PreToolUse hook — enforce full gitflow discipline in gitflow-enabled repos.

Active only when the current repo has gitflow config (`git config gitflow.branch.*`).
In all other repos the hook is completely inert — fail-open.

Rules enforced (numbered by concern, NOT evaluation order -- see the note on 2b below):

1. ASK — git flow release|hotfix finish
   These merge into the production branch; require explicit user confirmation.

2. ASK — git flow feature|bugfix start while another feature/bugfix branch is still open
   One logical change per branch, finished before the next starts (see CLAUDE.md "Decompose
   complex work"). The user confirms whether the new work is genuinely more urgent.
   Bypassed when the command is tagged `APOGEE_RUN_PLAN=1` (see run_plan_tagged) -- the
   /apogee:run-plan autonomous loop always finishes one branch before starting the next, so this
   never legitimately fires there; the bypass is a robustness net, not the primary mechanism.

2b. DENY — git flow feature|bugfix finish while the linked epic has open (non-closed) children
   The structural safety backstop for /apogee:run-plan: a git-flow branch maps 1:1 to a br epic
   (external_ref), and finishing it should mean all of the epic's steps are done. Fails OPEN (allows,
   matching every other hook's repo-wide convention) when the command is a plain manual finish and the
   br query errors -- a human is present and would likely notice via other cues. Fails CLOSED (denies)
   when the command is tagged `APOGEE_RUN_PLAN=1` and the br query errors -- an unattended autonomous
   finish must not proceed on an unverifiable claim that the work is complete.
   EVALUATED FIRST, ahead of rules 1 and 2: every rule here does `.search()` on the raw command
   string and exits unconditionally on its own match, with no awareness of what else might be
   chained in a compound command (`a && b`). If 2b were checked after 1/2, a command like
   `git flow feature start decoy && git flow feature finish <slug-with-open-children>` would let
   rule 2 consume the match and exit before 2b ever saw the `finish` half of the same string --
   silently defeating the one structural backstop /apogee:run-plan's safety model depends on.
   Checking 2b first and only exiting early on an actual deny (falling through otherwise on
   allow/no-match) closes that hole without changing behavior for any command that doesn't contain
   a feature/bugfix finish at all.

3. DENY — git commit outside a gitflow branch
   Commits are only allowed on feature/bugfix/release/hotfix/support branches.

4. DENY — manual git merge while ON the production branch
   The production branch only receives merges via `git flow release/hotfix finish`.

5. DENY — manual branch creation on a gitflow-prefixed name
   git checkout -b feature/..., git switch -c release/..., git branch hotfix/...

6. DENY — manual git merge of a gitflow-prefixed ref
   git merge feature/..., git merge release/...

Allows:
  - git flow <anything except release|hotfix finish, feature|bugfix start, feature|bugfix finish
    with open children>
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
from gate_common import (  # noqa: E402
    deny, ask, strip_payloads, br_find_by_external_ref, br_open_children,
)

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

# Matches standalone `git flow feature|bugfix finish <rest>`; capture group 1 = the type,
# named group "rest" = everything after `finish` (flags like -k/--no-ff may precede the slug).
_FLOW_FEATURE_BUGFIX_FINISH_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])\s+flow\s+(feature|bugfix)\s+finish\b(?P<rest>[^|;&\n]*)"
)

# Literal command-string tag /apogee:run-plan prefixes onto the exact `git flow ... start`/
# `... finish` invocations its autonomous loop issues. Stateless by design: no marker file, no env
# var, nothing to leak across a crash or a later unrelated command -- see run-plan.md. Matched at
# any command boundary (start of string, or after &&/;/|/&), not just a strict string-prefix, so
# `cd sub && APOGEE_RUN_PLAN=1 git flow ...` is still recognized -- run-plan.md's documented usage
# is a bare prefix, but this is cheap insurance against a plausible, non-adversarial wrapping that
# would otherwise silently downgrade a tagged finish to the weaker fail-open manual path.
_RUN_PLAN_TAG_RE = re.compile(r"(?:^|&&|\|\||;|&)\s*APOGEE_RUN_PLAN=1(?:\s|$)")


def _run_plan_tagged(command: str) -> bool:
    """True if `command` (post-strip_payloads) carries the /apogee:run-plan autonomous tag."""
    return bool(_RUN_PLAN_TAG_RE.search(command))


def _finish_slug(rest: str, cwd: str, type_name: str, prefixes: dict):
    """The slug `git flow <type> finish` operates on.

    An explicit slug (first non-flag token after `finish`) wins. Omitted entirely -- valid,
    common AVH git-flow usage that finishes the CURRENTLY CHECKED OUT branch -- falls back to
    `_current_branch(cwd)`, stripping its `<type>` prefix. Returns None only if neither resolves
    (e.g. detached HEAD with no explicit slug), in which case the caller has nothing to check.
    """
    for tok in rest.split():
        if not tok.startswith("-"):
            return tok
    branch = _current_branch(cwd)
    prefix = prefixes.get(type_name, f"{type_name}/")
    if branch and branch.startswith(prefix):
        return branch[len(prefix):]
    return None


def _rule_2b_decision(command: str, cwd: str, prefixes: dict):
    """Decide Rule 2b for a `git flow feature|bugfix finish` command.

    Returns a deny reason (str) to block, or None to allow. Factored out of main() so the
    fail-open/fail-closed split can be unit-tested by monkeypatching br_find_by_external_ref /
    br_open_children, without needing a real `br` sandbox for every branch of this logic (a real
    sandbox still separately covers the end-to-end happy/deny path -- see --test).
    """
    m = _FLOW_FEATURE_BUGFIX_FINISH_RE.search(command)
    if not m:
        return None
    tagged = _run_plan_tagged(command)
    type_name = m.group(1)
    slug = _finish_slug(m.group("rest"), cwd, type_name, prefixes)
    if not slug:
        return None
    branch = f"{prefixes.get(type_name, type_name + '/')}{slug}"
    epic, query_ok = br_find_by_external_ref(cwd, branch)
    if not query_ok:
        if tagged:
            return (
                f"Could not verify via br whether epic linked to '{branch}' has open "
                f"steps (br query failed) -- refusing to finish autonomously without that "
                f"guarantee. Retry, or finish manually to proceed despite the check failure."
            )
        return None  # untagged (manual): fail open, matching every other hook's convention here.
    if not epic:
        # No epic linked to this branch -- nothing to check, allow (matches the existing
        # convention elsewhere in this repo that an unlinked branch isn't this gate's problem).
        return None
    open_children, query_ok2 = br_open_children(cwd, epic.get("id", ""))
    if not query_ok2:
        if tagged:
            return (
                f"Could not verify via br whether epic {epic.get('id')} (linked to "
                f"'{branch}') has open steps (br query failed) -- refusing to finish "
                f"autonomously without that guarantee."
            )
        return None
    if open_children:
        return (
            f"Epic {epic.get('id')} (linked to '{branch}') still has open steps: "
            f"{', '.join(open_children)}. Close them in br before finishing this branch."
        )
    return None

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

    # ── Rule 2b: DENY finishing a feature/bugfix branch whose linked epic has open children ──
    # Checked FIRST, before Rules 1/2 -- every other rule below exits unconditionally on its own
    # match via `.search()`, which only looks for ITS pattern anywhere in the string and doesn't
    # care what else is chained alongside it. If Rule 2b were checked after Rule 1/Rule 2, a
    # compound command like `git flow feature start decoy && git flow feature finish <slug>`
    # would let Rule 2 consume the match and exit before Rule 2b ever saw the `finish` half of the
    # SAME string -- silently defeating the one structural safety backstop /apogee:run-plan
    # depends on. Checking it first, and only exiting early on an actual DENY (falling through
    # otherwise), closes that hole: a genuine violation anywhere in the command always wins,
    # regardless of what other git-flow verb happens to be chained around it.
    #
    # The backstop itself: a git-flow branch maps 1:1 to a br epic via external_ref (see the
    # git-flow skill's "beads link" convention), and finishing it should mean the epic's steps are
    # all done. Fail-open/fail-closed split (see module docstring and _rule_2b_decision): a plain
    # manual finish fails OPEN on any br error (repo-wide convention, a human is watching); an
    # /apogee:run-plan-tagged finish fails CLOSED (denies) on any br error, since an unattended
    # autonomous finish must not proceed on an unverifiable claim of completion.
    if _FLOW_FEATURE_BUGFIX_FINISH_RE.search(command):
        reason = _rule_2b_decision(command, cwd, prefixes)
        if reason:
            deny(reason)
            sys.exit(0)
        # Allowed (or nothing to check) -- fall through; don't assume this is the only git-flow
        # operation in the command string.

    # ── Rule 1: ASK before release/hotfix finish (touches production branch) ──
    if _FLOW_FINISH_RE.search(command):
        ask(
            "This command merges into the production branch and creates a release tag. "
            "It must only run on explicit user request — please confirm."
        )
        sys.exit(0)

    # ── Rule 2: ASK before starting a new feature/bugfix while another is still open ──
    # Bypassed for /apogee:run-plan's tagged commands: a disciplined autonomous loop always
    # finishes one branch before starting the next, so this never legitimately fires there.
    m = _FLOW_START_RE.search(command)
    if m:
        new_type = m.group(1)
        open_branches = _open_work_branches(cwd, prefixes)
        if open_branches and not _run_plan_tagged(command):
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
    import subprocess
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

    # _run_plan_tagged: pure string parsing for the /apogee:run-plan tag mechanism. Matched at any
    # command boundary, not just a strict string-prefix (see _RUN_PLAN_TAG_RE).
    tag_cases = [
        ("tagged start (bare prefix)", "APOGEE_RUN_PLAN=1 git flow feature start demo", True),
        ("untagged start",             "git flow feature start demo",                   False),
        ("tag after && (cd-wrapped)",
         "cd sub && APOGEE_RUN_PLAN=1 git flow feature finish demo",                    True),
        ("tag after ;",                "true; APOGEE_RUN_PLAN=1 git flow feature start demo", True),
        ("tag mid-token (not a boundary -- must not match)",
                               "git flow feature start APOGEE_RUN_PLAN=1demo", False),
        ("tag as substring of an unrelated word -- must not match",
                               "echo NOTAPOGEE_RUN_PLAN=1 && git flow feature start demo", False),
    ]
    for label, cmd, want in tag_cases:
        got = _run_plan_tagged(cmd)
        mark = "✓" if got == want else "✗ FAIL"
        if got != want:
            ok = False
        print(f"  {mark}  {label}: _run_plan_tagged={got} (want {want})")

    # _finish_slug: explicit-slug parsing, plus the current-branch fallback for a slug-less
    # `git flow <type> finish` (valid AVH usage -- finishes whatever branch is checked out).
    test_prefixes2 = {"feature": "feature/", "bugfix": "bugfix/"}
    with tempfile.TemporaryDirectory() as tmp2:
        subprocess.run(["git", "-C", tmp2, "init", "-q", "-b", "feature/on-branch"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", tmp2, "-c", "user.email=t@t.com", "-c", "user.name=t",
                        "commit", "-q", "--allow-empty", "-m", "x"], check=True, capture_output=True)
        finish_slug_cases = [
            ("plain slug",              "demo",           tmp2, "feature", "demo"),
            ("flag then slug",          " -k demo",       tmp2, "feature", "demo"),
            ("slug then flag",          " demo --no-ff",  tmp2, "feature", "demo"),
            ("no slug -> current branch fallback", "",     tmp2, "feature", "on-branch"),
            ("no slug, wrong type prefix on branch -> None", "", tmp2, "bugfix", None),
        ]
        for label, rest, cwd_, type_, want in finish_slug_cases:
            got = _finish_slug(rest, cwd_, type_, test_prefixes2)
            mark = "✓" if got == want else "✗ FAIL"
            if got != want:
                ok = False
            print(f"  {mark}  {label}: _finish_slug={got!r} (want {want!r})")

    # _rule_2b_decision: fail-open (untagged) vs fail-closed (tagged) on a br query error, and the
    # basic open-children deny/allow shape -- via monkeypatched helpers so every branch is
    # exercised without needing a live `br` sandbox per case. `from gate_common import name` binds
    # `name` directly into THIS module's globals, so the patch target is this module's globals(),
    # not gate_common's attributes (rebinding those wouldn't affect the already-bound names here).
    g = globals()
    real_find, real_children = g["br_find_by_external_ref"], g["br_open_children"]
    try:
        rule2b_cases = [
            ("br query fails, untagged -> fail OPEN (allow)",
             "git flow feature finish demo", lambda *_: (None, False), None, False),
            ("br query fails, tagged -> fail CLOSED (deny)",
             "APOGEE_RUN_PLAN=1 git flow feature finish demo", lambda *_: (None, False), None, True),
            ("epic found, open children -> deny (tagged or not)",
             "git flow feature finish demo",
             lambda root, ref: ({"id": "proj-1", "external_ref": ref}, True),
             lambda root, eid: (["proj-1.2"], True), True),
            ("epic found, no open children -> allow",
             "git flow feature finish demo",
             lambda root, ref: ({"id": "proj-1", "external_ref": ref}, True),
             lambda root, eid: ([], True), False),
            ("no epic linked to this branch -> allow",
             "git flow feature finish demo", lambda *_: (None, True), None, False),
        ]
        test_prefixes = {"feature": "feature/", "bugfix": "bugfix/", "release": "release/",
                          "hotfix": "hotfix/", "support": "support/"}
        for label, cmd, find_fn, children_fn, want_deny in rule2b_cases:
            g["br_find_by_external_ref"] = find_fn
            g["br_open_children"] = children_fn or (lambda *_: (None, False))
            reason = _rule_2b_decision(strip_payloads(cmd), "/tmp", test_prefixes)
            got_deny = reason is not None
            mark = "✓" if got_deny == want_deny else "✗ FAIL"
            if got_deny != want_deny:
                ok = False
            print(f"  {mark}  {label}: denied={got_deny} (want {want_deny})")
    finally:
        g["br_find_by_external_ref"], g["br_open_children"] = real_find, real_children

    print("\n" + ("All tests passed." if ok else "SOME TESTS FAILED."))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_self_test()
    else:
        main()
