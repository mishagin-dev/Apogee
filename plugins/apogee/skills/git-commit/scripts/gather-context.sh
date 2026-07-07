#!/usr/bin/env bash
# Collect everything needed to write a commit message:
#   - the diff to summarize (staged; falls back to ALL changes if nothing staged)
#   - recent history (to match the repo's existing style)
#   - short status (to see the set of touched files at a glance)
#
# Usage:  bash scripts/gather-context.sh
# Output is plain text meant to be read by the agent, not parsed.
set -euo pipefail

# Must be inside a git work tree.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not inside a git work tree. cd into the repo first." >&2
  exit 1
fi

echo "===== SCOPE ====="
if ! git diff --cached --quiet; then
  scope="staged"
  echo "Using STAGED changes (git diff --cached)."
elif ! git diff --quiet; then
  scope="all"
  echo "NOTICE: nothing staged. Falling back to ALL changes (git diff)."
else
  echo "No staged or modified tracked changes detected."
  untracked=$(git ls-files --others --exclude-standard)
  if [ -n "$untracked" ]; then
    echo "NOTICE: only untracked files exist (git diff ignores these)."
    echo "Stage them to commit:"
    echo "$untracked" | sed 's/^/  git add /'
  else
    echo "Stage something with 'git add' or make an edit, then re-run."
  fi
  exit 2
fi

echo
echo "===== STATUS (git status --short) ====="
git status --short

echo
echo "===== RECENT HISTORY (git log --oneline -10) ====="
git log --oneline -10 2>/dev/null || echo "(no commits yet)"

echo
echo "===== DIFFSTAT ====="
if [ "$scope" = "staged" ]; then
  git diff --cached --stat
else
  git diff --stat
fi

echo
echo "===== FULL DIFF ====="
if [ "$scope" = "staged" ]; then
  git diff --cached
else
  git diff
fi
