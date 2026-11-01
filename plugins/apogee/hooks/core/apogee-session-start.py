#!/usr/bin/env python3
"""
SessionStart hook — inject Apogee's rules, keep AI tooling out of git, auto-prime managed projects.

Three jobs:

0. **Rules injection.** Apogee's general rules (`rules/RULES.md`) and tone (`rules/SOUL.md`) live
   in the plugin, not in the project's `CLAUDE.md`, so they update with the plugin and a project's
   `CLAUDE.md` is never rewritten on update (ADR 0009). They are injected as additionalContext on
   every session start, including `resume`, `clear` and `compact`, so a compacted session keeps
   them. Gated on a `docs/apogee/` directory in cwd or an ancestor (a project set up with Apogee,
   or one of its submodules); elsewhere the plugin stays silent.

1. **Exclude maintenance.** The toolkit's decision is that a repository holds code and project
   documentation only: `CLAUDE.md`, `GEMINI.md`, `docs/apogee/`, `.claude/`, `.beads/`, `.scratch/` are
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
    "context (docs/apogee)."
)

# Only auto-prime fresh sessions, not resumed/compacted ones.
ACTIVE_SOURCES = {"startup", "clear"}

EXCLUDE_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "exclude-list.txt")
RULES_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "rules"))
RULES_FILES = ("SOUL.md", "RULES.md")
RULES_PREAMBLE = (
    "Apogee toolkit rules, delivered by the apogee plugin at session start. The project's own "
    "CLAUDE.md overrides them wherever the two disagree."
)
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


def has_apogee_docs(start: str) -> bool:
    """True if `start` or an ancestor holds `docs/apogee/` (a project set up with Apogee)."""
    dir_ = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(dir_, "docs", "apogee")):
            return True
        parent = os.path.dirname(dir_)
        if parent == dir_:
            return False
        dir_ = parent


def load_rules() -> str:
    """SOUL.md + RULES.md from the plugin, preamble first; '' if neither can be read."""
    parts = []
    for name in RULES_FILES:
        try:
            with open(os.path.join(RULES_DIR, name), encoding="utf-8") as f:
                parts.append(f.read().strip())
        except OSError:
            continue
    return (RULES_PREAMBLE + "\n\n" + "\n\n".join(parts)) if parts else ""


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

    context = []
    if has_apogee_docs(cwd):
        rules = load_rules()
        if rules:
            context.append(rules)
    if data.get("source", "") in ACTIVE_SOURCES and find_apogee_root(cwd):
        context.append(PRIME_DIRECTIVE)
    if not context:
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n".join(context),
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

    rules = load_rules()
    check("rules load (SOUL + RULES)", all(h in rules for h in ("how to be", "the rules")), True)
    check("rules carry the override preamble", rules.startswith(RULES_PREAMBLE), True)
    with tempfile.TemporaryDirectory() as tmp:
        check("no docs/apogee -> no rules", has_apogee_docs(tmp), False)
        sub = os.path.join(tmp, "app", "submodule")
        os.makedirs(os.path.join(tmp, "docs", "apogee"))
        os.makedirs(sub)
        check("docs/apogee in an ancestor -> rules", has_apogee_docs(sub), True)

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
