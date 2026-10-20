#!/usr/bin/env bash
# smoke-run-plan.sh — Integration test for the two rules enforce-git-flow-skill.py still has:
# Rule 1 (ASK before `git flow release|hotfix finish`) and Rule 2b (the /apogee:run-plan safety
# backstop: DENY finishing a feature/bugfix branch whose linked br epic has open children, ONLY for
# APOGEE_RUN_PLAN=1-tagged commands, fail-closed). An untagged finish is not checked at all --
# ADR 0005 narrowed the rule to the unattended case, where no human is present to notice drift.
#
# Unlike enforce-git-flow-skill.py --test (which unit-tests _rule_2b_decision with monkeypatched br
# helpers), this drives the REAL hook script against a REAL `br` + `git flow` sandbox, end to end.
# Never touches the repository you are working in.
#
# Usage: bash tests/smoke-run-plan.sh
set -euo pipefail

command -v git-flow >/dev/null 2>&1 || { echo "FAIL: git-flow binary not found"; exit 1; }
command -v br >/dev/null 2>&1 || { echo "FAIL: br binary not found"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SCRIPT_DIR/../plugins/apogee/hooks/git/enforce-git-flow-skill.py"
[ -f "$HOOK" ] || { echo "FAIL: hook not found at $HOOK"; exit 1; }

ok=1

# All sandboxes are created upfront and cleaned by ONE trap -- `trap ... EXIT` REPLACES any prior
# handler rather than stacking, so registering a separate trap per sandbox (as an earlier version
# of this script did) silently leaked all but the last one on every run.
sb1="$(mktemp -d)"
sb2="$(mktemp -d)"
sb3="$(mktemp -d)"
trap 'rm -rf "$sb1" "$sb2" "$sb3"' EXIT

# hook_decision <cwd> <command> -> prints "deny" or "allow" (or "other:<raw json>" for an ask)
hook_decision() {
    local cwd="$1" cmd="$2"
    local out
    out="$(python3 -c '
import json, sys
print(json.dumps({"tool_input": {"command": sys.argv[1]}, "cwd": sys.argv[2]}))
' "$cmd" "$cwd" | python3 "$HOOK")"
    if [ -z "$out" ]; then
        echo "allow"
    elif echo "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d["hookSpecificOutput"]["permissionDecision"]=="deny" else 1)' 2>/dev/null; then
        echo "deny"
    else
        echo "other:$out"
    fi
}

check() {
    local label="$1" got="$2" want="$3"
    if [ "$got" = "$want" ]; then
        echo "  ✓  $label: $got (want $want)"
    else
        echo "  ✗ FAIL  $label: $got (want $want)"
        ok=0
    fi
}

# ── Sandbox 1: real beads + git-flow, exercises the open-children deny/allow shape, the
# unlinked-branch allow, and the compound-command regression (HIGH bug found in review: another
# rule matching first in a chained `a && b` command must not shadow Rule 2b's check on the rest of
# the string) ──
(
    cd "$sb1"
    git init -q -b main
    git config user.email smoke@example.com
    git config user.name "Smoke Test"
    git commit -q --allow-empty -m "initial commit"
    git flow init -d >/dev/null
    br init --actor smoke -q

    epic="$(br create "Demo epic" --type epic --slug demo --silent --actor smoke)"
    step="$(br create "Demo step" --type task --parent "$epic" --silent --actor smoke)"

    git flow feature start demo >/dev/null
    br update "$epic" --external-ref feature/demo --actor smoke -q
    git checkout -q main
    git flow feature start unlinked >/dev/null   # never linked to any epic
    git checkout -q main

    echo "epic=$epic step=$step" > .smoke-ids
)
epic_id="$(grep -o 'epic=[^ ]*' "$sb1/.smoke-ids" | cut -d= -f2)"
step_id="$(grep -o 'step=[^ ]*' "$sb1/.smoke-ids" | cut -d= -f2)"

got="$(hook_decision "$sb1" "APOGEE_RUN_PLAN=1 git flow feature finish demo")"
check "tagged finish, open step -> deny" "$got" "deny"

got="$(hook_decision "$sb1" "git flow feature finish demo")"
check "untagged finish, open step -> allow (interactive finish is not checked)" "$got" "allow"

got="$(hook_decision "$sb1" "APOGEE_RUN_PLAN=1 git flow feature finish unlinked")"
check "tagged finish on a branch with no epic linked at all -> allow" "$got" "allow"

# Regression: both surviving rules `.search()` the WHOLE command string and act on their own match,
# so in a chained `a && b` neither may shadow the other. Rule 2b is evaluated first and only exits
# early on a deny; Rule 1 runs afterwards. Both orderings must still reach the deny.
got="$(hook_decision "$sb1" "git flow release finish 1.0.0 && APOGEE_RUN_PLAN=1 git flow feature finish demo")"
check "compound (release finish && tagged finish-with-open-step) -> deny (regression)" "$got" "deny"

got="$(hook_decision "$sb1" "APOGEE_RUN_PLAN=1 git flow feature finish demo && git flow release finish 1.0.0")"
check "compound (tagged finish-with-open-step && release finish) -> deny (regression, reverse)" "$got" "deny"

(cd "$sb1" && br update "$step_id" --claim --actor smoke -q && br close "$step_id" --actor smoke -q)

got="$(hook_decision "$sb1" "APOGEE_RUN_PLAN=1 git flow feature finish demo")"
check "tagged finish, step closed -> allow" "$got" "allow"

got="$(hook_decision "$sb1" "APOGEE_RUN_PLAN=1 git flow feature finish")"
check "tagged, no slug, on branch feature/demo, step closed -> current-branch fallback, allow" "$got" "allow"

# ── Sandbox 2: git-flow only, NO beads workspace reachable -> br query genuinely fails ──
(
    cd "$sb2"
    git init -q -b main
    git config user.email smoke@example.com
    git config user.name "Smoke Test"
    git commit -q --allow-empty -m "initial commit"
    git flow init -d >/dev/null
    git flow feature start orphan >/dev/null
)

got="$(hook_decision "$sb2" "git flow feature finish orphan")"
check "untagged finish, no beads workspace -> allow (no check at all)" "$got" "allow"

got="$(hook_decision "$sb2" "APOGEE_RUN_PLAN=1 git flow feature finish orphan")"
check "tagged finish, br query fails (no workspace) -> fail CLOSED (deny)" "$got" "deny"

# ── Sandbox 3: Rule 1 -- the release/hotfix ASK, and what it must NOT touch. This is the gate the
# user actually meets, and it had no integration coverage before ADR 0005 trimmed the hook. ──
(
    cd "$sb3"
    git init -q -b main
    git config user.email smoke@example.com
    git config user.name "Smoke Test"
    git commit -q --allow-empty -m "initial commit"
    git flow init -d >/dev/null
    git flow feature start first >/dev/null
)

is_ask() { [ "$1" != "allow" ] && [ "$1" != "deny" ] && echo yes || echo no; }

got="$(hook_decision "$sb3" "git flow release finish 1.0.0")"
check "release finish -> ask" "$(is_ask "$got")" "yes"

got="$(hook_decision "$sb3" "git flow hotfix finish 1.0.1")"
check "hotfix finish -> ask" "$(is_ask "$got")" "yes"

got="$(hook_decision "$sb3" "git flow release start 1.0.0")"
check "release start -> allow (only finish touches production)" "$got" "allow"

got="$(hook_decision "$sb3" "git flow feature start second")"
check "feature start while another branch is open -> allow (Rule 2 removed by ADR 0005)" "$got" "allow"

got="$(hook_decision "$sb3" "git commit -m wip")"
check "commit on a non-gitflow branch -> allow (Rule 3 removed by ADR 0005)" "$got" "allow"

got="$(hook_decision "$sb3" "agy -p 'then run git flow release finish 1.0.0'")"
check "release finish inside a quoted prompt -> allow (strip_payloads)" "$got" "allow"

echo
if [ "$ok" = "1" ]; then
    echo "SMOKE OK"
    exit 0
else
    echo "SMOKE FAILED"
    exit 1
fi
