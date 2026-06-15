#!/bin/bash
# br-snapshot.sh — SessionStart: capture a baseline signature of the br state for the br-progress
# gate (G3) to compare against at Stop. Once per session. Gated to beads projects; no-op otherwise.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INPUT="$(cat)"
SID="$(printf '%s' "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo unknown)"
CWD="$(printf '%s' "$INPUT" | jq -r '.cwd // ""' 2>/dev/null || echo "")"
[[ -z "$CWD" || ! -d "$CWD" ]] && CWD="$PWD"

# Walk up to a beads project root.
dir="$CWD"; root=""
while [[ -n "$dir" && "$dir" != "/" ]]; do
    [[ -d "$dir/.beads" ]] && { root="$dir"; break; }
    dir="$(dirname "$dir")"
done
[[ -z "$root" ]] && exit 0
command -v br >/dev/null 2>&1 || exit 0

SIG="/tmp/br-baseline-${SID}.sig"
[[ -f "$SIG" ]] && exit 0   # once per session

( cd "$root" && br -q list --json --no-color --all 2>/dev/null ) | python3 "$SCRIPT_DIR/br-sig.py" > "$SIG" 2>/dev/null || echo "NA" > "$SIG"
exit 0
