"""
Shared helpers for the Apogee hook gates.

Cross-group primitives reused by the br/* and git/* gates. Kept in `core/lib/` (a deliberate exception
to the "helpers in their own group dir" rule — same rationale as `idea/lib/`) because more than one
hook group depends on them. Importers anchor `sys.path` on their own `__file__`, never on CWD or
`${CLAUDE_PLUGIN_ROOT}`.
"""

import json
import os
import re
import subprocess

# Top-level dirs whose edits never count as trackable code (meta / docs / config).
EXEMPT_TOP = {".beads", "workflow", "conductor", ".claude"}

# Nested dirs (not top-level) that are always exempt regardless of git-ignore state. docs/apogee is
# Apogee's own working memory -- setup.sh adds it to .git/info/exclude on install, but that write is
# a one-time side effect a project can end up without (plugin enabled without running setup.sh, or
# /apogee:init run before it). Hardcoding it here (like .claude in EXEMPT_TOP) means the exemption
# holds regardless of whether that install step ever ran.
EXEMPT_NESTED = {os.path.join("docs", "apogee")}

# Extensions treated as source CODE by the br edit/branch gates: only these require a br step / a
# git-flow work branch. Everything else (docs, markdown, configs, images, data, no extension) is a
# non-code edit and passes freely — so service commands (update-docs, readme, doc, image-*) and
# ordinary doc/config edits never hit the br ceremony. Mirrors the default PATS in review-docs-gate.sh
# and br-progress-gate.sh — keep these sets in sync.
CODE_EXTENSIONS = frozenset({
    "py", "ts", "tsx", "js",
    "swift", "go", "rs", "kt", "kts",
    "c", "cpp", "h", "java",
})


def beads_root(start: str):
    """Walk up from `start` to the nearest ancestor containing a `.beads/` dir, or None."""
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, ".beads")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def git_root_for(fp, fallback):
    """Return the git repo root that actually CONTAINS `fp` -- not necessarily the beads
    workspace root passed in as `fallback`.

    `fp` may live inside a git submodule nested under the beads root: submodules are independent
    git repositories with their own branch/HEAD, so `git -C <fp's dir> rev-parse --show-toplevel`
    correctly resolves to the submodule's own root, while the outer/beads root would report the
    SUPER-repo's branch instead -- the wrong one for a branch-discipline check on that file. Walks
    up to the nearest existing ancestor directory first, so this also works for a not-yet-created
    file (a fresh `Write`). Falls back to `fallback` if `fp` is empty or git can't resolve a root
    (e.g. the path isn't inside any git repo).
    """
    if not fp:
        return fallback
    d = os.path.dirname(os.path.abspath(fp))
    while d and not os.path.isdir(d):
        parent = os.path.dirname(d)
        if parent == d:
            return fallback
        d = parent
    if not d:
        return fallback
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else fallback
    except Exception:
        return fallback


def git_ignored(root, rel):
    """True if `rel` (path relative to `root`) is git-ignored within `root`.

    Tracked files return False even if a matching ignore rule exists. Works on
    not-yet-created paths (matches ignore rules, not the filesystem) so a Write of a
    fresh `docs/apogee/...` file is recognized. Fail-open: any error -> not ignored."""
    try:
        r = subprocess.run(["git", "-C", root, "check-ignore", "-q", rel],
                           capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def path_exempt(root, fp):
    """Should an edit to `fp` skip the br edit gates?

    Exempt = the edit can never be trackable code under the branch/step discipline:
      - no file path (e.g. NotebookEdit without one) -> not exempt, let the gate run;
      - edits outside the beads root;
      - meta/doc/config top-level dirs (`EXEMPT_TOP`), and `docs/apogee/**` specifically
        (`EXEMPT_NESTED`) -- Apogee's own working memory, exempt unconditionally;
      - any other git-ignored working file (e.g. a project's own scratch/report dirs);
      - any `CLAUDE.md` (project / submodule instructions) -> bootstrap content, and the
        commit gate still enforces where it lands.
    """
    if not fp:
        return False
    abs_fp = os.path.abspath(fp)
    rel = os.path.relpath(abs_fp, root)
    if rel.startswith(".."):
        return True
    parts = rel.split(os.sep)
    if parts[0] in EXEMPT_TOP:
        return True
    if os.sep.join(parts[:2]) in EXEMPT_NESTED:
        return True
    if os.path.basename(abs_fp) == "CLAUDE.md":
        return True
    return git_ignored(root, rel)


def is_code_file(fp):
    """True if `fp`'s extension marks it as source code — the only edits the br gates track.

    Non-code files (docs, markdown, configs, images, data, extension-less) return False, so the br
    edit/branch gates skip them: a README tweak, a doc update, or any service-command write to a
    non-code file needs no br step and no git-flow work branch. Mirrors the Stop-gate PATS; see
    CODE_EXTENSIONS.
    """
    if not fp:
        return False
    ext = os.path.splitext(fp)[1].lstrip(".").lower()
    return ext in CODE_EXTENSIONS


def deny(reason):
    """Emit a PreToolUse deny decision."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def ask(reason):
    """Emit a PreToolUse ask decision (surfaces a confirmation prompt)."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))


def strip_payloads(cmd: str) -> str:
    """Remove quoted-string and heredoc payloads so git-op regexes only see real commands, not git
    mentions inside another command's arguments.

    Shared by the git-commit and git-flow enforcement hooks. Without this, `agy -p 'remember to
    git commit'` (or a heredoc body discussing `git merge`) would false-match the commit/merge
    rules and block an unrelated tool call — the reported symptom of `/apogee:second-opinion`
    being denied on `develop`. Real git commands keep their operative verb outside quotes
    (`git commit -m 'x'` -> `git commit -m `), so detection is preserved.
    """
    # Heredoc bodies: <<MARK ... MARK (also <<-MARK and quoted markers), across newlines.
    cmd = re.sub(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?.*?\n\1(?![\w-])", " ", cmd, flags=re.DOTALL)
    cmd = re.sub(r'"[^"]*"', " ", cmd)   # double-quoted strings
    cmd = re.sub(r"'[^']*'", " ", cmd)   # single-quoted strings
    return cmd


# ── Self-test (run directly) ──────────────────────────────────────────────────
#
# Guards the ceremony-exemption invariant: edits to git-ignored paths (reports, scratch, build
# outputs) must skip the br/git-flow gates — a deliverable written to an ignored folder needs no
# br step, no work branch, and no commit. path_exempt/git_ignored are the core of that, and were
# previously untested; this keeps a future refactor from silently breaking the behavior.

if __name__ == '__main__':
    import tempfile

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        # Mini git repo with ignore rules. git init / check-ignore need no user config or commits.
        subprocess.run(["git", "-C", tmp, "init", "-q"], check=True, capture_output=True)
        with open(os.path.join(tmp, ".gitignore"), "w") as f:
            f.write("reports/\n*.log\n")
        os.makedirs(os.path.join(tmp, "src"))
        os.makedirs(os.path.join(tmp, "reports", "sub"))

        root = tmp
        join = lambda *parts: os.path.join(root, *parts)
        # A path guaranteed to be outside the beads root (a sibling of tmp), regardless of where
        # the OS puts the temp dir.
        outside = os.path.join(os.path.dirname(root), "apogee-selftest-sibling", "x.md")

        path_cases = [
            # (label, file_path, expected_exempt)
            ("ignored report (md)",     join("reports", "research.md"),    True),
            ("ignored nested dir",      join("reports", "sub", "deep.txt"), True),
            ("ignored *.log",           join("debug.log"),                 True),
            ("non-ignored code",        join("src", "foo.py"),             False),
            ("EXEMPT_TOP .beads",       join(".beads", "issues.json"),     True),
            ("EXEMPT_TOP .claude",      join(".claude", "x.md"),           True),
            ("EXEMPT_NESTED docs/apogee (not gitignored)",
                                        join("docs", "apogee", "progress.md"), True),
            ("docs/other (not exempt)", join("docs", "other", "x.md"),     False),
            ("CLAUDE.md",               join("CLAUDE.md"),                 True),
            ("outside the root",        outside,                           True),
            ("empty path",              "",                                False),
        ]
        print("path_exempt() tests:")
        for label, fp, want in path_cases:
            got = path_exempt(root, fp)
            mark = "✓" if got == want else "✗ FAIL"
            if got != want:
                ok = False
            print(f"  {mark}  {label}: {got} (want {want})")

        print("\ngit_ignored() tests:")
        ignore_cases = [
            ("reports/x.md", True),
            ("debug.log",    True),
            ("src/foo.py",   False),
            (".beads/x",     False),
        ]
        for rel, want in ignore_cases:
            got = git_ignored(root, rel)
            mark = "✓" if got == want else "✗ FAIL"
            if got != want:
                ok = False
            print(f"  {mark}  git_ignored({rel!r}) = {got} (want {want})")

        print("\ngit_root_for() tests (simulated submodule: a nested repo with its own .git):")
        submodule = os.path.join(tmp, "vendor", "sub")
        os.makedirs(submodule)
        subprocess.run(["git", "-C", submodule, "init", "-q"], check=True, capture_output=True)
        real_root = os.path.realpath(root)
        real_submodule = os.path.realpath(submodule)
        root_cases = [
            ("file inside nested submodule", join("vendor", "sub", "inner.py"), real_submodule),
            ("file in the outer repo",        join("src", "foo.py"),            real_root),
            ("not-yet-created file",          join("vendor", "sub", "new.py"),  real_submodule),
            ("empty path falls back",         "",                                real_root),
        ]
        for label, fp, want in root_cases:
            got = os.path.realpath(git_root_for(fp, root))
            mark = "✓" if got == want else "✗ FAIL"
            if got != want:
                ok = False
            print(f"  {mark}  {label}: {got} (want {want})")

    print("\nis_code_file() tests:")
    code_cases = [
        # code -> br gates enforce
        ("src/app.py",     True),
        ("lib/foo.ts",     True),
        ("View.tsx",       True),
        ("main.go",        True),
        ("kernel.c",       True),
        ("header.h",       True),
        ("App.java",       True),
        ("svc.rs",         True),
        # non-code -> br gates skip (service commands / doc & config edits pass freely)
        ("README.md",      False),
        ("docs/spec.md",   False),
        ("CLAUDE.md",      False),
        ("config.yaml",    False),
        ("data.json",      False),
        ("logo.png",       False),
        ("Makefile",       False),
        ("",               False),
    ]
    for fp, want in code_cases:
        got = is_code_file(fp)
        mark = "✓" if got == want else "✗ FAIL"
        if got != want:
            ok = False
        print(f"  {mark}  is_code_file({fp!r}) = {got} (want {want})")

    print("\n" + ("All tests passed." if ok else "SOME TESTS FAILED."))
    raise SystemExit(0 if ok else 1)

