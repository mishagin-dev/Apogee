#!/usr/bin/env python3
"""
SessionStart hook — keep AI tooling out of git, and auto-prime Apogee-managed projects.

Two jobs, both silent on success:

1. **Exclude maintenance.** The toolkit's decision is that a repository holds code and project
   documentation only: `CLAUDE.md`, `GEMINI.md`, `docs/apogee/`, `.claude/`, `.beads/` are
   personal working state and live in `.git/info/exclude`, never in `.gitignore`. `setup.sh` writes
   that list once; this hook re-asserts it on every session start, for the repo root and each
   first-level submodule, so a path created later (the first plan file, the first memory entry, a
   submodule's own `CLAUDE.md`) never surfaces in `git status` and never gives the agent a reason
   to wonder whether it should be committed. Gated on `docs/apogee/` existing at the repo root (the
   scaffold marker); a repo that was never set up with Apogee is left alone. The list is
   `config/exclude-list.txt`, shared with `setup.sh`.

2. **Prime directive.** For projects the user manages with Apogee, every session should begin with
   `/apogee:prime`. A hook cannot run a slash command, so this injects an additionalContext
   directive. Trigger: `.beads/` AND `docs/apogee/` at the same repo root. Only `startup` and
   `clear` sessions — re-priming a resumed or compacted session is redundant and noisy.

Fail-open: any parse/IO error exits 0 with no output, so session start is never blocked.
"""

import json
import os
import subprocess
import sys

PRIME_DIRECTIVE = (
    "This is an Apogee-managed project (beads tracker detected). "
    "Before doing anything else, run the /apogee:prime command to load project "
    "context (docs/apogee and the beads tracker state)."
)

# Only auto-prime fresh sessions, not resumed/compacted ones.
ACTIVE_SOURCES = {"startup", "clear"}

EXCLUDE_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "exclude-list.txt")
EXCLUDE_COMMENT = "# Apogee: AI tooling is local-only by decision (see exclude-list.txt in the plugin)"


def _git(args, cwd, timeout=3):
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _exclude_patterns():
    try:
        with open(EXCLUDE_LIST, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    except OSError:
        return []


def ensure_excluded(repo, patterns):
    """Append any pattern missing from `repo`'s .git/info/exclude. Returns the count added."""
    exclude = _git(["rev-parse", "--git-path", "info/exclude"], repo)
    if not exclude:
        return 0
    if not os.path.isabs(exclude):
        exclude = os.path.join(repo, exclude)
    try:
        present = set()
        if os.path.isfile(exclude):
            with open(exclude, encoding="utf-8") as f:
                present = {ln.strip() for ln in f}
        missing = [p for p in patterns if p not in present]
        if not missing:
            return 0
        os.makedirs(os.path.dirname(exclude), exist_ok=True)
        with open(exclude, "a", encoding="utf-8") as f:
            f.write("\n" + EXCLUDE_COMMENT + "\n" + "\n".join(missing) + "\n")
        return len(missing)
    except OSError:
        return 0


def submodule_paths(root):
    out = _git(["config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"], root)
    paths = []
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            candidate = os.path.join(root, parts[1].strip())
            if os.path.isdir(candidate) and _git(["rev-parse", "--git-dir"], candidate):
                paths.append(candidate)
    return paths


def maintain_excludes(cwd):
    root = _git(["rev-parse", "--show-toplevel"], cwd)
    if not root or not os.path.isdir(os.path.join(root, "docs", "apogee")):
        return
    patterns = _exclude_patterns()
    if not patterns:
        return
    ensure_excluded(root, patterns)
    for sub in submodule_paths(root):
        ensure_excluded(sub, patterns)


def find_apogee_root(start: str) -> bool:
    """True if `start` or any ancestor is a Apogee project root."""
    dir_ = os.path.abspath(start)
    while True:
        beads = os.path.isdir(os.path.join(dir_, ".beads"))
        aictx = os.path.isdir(os.path.join(dir_, "docs", "apogee"))
        if beads and aictx:
            return True
        parent = os.path.dirname(dir_)
        if parent == dir_:
            return False
        dir_ = parent


def main() -> None:
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}

    cwd = data.get("cwd") or os.getcwd()
    if not os.path.isdir(cwd):
        return

    maintain_excludes(cwd)

    if data.get("source", "") not in ACTIVE_SOURCES:
        return
    if not find_apogee_root(cwd):
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": PRIME_DIRECTIVE,
        }
    }))


def _run_self_test() -> None:
    """Run: python3 apogee-session-start.py --test"""
    import tempfile

    ok = True

    def check(label, got, want):
        nonlocal ok
        mark = "ok  " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  {mark} {label}: {got!r} (want {want!r})")

    patterns = _exclude_patterns()
    check("exclude list loaded", bool(patterns), True)

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "-C", tmp, "init", "-q"], check=True, capture_output=True)
        exclude_path = os.path.join(tmp, ".git", "info", "exclude")

        def exclude_text():
            try:
                with open(exclude_path, encoding="utf-8") as f:
                    return f.read()
            except OSError:
                return ""

        maintain_excludes(tmp)
        check("repo without docs/apogee is left alone", EXCLUDE_COMMENT in exclude_text(), False)
        os.makedirs(os.path.join(tmp, "docs", "apogee"))
        maintain_excludes(tmp)
        content = exclude_text()
        check("all patterns written", all(p in content.splitlines() for p in patterns), True)
        check("second run adds nothing", ensure_excluded(tmp, patterns), 0)
        for probe in ("CLAUDE.md", ".claude/plans/x.md", ".beads/issues.jsonl", "docs/apogee/ai-context/spec.md"):
            d = os.path.dirname(os.path.join(tmp, probe))
            os.makedirs(d, exist_ok=True)
            open(os.path.join(tmp, probe), "w").close()
            r = subprocess.run(["git", "-C", tmp, "check-ignore", "-q", probe], capture_output=True)
            check(f"git ignores {probe}", r.returncode, 0)
        open(os.path.join(tmp, "src.py"), "w").close()
        r = subprocess.run(["git", "-C", tmp, "check-ignore", "-q", "src.py"], capture_output=True)
        check("git still sees src.py", r.returncode, 1)

    print("\n" + ("All tests passed." if ok else "SOME TESTS FAILED."))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_self_test()
    else:
        try:
            main()
        except Exception:
            # Fail-open: never block session start.
            pass
        sys.exit(0)
