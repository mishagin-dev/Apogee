#!/usr/bin/env bash
# smoke.sh — Validate the installed `git flow` binary end-to-end.
#
# Runs the real AVH `git flow` against a THROWAWAY temp repo: init, a feature
# round-trip, and a release round-trip (merge + tag + back-merge). Never touches
# the repository you are working in. Prints "SMOKE OK" and exits 0 on success.
#
# Usage: bash plugins/apogee/skills/git-flow/smoke.sh
set -euo pipefail

command -v git-flow >/dev/null 2>&1 || { echo "FAIL: git-flow binary not found"; exit 1; }

sandbox="$(mktemp -d)"
cleanup() { rm -rf "$sandbox"; }
trap cleanup EXIT

cd "$sandbox"
git init -q -b main
git config user.email smoke@example.com
git config user.name "Smoke Test"
git commit -q --allow-empty -m "initial commit on main"

# init: -d accepts default branch/prefix conventions non-interactively.
git flow init -d >/dev/null

git rev-parse --verify -q develop >/dev/null || { echo "FAIL: develop not created by init"; exit 1; }

# feature round-trip: start branches off develop, finish merges back and deletes it.
git flow feature start demo >/dev/null
[ "$(git branch --show-current)" = "feature/demo" ] || { echo "FAIL: feature start did not switch to feature/demo"; exit 1; }
git commit -q --allow-empty -m "work on demo feature"
git flow feature finish demo >/dev/null
git rev-parse --verify -q feature/demo >/dev/null && { echo "FAIL: feature/demo still exists after finish"; exit 1; }
git merge-base --is-ancestor feature/demo develop 2>/dev/null && true  # branch gone; ancestry check below
[ "$(git branch --show-current)" = "develop" ] || { echo "FAIL: not on develop after feature finish"; exit 1; }

# release round-trip: merges to main, tags, back-merges to develop, deletes branch.
git flow release start 1.0.0 >/dev/null
[ "$(git branch --show-current)" = "release/1.0.0" ] || { echo "FAIL: release start did not switch to release/1.0.0"; exit 1; }
git commit -q --allow-empty -m "bump version to 1.0.0"
git flow release finish -m "Release 1.0.0" 1.0.0 >/dev/null
git rev-parse --verify -q release/1.0.0 >/dev/null && { echo "FAIL: release/1.0.0 still exists after finish"; exit 1; }
git rev-parse --verify -q "refs/tags/1.0.0" >/dev/null || { echo "FAIL: tag 1.0.0 not created by release finish"; exit 1; }
git merge-base --is-ancestor 1.0.0 main || { echo "FAIL: release tag not on main"; exit 1; }
git merge-base --is-ancestor main develop || { echo "FAIL: main not back-merged into develop"; exit 1; }

echo "SMOKE OK"
