#!/usr/bin/env bash
# smoke-run-plan.sh — Integration test for enforce-git-flow-skill.py's Rule 2b (the /apogee:run-plan
# safety backstop: DENY finishing a feature/bugfix branch whose linked br epic has open children,
# fail-open for a plain manual finish vs fail-closed for an APOGEE_RUN_PLAN=1-tagged one).
#
# Unlike enforce-git-flow-skill.py --test (which unit-tests _rule_2b_decision with monkeypatched br
# helpers), this drives the REAL hook script against a REAL `br` + `git flow` sandbox, end to end.
# Never touches the repository you are working in.
#
# Usage: bash plugins/apogee/skills/git-flow/smoke-run-plan.sh
set -euo pipefail

command -v git-flow >/dev/null 2>&1 || { echo "FAIL: git-flow binary not found"; exit 1; }
command -v br >/dev/null 2>&1 || { echo "FAIL: br binary not found"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SCRIPT_DIR/../../hooks/git/enforce-git-flow-skill.py"
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
# unlinked-branch allow, and the compound-command regression (HIGH bug found in review: an earlier
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
check "untagged finish, open step -> deny (not gated on tag, just fail-open vs fail-closed on ERROR)" "$got" "deny"

got="$(hook_decision "$sb1" "git flow feature finish unlinked")"
check "finish on a branch with no epic linked at all -> allow" "$got" "allow"

# Regression: a compound command where an earlier-evaluated rule (Rule 2's `start`) also matches
# must not let its own unconditional exit shadow Rule 2b's check on the `finish` half of the SAME
# string. Nothing else has "another branch open" here, so Rule 2 itself would silently allow the
# `start` part -- the only thing that should stop this compound command is Rule 2b denying the
# `finish` half, since "demo"'s step is still open at this point in the script.
got="$(hook_decision "$sb1" "git flow feature start decoy && git flow feature finish demo")"
check "compound command (start && finish-with-open-step) -> deny (regression)" "$got" "deny"

got="$(hook_decision "$sb1" "APOGEE_RUN_PLAN=1 git flow feature finish demo && git flow feature start decoy2")"
check "compound command (tagged finish-with-open-step && start) -> deny (regression, reverse order)" "$got" "deny"

(cd "$sb1" && br update "$step_id" --claim --actor smoke -q && br close "$step_id" --actor smoke -q)

got="$(hook_decision "$sb1" "APOGEE_RUN_PLAN=1 git flow feature finish demo")"
check "tagged finish, step closed -> allow" "$got" "allow"

got="$(hook_decision "$sb1" "git flow feature finish demo")"
check "untagged finish, step closed -> allow" "$got" "allow"

got="$(hook_decision "$sb1" "git flow feature finish")"
check "no slug, on branch feature/demo, step closed -> current-branch fallback resolves, allow" "$got" "allow"

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
check "untagged finish, br query fails (no workspace) -> fail OPEN (allow)" "$got" "allow"

got="$(hook_decision "$sb2" "APOGEE_RUN_PLAN=1 git flow feature finish orphan")"
check "tagged finish, br query fails (no workspace) -> fail CLOSED (deny)" "$got" "deny"

# ── Rule 2 bypass: starting a new branch while another is open, tagged vs untagged ──
(
    cd "$sb3"
    git init -q -b main
    git config user.email smoke@example.com
    git config user.name "Smoke Test"
    git commit -q --allow-empty -m "initial commit"
    git flow init -d >/dev/null
    git flow feature start first >/dev/null
)

got="$(hook_decision "$sb3" "git flow feature start second")"
check "untagged start, another branch open -> ask (surfaces as non-empty, non-deny output)" \
    "$([ "$got" != "allow" ] && [ "$got" != "deny" ] && echo yes || echo no)" "yes"

got="$(hook_decision "$sb3" "APOGEE_RUN_PLAN=1 git flow feature start second")"
check "tagged start, another branch open -> bypass (allow)" "$got" "allow"

echo
if [ "$ok" = "1" ]; then
    echo "SMOKE OK"
    exit 0
else
    echo "SMOKE FAILED"
    exit 1
fi
