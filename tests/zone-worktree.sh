#!/usr/bin/env bash
# Sandbox test for skills/start/scripts/zone-worktree.sh: a superproject with submodules a, b,
# x/c1 and x/c2, a zone opened on a and x, b read-only; the guard against a bare
# `git submodule update`; a concurrent pin on develop; close; the main checkout left clean.
# Needs git-flow (AVH). Runs under /bin/bash (3.2 on macOS).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZONE="${REPO_ROOT}/plugins/apogee/skills/start/scripts/zone-worktree.sh"
SANDBOX="$(cd "$(mktemp -d)" && pwd -P)"
trap 'rm -rf "$SANDBOX"' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=protocol.file.allow GIT_CONFIG_VALUE_0=always
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }

cd "$SANDBOX"
flow_init() { git -C "$1" flow init -d >/dev/null 2>&1; }
for r in a b c1 c2; do
  git init -q -b main "src-$r"
  git -C "src-$r" commit -q --allow-empty -m "init $r"
  flow_init "src-$r"
done
git init -q -b main super
git -C super commit -q --allow-empty -m init
flow_init super
(cd super
 git submodule add -q -b develop ../src-a a
 git submodule add -q -b develop ../src-b b
 git submodule add -q -b develop ../src-c1 x/c1
 git submodule add -q -b develop ../src-c2 x/c2
 git commit -q -m "add submodules")
for p in a b x/c1 x/c2; do
  git -C "super/$p" branch -q main origin/main   # a submodule clone has only develop locally
  flow_init "super/$p"
done
ROOT="$SANDBOX/super"
WT="$ROOT/worktrees/zone-test"

out=$(cd "$ROOT" && /bin/bash "$ZONE" open feature/zone-test a x --read b)
check "open prints the worktree" '[ "$out" = "$WT" ]'
check "superproject branch" '[ "$(git -C "$WT" branch --show-current)" = feature/zone-test ]'
check "a on the branch" '[ "$(git -C "$WT/a" branch --show-current)" = feature/zone-test ]'
check "x/c2 on the branch" '[ "$(git -C "$WT/x/c2" branch --show-current)" = feature/zone-test ]'
check "b detached at its pin" '[ "$(git -C "$WT/b" rev-parse HEAD)" = "$(git -C "$WT" rev-parse HEAD:b)" ] && [ -z "$(git -C "$WT/b" branch --show-current)" ]'
check "main checkout untouched" '[ "$(git -C "$ROOT" branch --show-current)" = develop ] && [ "$(git -C "$ROOT/a" branch --show-current)" = develop ]'

git -C "$WT" submodule update --init --recursive >/dev/null 2>&1 || true
check "bare submodule update leaves a on its branch" '[ "$(git -C "$WT/a" branch --show-current)" = feature/zone-test ]'
check "main checkout's a still works" 'git -C "$ROOT/a" status --porcelain >/dev/null 2>&1'

git -C "$WT/a" commit -q --allow-empty -m "work in a"
git -C "$WT/x/c1" commit -q --allow-empty -m "work in c1"
git -C "$ROOT/b" commit -q --allow-empty -m "another session's b"
git -C "$ROOT" checkout -q -b feature/other-pin
git -C "$ROOT" add b
git -C "$ROOT" commit -q -m "pin b"
git -C "$ROOT" flow feature finish other-pin >/dev/null 2>&1

rc=0; (cd "$WT" && /bin/bash "$ZONE" close) >/dev/null 2>&1 || rc=$?
check "close succeeds" '[ "$rc" -eq 0 ]'
check "worktree gone" '[ ! -e "$WT" ] && [ "$(git -C "$ROOT" worktree list | wc -l | tr -d " ")" = 1 ]'
check "a merged into its develop" 'git -C "$ROOT/a" log --format=%s develop | grep -qx "work in a"'
check "c2 branch without commits deleted" '! git -C "$ROOT/x/c2" rev-parse --verify -q refs/heads/feature/zone-test >/dev/null'
check "superproject branch pins a to develop" '[ "$(git -C "$ROOT" rev-parse feature/zone-test:a)" = "$(git -C "$ROOT/a" rev-parse develop)" ]'

(cd "$ROOT" && git flow feature finish zone-test >/dev/null 2>&1)
check "superproject finish leaves the main checkout clean" '[ -z "$(git -C "$ROOT" status --porcelain)" ]'
check "concurrent pin of b kept" '[ "$(git -C "$ROOT" rev-parse HEAD:b)" = "$(git -C "$ROOT/b" rev-parse develop)" ]'

[ "$fails" -eq 0 ]
