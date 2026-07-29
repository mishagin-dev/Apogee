#!/usr/bin/env python3
"""
PreToolUse hook — the two git-flow safety checks that survive ADR 0005.

Active only when the current repo has gitflow config (`git config gitflow.branch.*`).
In all other repos the hook is completely inert — fail-open.

Rules enforced:

1. ASK — git flow release|hotfix finish
   Merges into the production branch and creates a tag. Locally this is a three-branch reflog
   unwind; once pushed it is rewritten shared history. It is an ASK, not a DENY: it surfaces a
   decision the user has to make anyway, at the one moment the tree changes awkwardly.

2b. DENY — `APOGEE_RUN_PLAN=1 git flow feature|bugfix finish` while the linked br epic still has
   open (non-closed) children.
   Scoped deliberately to /apogee:run-plan's autonomous loop. An interactive finish gets NO check
   at all — a human is present, and the failure (tracker drift) is one `br update` to fix. An
   unattended loop has no such backstop: a model drifting over a long run will eventually believe
   an epic is complete, close it, merge, and proceed, compounding across epics. That is the one
   place in this toolkit where a hard circuit breaker still earns its keep, so here the check is
   fail-CLOSED: if `br` cannot be queried, the finish is refused rather than allowed.

Everything else this file used to enforce — commits off gitflow branches, manual merges, manual
branch creation, one-branch-at-a-time — is now prose in `skills/git-flow/SKILL.md` and
`scaffold/CLAUDE.md`. See ADR 0005 for the evidence behind that change.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from gitflow_common import (  # noqa: E402
    ask,
    deny,
    strip_payloads,
    br_find_by_external_ref,
    br_open_children,
    is_gitflow_repo as _is_gitflow_repo,
    get_prefixes as _get_prefixes,
    effective_repo as _effective_repo,
)


# Matches standalone `git flow release|hotfix finish ...` (Rule 1).
_FLOW_FINISH_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])\s+flow\s+(release|hotfix)\s+finish\b"
)

# Matches standalone `git flow feature|bugfix finish <rest>` (Rule 2b); group 1 = the type,
# named group "rest" = everything after `finish` (flags like -k/--no-ff may precede the slug).
_FLOW_FEATURE_BUGFIX_FINISH_RE = re.compile(
    r"(?<![\w/.-])git(?![\w-])\s+flow\s+(feature|bugfix)\s+finish\b(?P<rest>[^|;&\n]*)"
)

# Literal command-string tag /apogee:run-plan prefixes onto the `git flow ... finish` invocations
# its autonomous loop issues. Stateless by design: no marker file, no env var, nothing to leak
# across a crash. Matched at any command boundary (start, or after &&/;/||/&) so a `cd sub && TAG
# git flow ...` wrapping is still recognized.
_RUN_PLAN_TAG_RE = re.compile(r"(?:^|&&|\|\||;|&)\s*APOGEE_RUN_PLAN=1(?:\s|$)")


def _run_plan_tagged(command: str) -> bool:
    """True if `command` carries the /apogee:run-plan autonomous tag."""
    return bool(_RUN_PLAN_TAG_RE.search(command))


def _finish_slug(rest: str, cwd: str, type_name: str, prefixes: dict):
    """The slug `git flow <type> finish` operates on.

    An explicit slug (first non-flag token after `finish`) wins. Omitted entirely -- valid AVH
    usage that finishes the CURRENTLY CHECKED OUT branch -- falls back to the current branch with
    its `<type>` prefix stripped. None only if neither resolves (e.g. detached HEAD, no slug).
    """
    for tok in rest.split():
        if not tok.startswith("-"):
            return tok
    from gitflow_common import run as _run
    branch = _run(["git", "-C", cwd, "branch", "--show-current"], cwd)
    prefix = prefixes.get(type_name, f"{type_name}/")
    if branch and branch.startswith(prefix):
        return branch[len(prefix):]
    return None


def _rule_2b_decision(command: str, cwd: str, prefixes: dict):
    """Decide Rule 2b. Returns a deny reason (str) to block, or None to allow.

    Only tagged (autonomous) commands are checked at all. Factored out of main() so the
    fail-closed behaviour can be unit-tested by monkeypatching the br helpers, without needing a
    live `br` sandbox for every branch of the logic.
    """
    if not _run_plan_tagged(command):
        return None  # interactive finish: no check, a human is watching
    m = _FLOW_FEATURE_BUGFIX_FINISH_RE.search(command)
    if not m:
        return None
    type_name = m.group(1)
    slug = _finish_slug(m.group("rest"), cwd, type_name, prefixes)
    if not slug:
        return None
    branch = f"{prefixes.get(type_name, type_name + '/')}{slug}"
    epic, query_ok = br_find_by_external_ref(cwd, branch)
    if not query_ok:
        return (
            f"Could not verify via br whether the epic linked to '{branch}' has open steps "
            f"(br query failed) -- refusing to finish autonomously without that guarantee. "
            f"Retry, or finish manually (without the APOGEE_RUN_PLAN=1 prefix) to proceed anyway."
        )
    if not epic:
        return None  # no epic linked to this branch -- nothing to check
    open_children, query_ok2 = br_open_children(cwd, epic.get("id", ""))
    if not query_ok2:
        return (
            f"Could not verify via br whether epic {epic.get('id')} (linked to '{branch}') has "
            f"open steps (br query failed) -- refusing to finish autonomously without that "
            f"guarantee."
        )
    if open_children:
        return (
            f"Epic {epic.get('id')} (linked to '{branch}') still has open steps: "
            f"{', '.join(open_children)}. Close them in br before finishing this branch."
        )
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        cwd = payload.get("cwd") or os.getcwd()
    except Exception:
        sys.exit(0)  # fail open

    # Drop quoted/heredoc payloads so git-op regexes don't false-match inside another command's
    # arguments (e.g. `agy -p '...git flow release finish...'` is not a release finish).
    command = strip_payloads(command)

    if "git" not in command:
        sys.exit(0)

    # Judge the repo the git command actually TARGETS, not the session cwd: `git -C sub ...` or
    # `cd sub && git ...` operates on a submodule with its own branch/HEAD and its own gitflow
    # config.
    cwd = _effective_repo(command, cwd)

    if not _is_gitflow_repo(cwd):
        sys.exit(0)

    # ── Rule 2b: DENY an autonomous finish while the linked epic has open children ──
    # Checked before Rule 1 because both do `.search()` on the whole string and exit on their own
    # match; a compound command must not let one rule shadow the other's half.
    if _FLOW_FEATURE_BUGFIX_FINISH_RE.search(command):
        reason = _rule_2b_decision(command, cwd, _get_prefixes(cwd))
        if reason:
            deny(reason)
            sys.exit(0)
        # Allowed -- fall through; don't assume this is the only git-flow op in the command.

    # ── Rule 1: ASK before release/hotfix finish (touches production branch) ──
    if _FLOW_FINISH_RE.search(command):
        ask(
            "This command merges into the production branch and creates a release tag. "
            "It must only run on explicit user request — please confirm."
        )

    sys.exit(0)


def _run_self_test() -> None:
    """Run: python3 enforce-git-flow-skill.py --test"""
    import subprocess
    import tempfile

    ok = True

    def check(label, got, want):
        nonlocal ok
        mark = "✓" if got == want else "✗ FAIL"
        if got != want:
            ok = False
        print(f"  {mark}  {label}: {got!r} (want {want!r})")

    # Rule 1's regex, post-strip_payloads. This is the rule with the widest blast radius and it had
    # no direct coverage before ADR 0005 trimmed this file.
    print("_FLOW_FINISH_RE (Rule 1) tests:")
    finish_cases = [
        ("release finish",                  "git flow release finish 1.2.3",                     True),
        ("hotfix finish",                   "git flow hotfix finish urgent",                     True),
        ("compound, finish second",         "git add . && git flow release finish 1.2.3",        True),
        ("feature finish is NOT rule 1",    "git flow feature finish demo",                      False),
        ("bugfix finish is NOT rule 1",     "git flow bugfix finish demo",                       False),
        ("tagged feature finish, not r1",   "APOGEE_RUN_PLAN=1 git flow feature finish demo",    False),
        ("release start is not finish",     "git flow release start 1.2.3",                      False),
        ("inside a quoted agy prompt",      "agy -p 'then run git flow release finish'",         False),
        ("inside a heredoc body",           "agy -p 'x' <<'EOF'\ngit flow hotfix finish\nEOF",   False),
        ("a path that merely contains it",  "cat docs/git-flow-release-finish.md",               False),
    ]
    for label, cmd, want in finish_cases:
        check(label, bool(_FLOW_FINISH_RE.search(strip_payloads(cmd))), want)

    # The autonomous tag.
    print("\n_run_plan_tagged tests:")
    for label, cmd, want in [
        ("bare prefix",              "APOGEE_RUN_PLAN=1 git flow feature finish demo",            True),
        ("untagged",                 "git flow feature finish demo",                              False),
        ("after && (cd-wrapped)",    "cd sub && APOGEE_RUN_PLAN=1 git flow feature finish demo",  True),
        ("mid-token, must not match", "git flow feature finish APOGEE_RUN_PLAN=1demo",            False),
        ("substring of another word", "echo NOTAPOGEE_RUN_PLAN=1 && git flow feature finish x",   False),
    ]:
        check(label, _run_plan_tagged(cmd), want)

    # Slug resolution, including the current-branch fallback for a slug-less finish.
    print("\n_finish_slug tests:")
    prefixes = {"feature": "feature/", "bugfix": "bugfix/"}
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "-C", tmp, "init", "-q", "-b", "feature/on-branch"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", tmp, "-c", "user.email=t@t.com", "-c", "user.name=t",
                        "commit", "-q", "--allow-empty", "-m", "x"], check=True, capture_output=True)
        for label, rest, type_, want in [
            ("explicit slug",                    "demo",          "feature", "demo"),
            ("flag then slug",                   " -k demo",      "feature", "demo"),
            ("slug then flag",                   " demo --no-ff", "feature", "demo"),
            ("no slug -> current branch",        "",              "feature", "on-branch"),
            ("no slug, wrong type -> None",      "",              "bugfix",  None),
        ]:
            check(label, _finish_slug(rest, tmp, type_, prefixes), want)

    # Rule 2b: tagged-only, and fail-CLOSED on a br error. Monkeypatched so every branch is
    # exercised without a live br sandbox. `from X import name` binds into THIS module's globals,
    # so that is the patch target -- rebinding gitflow_common's attributes would not take effect.
    print("\n_rule_2b_decision tests:")
    g = globals()
    real_find, real_children = g["br_find_by_external_ref"], g["br_open_children"]
    try:
        cases = [
            ("untagged finish -> no check at all, even with open children",
             "git flow feature finish demo",
             lambda root, ref: ({"id": "p-1", "external_ref": ref}, True),
             lambda root, eid: (["p-1.2"], True), False),
            ("tagged, br query fails -> fail CLOSED (deny)",
             "APOGEE_RUN_PLAN=1 git flow feature finish demo",
             lambda *_: (None, False), None, True),
            ("tagged, open children -> deny",
             "APOGEE_RUN_PLAN=1 git flow feature finish demo",
             lambda root, ref: ({"id": "p-1", "external_ref": ref}, True),
             lambda root, eid: (["p-1.2"], True), True),
            ("tagged, all children closed -> allow",
             "APOGEE_RUN_PLAN=1 git flow feature finish demo",
             lambda root, ref: ({"id": "p-1", "external_ref": ref}, True),
             lambda root, eid: ([], True), False),
            ("tagged, no epic linked -> allow",
             "APOGEE_RUN_PLAN=1 git flow feature finish demo",
             lambda *_: (None, True), None, False),
            ("tagged, children query fails -> fail CLOSED (deny)",
             "APOGEE_RUN_PLAN=1 git flow feature finish demo",
             lambda root, ref: ({"id": "p-1", "external_ref": ref}, True),
             lambda root, eid: (None, False), True),
        ]
        test_prefixes = {"feature": "feature/", "bugfix": "bugfix/"}
        for label, cmd, find_fn, children_fn, want_deny in cases:
            g["br_find_by_external_ref"] = find_fn
            g["br_open_children"] = children_fn or (lambda *_: (None, False))
            reason = _rule_2b_decision(strip_payloads(cmd), "/tmp", test_prefixes)
            check(label, reason is not None, want_deny)
    finally:
        g["br_find_by_external_ref"], g["br_open_children"] = real_find, real_children

    # effective_repo must retarget submodule git ops so the gitflow config checked is the right
    # repo's. The newline case is a regression guard from 1.16.1.
    print("\neffective_repo tests:")
    with tempfile.TemporaryDirectory() as tmp:
        sub = os.path.normpath(os.path.join(tmp, "sub"))
        os.makedirs(sub)
        for label, cmd, want in [
            ("git -C sub",              "git -C sub flow release finish",     sub),
            ("cd sub && ...",           "cd sub && git flow release finish",  sub),
            ("cd sub; ...",             "cd sub; git flow release finish",    sub),
            ("cd sub on its own line",  "cd sub\ngit flow release finish",    sub),
            ("plain -> cwd",            "git flow release finish",            tmp),
            ("nonexistent -C -> cwd",   "git -C nope flow release finish",    tmp),
        ]:
            check(label, _effective_repo(cmd, tmp), want)

    print("\n" + ("All tests passed." if ok else "SOME TESTS FAILED."))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_self_test()
    else:
        main()
