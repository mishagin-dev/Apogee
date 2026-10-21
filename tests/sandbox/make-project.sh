#!/usr/bin/env bash
#
# make-project.sh — build a throwaway Apogee-managed project for live runs of the skills.
#
# Creates, under a fresh temp dir (or the directory given as $1):
#   remote.git/   a bare repository acting as origin
#   project/      git (main + develop, both pushed), git-flow pinned to main, br initialised,
#                 a tiny Python module with unittest tests, and the Apogee scaffold
#                 (CLAUDE.md with a Testing section, docs/apogee/, excludes, settings.local.json)
#
# The marketplace-installed apogee plugin is disabled in the project's .claude/settings.json, so a
# session started with `claude --plugin-dir <repo>/plugins/apogee` runs the working tree's plugin
# and nothing else. setup.sh runs with the claude CLI hidden from PATH, so building the sandbox
# never touches the user's plugin registry.
#
# Usage: bash tests/sandbox/make-project.sh [dir]   → prints the project path on the last line
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="${1:-$(mktemp -d)}"
mkdir -p "$ROOT"
PROJECT="$ROOT/project"
REMOTE="$ROOT/remote.git"

for bin in git git-flow br jq python3; do
    command -v "$bin" >/dev/null 2>&1 || { echo "missing: $bin" >&2; exit 1; }
done

git init -q --bare -b main "$REMOTE"
mkdir -p "$PROJECT"
cd "$PROJECT"
git init -q -b main
git config user.email sandbox@example.com
git config user.name "Apogee Sandbox"
git config commit.gpgsign false
git config tag.gpgsign false
git remote add origin "$REMOTE"

mkdir -p calc tests
cat > calc/__init__.py <<'PY'
"""A tiny arithmetic module used to exercise Apogee's work loop."""


def add(a: float, b: float) -> float:
    """Return the sum of a and b."""
    return a + b
PY
cat > tests/__init__.py <<'PY'
PY
cat > tests/test_add.py <<'PY'
import unittest

from calc import add


class AddTest(unittest.TestCase):
    def test_adds(self) -> None:
        self.assertEqual(add(2, 3), 5)


if __name__ == "__main__":
    unittest.main()
PY
printf '__pycache__/\n' > .gitignore
git add .gitignore calc tests
git commit -q -m "chore: Initial calc module"
git push -q -u origin main

# Scaffold with the claude CLI hidden (no plugin registry changes); tracker init does git-flow
# with main + develop.
SAFE_PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v "$HOME/.local/bin" | paste -sd: -)"
env PATH="$SAFE_PATH" bash "$REPO/setup.sh" "$PROJECT" --per-project >/dev/null
# `br` lives in ~/.local/bin too, which SAFE_PATH hides; initialise it with the full PATH.
[[ -d .beads ]] || br init --actor sandbox -q
git push -q -u origin develop

# Only the working tree's plugin should run here: disable the marketplace copy for this project.
jq '.enabledPlugins["apogee@apogee"] = false' .claude/settings.json > .claude/settings.json.tmp
mv .claude/settings.json.tmp .claude/settings.json

# Project facts the skills rely on: what this is, and how to run the tests.
python3 - "$PROJECT/CLAUDE.md" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
t = t.replace("# [Project Name]", "# calc (Apogee sandbox)", 1)
t = t.replace("## 1. Project\n", "## 1. Project\n\nA tiny Python arithmetic module, `calc`, used only to exercise Apogee's work loop.\n", 1)
t = t.replace("## 5. Testing\n", "## 5. Testing\n\n- Targeted (your own change): `python3 -m unittest tests.test_<name>`\n- Full suite (release gate): `python3 -m unittest discover -s tests`\n", 1)
p.write_text(t, encoding="utf-8")
PY

echo "sandbox: $ROOT"
echo "$PROJECT"
