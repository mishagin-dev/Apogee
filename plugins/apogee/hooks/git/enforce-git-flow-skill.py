#!/usr/bin/env python3
"""
PreToolUse hook — the production-branch wall plus the two git-flow checks that survive ADR 0005.

Rules, in evaluation order:

3. DENY — anything that publishes or rewrites the production branch or a tag (ADR 0007).
   `git push` whose destination resolves to the production branch (`main`, `HEAD:main`, `:main`,
   `--delete main`, a bare `git push` while `main` is checked out), any push of tags (`--tags`,
   `refs/tags/...`, a refspec naming an existing tag), `--all`/`--mirror`, any force push; `git
   merge` while the production branch is checked out (also `git checkout main && git merge ...`
   in one command); `git tag <name>` creation. Applies in ANY git repo that has a production
   branch (`gitflow.branch.master`, else `main`/`master`), not only git-flow ones: pushing shared
   history cannot be undone, and a submodule without git-flow config is still a repo with a main.
   Everything else -- pushing `develop`, pushing or deleting work branches -- is allowed without
   a question. The wall is what makes that autonomy safe.

2b. DENY — `APOGEE_RUN_PLAN=1 git flow feature|bugfix finish` while the linked br epic still has
   open (non-closed) children. Scoped to /apogee:run-plan's autonomous loop; fail-CLOSED (a `br`
   query error refuses the finish). An interactive finish gets no check. See ADR 0006.

1. DENY — `git flow release|hotfix finish`. It merges into the production branch and tags; by
   decision (ADR 0007) that step belongs to the operator in a terminal. `/apogee:release` prepares
   the branch and prints the two commands.

Active only in git repos; fail-open on any parse/IO error. Everything else this file used to
enforce is prose in `skills/git-flow/SKILL.md` and `scaffold/CLAUDE.md` (ADR 0005).
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from gitflow_common import (  # noqa: E402
    deny,
    run as _run,
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

# `git [global opts] <subcommand> <rest>` for the subcommands the wall inspects. Global options
# (`-C dir`, `-c k=v`, `--no-pager`, ...) are skipped so `git -C sub push` is still a push; the
# subcommand must be a whole word so `git log --grep push` is not.
_GIT_SUB_RE = (
    r"(?<![\w/.-])git(?![\w-])(?:\s+(?:-C\s+\S+|-c\s+\S+|--[\w-]+(?:=\S+)?))*\s+{sub}(?=\s|$)"
    r"(?P<rest>[^|;&\n]*)"
)
_PUSH_RE = re.compile(_GIT_SUB_RE.format(sub="push"))
_MERGE_RE = re.compile(_GIT_SUB_RE.format(sub="merge"))
_TAG_RE = re.compile(_GIT_SUB_RE.format(sub="tag"))
_CHECKOUT_RE = re.compile(_GIT_SUB_RE.format(sub=r"(?:checkout|switch)"))

_PUSH_DENY_FLAGS = {"--all", "--mirror", "--tags", "--follow-tags", "-f", "--force",
                    "--force-if-includes"}
_PUSH_DRY_FLAGS = {"-n", "--dry-run"}
# Flags that take a value in the next token, so that token is not a refspec.
_PUSH_VALUE_FLAGS = {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}
_TAG_LIST_FLAGS = {"-l", "--list", "-n", "-d", "--delete", "-v", "--verify", "--contains",
                   "--no-contains", "--points-at", "--merged", "--no-merged", "--column",
                   "--no-column", "--sort", "--format", "-i", "--ignore-case"}


def _run_plan_tagged(command: str) -> bool:
    """True if `command` carries the /apogee:run-plan autonomous tag."""
    return bool(_RUN_PLAN_TAG_RE.search(command))


def production_branch(cwd: str):
    """The branch the wall protects: `gitflow.branch.master`, else an existing `main`/`master`.
    None when `cwd` is not a git repo or has no such branch (a brand-new repo has nothing to
    protect yet)."""
    configured = _run(["git", "-C", cwd, "config", "gitflow.branch.master"], cwd)
    if configured:
        return configured
    for name in ("main", "master"):
        if _run(["git", "-C", cwd, "show-ref", "--verify", f"refs/heads/{name}"], cwd):
            return name
    return None


def _current_branch(cwd: str) -> str:
    return _run(["git", "-C", cwd, "branch", "--show-current"], cwd)


def _is_tag(cwd: str, name: str) -> bool:
    return bool(name) and bool(_run(["git", "-C", cwd, "tag", "--list", name], cwd))


def _refspec_targets_wall(spec: str, cwd: str, prod: str):
    """Reason string if one refspec publishes/deletes the production branch or a tag, else None."""
    spec = spec.lstrip("+")
    if spec.startswith("refs/tags/"):
        return f"pushes tag {spec}"
    src, _, dst = spec.partition(":")
    dst = dst or src
    if dst in ("HEAD", "@"):
        dst = _current_branch(cwd)
    if dst.startswith("refs/tags/"):
        return f"pushes tag {dst}"
    dst_name = dst[len("refs/heads/"):] if dst.startswith("refs/heads/") else dst
    if dst_name == prod:
        return f"targets '{prod}'" if src else f"deletes '{prod}' on the remote"
    if _is_tag(cwd, dst_name):
        return f"pushes tag {dst_name}"
    return None


def _push_decision(rest: str, cwd: str, prod: str):
    """Reason string if this `git push <rest>` must be refused, else None."""
    tokens = rest.split()
    if any(t in _PUSH_DRY_FLAGS for t in tokens):
        return None
    positional = []
    skip_next = False
    for t in tokens:
        if skip_next:
            skip_next = False
            continue
        if t.startswith("--force-with-lease"):
            return "force-pushes"
        if t in _PUSH_DENY_FLAGS:
            return f"uses {t}"
        if t in _PUSH_VALUE_FLAGS:
            skip_next = True
            continue
        if t.startswith("-"):
            continue
        positional.append(t)
    refspecs = positional[1:]  # positional[0] is the remote
    if not refspecs:
        if _current_branch(cwd) == prod:
            return f"pushes the checked-out '{prod}'"
        return None
    for spec in refspecs:
        reason = _refspec_targets_wall(spec, cwd, prod)
        if reason:
            return reason
    return None


def _wall_decision(command: str, cwd: str, prod: str):
    """Rule 3: a deny reason if `command` publishes or rewrites the production branch or a tag."""
    for m in _PUSH_RE.finditer(command):
        reason = _push_decision(m.group("rest"), cwd, prod)
        if reason:
            return (
                f"This push {reason}. Publishing '{prod}' or tags is reserved for the operator "
                f"(ADR 0007): push `develop` and work branches freely; for a release, "
                f"/apogee:release prepares the branch and prints the finish and push commands to "
                f"run in a terminal."
            )
    if _MERGE_RE.search(command):
        on_prod = _current_branch(cwd) == prod
        switches_to_prod = any(
            prod in m.group("rest").split() for m in _CHECKOUT_RE.finditer(command)
        )
        if on_prod or switches_to_prod:
            return (
                f"Merging into '{prod}' is reserved for the operator (ADR 0007). Finish work "
                f"branches into develop with `git flow feature|bugfix finish`; releases are "
                f"prepared by /apogee:release and finished by the operator in a terminal."
            )
    for m in _TAG_RE.finditer(command):
        tokens = m.group("rest").split()
        if not tokens or any(t in _TAG_LIST_FLAGS or t.startswith("--list") or t.startswith("--sort")
                             or t.startswith("--format") or t.startswith("--contains")
                             or t.startswith("--points-at") for t in tokens):
            continue
        if any(not t.startswith("-") for t in tokens):
            return (
                "Creating tags is reserved for the operator (ADR 0007): a tag is a release "
                "marker, and `git flow release finish` run by the operator creates it."
            )
    return None


def _finish_slug(rest: str, cwd: str, type_name: str, prefixes: dict):
    """The slug `git flow <type> finish` operates on.

    An explicit slug (first non-flag token after `finish`) wins. Omitted entirely -- valid AVH
    usage that finishes the CURRENTLY CHECKED OUT branch -- falls back to the current branch with
    its `<type>` prefix stripped. None only if neither resolves (e.g. detached HEAD, no slug).
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

    # ── Rule 3: the production-branch wall, in any repo that has a production branch ──
    prod = production_branch(cwd)
    if prod:
        reason = _wall_decision(command, cwd, prod)
        if reason:
            deny(reason)
            sys.exit(0)

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

    # ── Rule 1: DENY release/hotfix finish (merges into the production branch, creates a tag) ──
    if _FLOW_FINISH_RE.search(command):
        deny(
            "Finishing a release or hotfix merges into the production branch and creates a tag; "
            "by decision (ADR 0007) the operator runs that in a terminal. /apogee:release prepares "
            "the branch (version, CHANGELOG, validate gate, commits) and prints the finish and push "
            "commands; stop there."
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

    def git(repo, *args):
        # Signing is forced off: a global `tag.gpgsign`/`commit.gpgsign` would otherwise make the
        # sandbox tag prompt for a key (or fail with "no tag message").
        subprocess.run(["git", "-C", repo, "-c", "user.email=t@t.com", "-c", "user.name=t",
                        "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                       check=True, capture_output=True)

    # Rule 1's regex, post-strip_payloads.
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
        git(tmp, "init", "-q", "-b", "feature/on-branch")
        git(tmp, "commit", "-q", "--allow-empty", "-m", "x")
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

    # Rule 3: the production-branch wall, against a real repo with main, develop, a work branch
    # and a tag. Decisions are computed without running any push.
    print("\n_wall_decision (Rule 3) tests:")
    with tempfile.TemporaryDirectory() as tmp:
        git(tmp, "init", "-q", "-b", "main")
        git(tmp, "commit", "-q", "--allow-empty", "-m", "init")
        git(tmp, "tag", "1.0.0")
        git(tmp, "branch", "develop")
        git(tmp, "branch", "feature/x")
        git(tmp, "checkout", "-q", "develop")
        check("prod detected without gitflow config", production_branch(tmp), "main")
        git(tmp, "config", "gitflow.branch.master", "main")
        check("prod from gitflow config", production_branch(tmp), "main")
        prod = "main"
        wall = lambda cmd: _wall_decision(strip_payloads(cmd), tmp, prod) is not None  # noqa: E731
        for label, cmd, want in [
            ("push develop",                     "git push origin develop",                 False),
            ("push -u work branch",              "git push -u origin feature/x",            False),
            ("push develop:develop",             "git push origin develop:develop",         False),
            ("bare push on develop",             "git push",                                False),
            ("push HEAD on develop",             "git push origin HEAD",                    False),
            ("delete remote work branch",        "git push origin --delete feature/x",      False),
            ("dry run to main is harmless",      "git push --dry-run origin main",          False),
            ("push main",                        "git push origin main",                    True),
            ("push HEAD:main",                   "git push origin HEAD:main",               True),
            ("push work branch onto main",       "git push origin feature/x:main",          True),
            ("push refs/heads/main",             "git push origin refs/heads/main",         True),
            ("delete remote main (:main)",       "git push origin :main",                   True),
            ("delete remote main (--delete)",    "git push origin --delete main",           True),
            ("push --tags",                      "git push origin --tags",                  True),
            ("push --follow-tags",               "git push --follow-tags origin develop",   True),
            ("push an existing tag by name",     "git push origin 1.0.0",                   True),
            ("push refs/tags/",                  "git push origin refs/tags/1.0.0",         True),
            ("push --all",                       "git push --all origin",                   True),
            ("push --mirror",                    "git push --mirror origin",                True),
            ("force push work branch",           "git push --force origin feature/x",       True),
            ("force-with-lease",                 "git push --force-with-lease origin dev",  True),
            ("push with -C to this repo",        f"git -C {tmp} push origin main",          True),
            ("push option value not a refspec",  "git push -o ci.skip origin develop",      False),
            ("tagged autonomous push develop",   "APOGEE_RUN_PLAN=1 git push origin develop", False),
            ("merge on develop",                 "git merge feature/x",                     False),
            ("checkout main && merge",           "git checkout main && git merge develop",  True),
            ("switch main; merge",               "git switch main; git merge develop",      True),
            ("tag creation",                     "git tag 1.2.0",                           True),
            ("annotated tag creation",           "git tag -a 1.2.0 -m x",                   True),
            ("tag list",                         "git tag -l",                              False),
            ("bare tag (lists)",                 "git tag",                                 False),
            ("tag delete (local)",               "git tag -d 1.0.0",                        False),
            ("log --grep push is not a push",    "git log --grep push",                     False),
            ("push inside quoted prompt",        "agy -p 'then git push origin main'",      False),
            ("unrelated git",                    "git status",                              False),
        ]:
            check(label, wall(cmd), want)
        git(tmp, "checkout", "-q", "main")
        check("bare push while on main", wall("git push"), True)
        check("push -u origin HEAD while on main", wall("git push -u origin HEAD"), True)
        check("merge while on main", wall("git merge develop"), True)
        git(tmp, "checkout", "-q", "develop")
        # A repo with no production branch at all has nothing to protect.
        with tempfile.TemporaryDirectory() as fresh:
            git(fresh, "init", "-q", "-b", "trunk")
            check("no main/master -> no wall", production_branch(fresh), None)

    print("\n" + ("All tests passed." if ok else "SOME TESTS FAILED."))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_self_test()
    else:
        main()
