#!/usr/bin/env bash
# Refuse commit messages that name the local-only AI tooling (RULES.md "AI tooling is
# local-only"): CLAUDE.md, docs/apogee, .claude/, .beads and the like, and the notes kept in
# docs/apogee. Such a name in a pushed message can only be removed by rewriting history.
#
# Usage:
#   printf '%s' "$msg" | bash check-local-names.sh      # one message, from stdin
#   bash check-local-names.sh --range <base>..HEAD      # every commit message in a range
#
# Prints "OK" (exit 0), or one "FAIL: ..." line per hit (exit 1).
#
# A name the repository tracks is part of the project and may be named. A repository whose
# subject is the tooling itself opts out with `git config apogee.commitLocalNames allow`.
#
# No -e: grep's "no match" exit is the normal case here. Runs on bash 3.2.
set -uo pipefail
export GIT_OPTIONAL_LOCKS=0

if [ "$(git config --get apogee.commitLocalNames 2>/dev/null)" = "allow" ]; then
  echo "OK"
  exit 0
fi

range=""
if [ "${1:-}" = "--range" ]; then
  range="${2:?--range needs <base>..<head>}"
fi

# docs/apogee lives at the top superproject, so a submodule's commits are checked against it too.
root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "OK"; exit 0; }
while sup=$(git -C "$root" rev-parse --show-superproject-working-tree 2>/dev/null) && [ -n "$sup" ]; do
  root=$sup
done
# In a linked worktree of the superproject (a zone), docs/apogee is in the main checkout.
if [ ! -d "$root/docs/apogee" ]; then
  common=$(git -C "$root" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) &&
    root=$(dirname "$common")
fi

# The local-only names, from the list setup.sh and the session-start hook keep excluded.
EXCLUDE_LIST="$(dirname "${BASH_SOURCE[0]}")/../../../hooks/core/config/exclude-list.txt"
names=$(sed -e '/^#/d' -e '/^[[:space:]]*$/d' -e 's#^/##' -e 's#/$##' "$EXCLUDE_LIST")

tracked=$(git ls-files 2>/dev/null)
patterns=""
for t in $names; do
  grep -qiF -- "$t" <<< "$tracked" && continue   # a here-string: grep -q in a pipe trips pipefail
  patterns="$patterns$t"$'\n'
done
# Note names: the dated ones (YYYY-MM-DD-<slug>); undated names like project-structure are
# ordinary words too.
if [ -d "$root/docs/apogee" ]; then
  while IFS= read -r f; do
    stem=$(basename "$f" .md)
    if printf '%s' "$stem" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}-.'; then
      patterns="$patterns$stem"$'\n'
    fi
  done < <(find "$root/docs/apogee" -maxdepth 3 -type f -name '*.md' 2>/dev/null)
fi
patterns=$(printf '%s' "$patterns" | sed '/^$/d' | sort -u)
[ -z "$patterns" ] && { echo "OK"; exit 0; }

hits=0
# check <label>: reads one message on stdin, prints a FAIL line per offending line.
check() {
  local out
  out=$(grep -niF -f <(printf '%s\n' "$patterns") 2>/dev/null) || return 0
  while IFS= read -r line; do
    echo "FAIL: ${1}line ${line%%:*} names local-only tooling: ${line#*:}"
    hits=$((hits + 1))
  done <<< "$out"
}

if [ -n "$range" ]; then
  commits=$(git rev-list "$range") || { echo "FAIL: cannot read range $range"; exit 1; }
  for c in $commits; do
    check "$(git log -1 --format='%h "%s"' "$c"), " < <(git log -1 --format=%B "$c")
  done
else
  check "" < <(cat)
fi

if [ "$hits" -eq 0 ]; then
  echo "OK"
  exit 0
fi
echo "Rewrite the message without them: the repository holds code and project docs only."
exit 1
