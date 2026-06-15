#!/bin/bash
# gated.sh — run a Apogee hook only inside Apogee-managed projects.
#
# Apogee hooks ship in the apogee plugin and fire in every session where the plugin
# is enabled (including throwaway ones in plain dirs). This wrapper gates the
# noisy ones (snapshot-baseline) to projects that are actually Apogee-managed,
# detected by the scaffold's invariant:
#   a .beads/ directory AND a docs/apogee/ directory, at the same repo root.
#
# Usage (from hooks.json):  bash gated.sh <absolute-path-to-real-hook.sh>
# Reads the hook JSON on stdin, finds `cwd`, and execs the real hook with that
# same stdin only when the cwd is under a Apogee project; otherwise exits 0 (allow).

set -euo pipefail

REAL_HOOK="${1:-}"
[[ -z "$REAL_HOOK" || ! -f "$REAL_HOOK" ]] && exit 0   # nothing to run -> allow

# Capture stdin once so we can both inspect it and forward it unchanged.
INPUT_JSON="$(cat)"

# Resolve cwd from the hook payload (fall back to the process cwd).
HOOK_CWD="$(printf '%s' "$INPUT_JSON" | jq -r '.cwd // ""' 2>/dev/null || echo "")"
[[ -z "$HOOK_CWD" || ! -d "$HOOK_CWD" ]] && HOOK_CWD="$PWD"

# Walk up from cwd looking for a Apogee project root.
is_apogee_project() {
    local dir="$1"
    while [[ -n "$dir" && "$dir" != "/" ]]; do
        if [[ -d "$dir/.beads" && -d "$dir/docs/apogee" ]]; then
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    # Final check at filesystem root.
    [[ -d "/.beads" && -d "/docs/apogee" ]]
}

if is_apogee_project "$HOOK_CWD"; then
    # Forward the original stdin to the real hook; propagate its exit code/stdout.
    printf '%s' "$INPUT_JSON" | bash "$REAL_HOOK"
    exit $?
fi

exit 0
