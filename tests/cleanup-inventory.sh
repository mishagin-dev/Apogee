#!/usr/bin/env bash
# Verdicts of skills/cleanup/scripts/inventory.sh on a sandbox superproject with a submodule
# and one worktree of each kind. Runs under /bin/bash to cover bash 3.2 on macOS.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
inv="$repo_root/plugins/apogee/skills/cleanup/scripts/inventory.sh"
sb=$(mktemp -d)
trap 'rm -rf "$sb"' EXIT
sb=$(cd "$sb" && pwd -P)

export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=protocol.file.allow GIT_CONFIG_VALUE_0=always
fail=0
check() {  # check <verdict> <path suffix> [<note fragment>]
  local line
  line=$(grep -F "	$sb/$2	" <<<"$out" || true)
  if [[ "$line" != "$1	"* || "$line" != *"${3:-}"* ]]; then
    echo "FAIL: $2: expected $1 ${3:+($3)}, got: ${line:-nothing}"; fail=1
  fi
}

cd "$sb"
git init -q -b develop sub && git -C sub commit -q --allow-empty -m s0
git init -q -b develop super && cd super
git commit -q --allow-empty -m p0
git submodule add -q ../sub core && git commit -q -m "add core"

# No linked worktrees at all: must not abort on empty arrays.
out=$(/bin/bash "$inv" --no-size "$sb/super") || { echo "FAIL: aborts with no worktrees"; fail=1; }

git worktree add -q --detach ../wt/clean
git -C ../wt/clean submodule update -q --init
git worktree add -q -b feature/dirty ../wt/dirty && echo x > ../wt/dirty/new.txt
git worktree add -q --detach ../wt/subahead
git -C ../wt/subahead submodule update -q --init
git -C ../wt/subahead/core commit -q --allow-empty -m lost
git -C core worktree add -q --detach ../../core-wt-ahead
git -C ../core-wt-ahead commit -q --allow-empty -m ahead
git worktree add -q --detach ../wt/gone && rm -rf ../wt/gone
git worktree add -q --detach ../wt/locked-gone && git worktree lock ../wt/locked-gone
mv ../wt/locked-gone ../wt/moved-away
printf '[package]\nname="c"\n' > core/Cargo.toml && mkdir core/target
mkdir -p notes/target

# Back-date every index so only the activity case below counts as recent.
find "$sb" -name index -path '*.git*' -exec touch -t 202001010000 {} +
git worktree add -q --detach ../wt/active

out=$(/bin/bash "$inv" --no-size "$sb/super/core")   # started from inside a submodule
check REMOVE wt/clean "clean, merged or pushed"
check KEEP wt/dirty "1 uncommitted"
check KEEP wt/subahead "core: 1 commit(s)"
check KEEP core-wt-ahead "1 commit(s) on no base branch"
check PRUNE wt/gone
check KEEP wt/locked-gone "locked"
check KEEP wt/active "active in the last"
check BUILD super/core/target
grep -qF "$sb/super/notes/target" <<<"$out" && { echo "FAIL: notes/target reported as BUILD"; fail=1; }

[ "$fail" = 0 ] && echo "cleanup-inventory: ok"
exit "$fail"
