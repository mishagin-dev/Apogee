#!/usr/bin/env bash
# Sandbox test for skills/git-commit/scripts/check-local-names.sh, under /bin/bash (3.2 on macOS).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHECK="${REPO_ROOT}/plugins/apogee/skills/git-commit/scripts/check-local-names.sh"
SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

fails=0
expect() { # expect <ok|fail> <label> <message>
  local rc=0
  printf '%s\n' "$3" | /bin/bash "$CHECK" >/dev/null 2>&1 || rc=$?
  if { [ "$1" = ok ] && [ "$rc" -eq 0 ]; } || { [ "$1" = fail ] && [ "$rc" -ne 0 ]; }; then
    echo "ok   $2"
  else
    echo "FAIL $2 (exit $rc)"; fails=$((fails + 1))
  fi
}

cd "$SANDBOX"
git init -q -b develop .
git -c user.name=t -c user.email=t@t commit -q --allow-empty -m "chore: Init"
mkdir -p docs/apogee/research
: > docs/apogee/research/2026-11-20-gateway-migration.md
: > docs/apogee/handoff.md

expect ok   "clean message"            "fix(net): Retry the handshake once"
expect fail "CLAUDE.md"                "fix(net): Retry once, as CLAUDE.md says"
expect fail "docs/apogee path"         "fix(net): Retry once per docs/apogee/spec"
expect fail ".beads"                   "chore: Sync .beads issues"
expect fail "note stem"                "fix(net): Follow 2026-11-20-gateway-migration"
expect ok   "short note stem ignored"  "fix(net): Write the handoff code"

: > CLAUDE.md
git add CLAUDE.md
git -c user.name=t -c user.email=t@t commit -q -m "docs: Track the agent guide"
expect ok   "tracked name allowed"     "docs: Update CLAUDE.md"

git config apogee.commitLocalNames allow
expect ok   "opt-out"                  "chore: Sync .beads issues"
git config --unset apogee.commitLocalNames

git -c user.name=t -c user.email=t@t commit -q --allow-empty -m "fix: Retry" -m "See .scratch/notes"
rc=0; /bin/bash "$CHECK" --range HEAD~2..HEAD >/dev/null 2>&1 || rc=$?
if [ "$rc" -ne 0 ]; then echo "ok   range finds the commit"; else echo "FAIL range"; fails=$((fails + 1)); fi
rc=0; /bin/bash "$CHECK" --range HEAD~2..HEAD~1 >/dev/null 2>&1 || rc=$?
if [ "$rc" -eq 0 ]; then echo "ok   range clean"; else echo "FAIL range clean"; fails=$((fails + 1)); fi

[ "$fails" -eq 0 ]
