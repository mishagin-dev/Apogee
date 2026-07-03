#!/bin/bash
# br-progress-gate.sh — Stop gate (G3): don't let a session end with untracked code work.
#
# If, since SessionStart, the br state is UNCHANGED (no new/updated/closed issue) AND the working
# tree has meaningful code changes (net ≥ min_lines vs the git baseline), block the stop and ask to
# record progress in br. 2-phase / never-traps: the 1st stop blocks; stopping again clears the state
# and allows (override). Gated to beads projects; no-op otherwise. Fail-open on any error.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INPUT="$(cat)"
SID="$(printf '%s' "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo unknown)"
CWD="$(printf '%s' "$INPUT" | jq -r '.cwd // ""' 2>/dev/null || echo "")"
[[ -z "$CWD" || ! -d "$CWD" ]] && CWD="$PWD"

dir="$CWD"; root=""
while [[ -n "$dir" && "$dir" != "/" ]]; do
    [[ -d "$dir/.beads" ]] && { root="$dir"; break; }
    dir="$(dirname "$dir")"
done
[[ -z "$root" ]] && exit 0
command -v br >/dev/null 2>&1 || exit 0

STATE="/tmp/br-gate-${SID}.state"
ST="$(cat "$STATE" 2>/dev/null || echo "")"
# Sticky override: once you've stopped again on THIS gate, stay quiet for the rest of the session.
# (Non-sticky clear-on-2nd-stop used to ping-pong with the other Stop hook: clearing the state let
#  this gate re-arm on the next stop while the other hook was still blocking — an endless loop.)
[[ "$ST" == "overridden" ]] && exit 0

# Has br changed since the session baseline?
CUR="$(cd "$root" && br -q list --json --no-color --all 2>/dev/null | python3 "$SCRIPT_DIR/br-sig.py" 2>/dev/null || echo NA)"
BASE="$(cat "/tmp/br-baseline-${SID}.sig" 2>/dev/null || echo "")"
if [[ -n "$BASE" && "$CUR" != "$BASE" ]]; then rm -f "$STATE"; exit 0; fi   # br touched -> allow + reset

# br unchanged -> is there meaningful code change?
CONFIG="$SCRIPT_DIR/config/pipeline.json"
MIN=10
[[ -f "$CONFIG" ]] && MIN="$(jq -r '.min_lines_changed // 10' "$CONFIG" 2>/dev/null || echo 10)"

cd "$root" 2>/dev/null || exit 0
PATS=()
if [[ -f "$CONFIG" ]]; then
    while IFS= read -r p; do [[ -n "$p" ]] && PATS+=("$p"); done < <(jq -r '(.file_patterns // [])|.[]' "$CONFIG" 2>/dev/null)
fi
[[ ${#PATS[@]} -eq 0 ]] && PATS=("*.py" "*.ts" "*.tsx" "*.js" "*.swift" "*.go" "*.rs" "*.kt" "*.kts" "*.c" "*.cpp" "*.h" "*.java")

# Only TRACKED code files count (git diff --numstat + PATS). Git-ignored outputs (reports, scratch)
# never land here, so writing a deliverable to an ignored folder demands no br progress. See
# gate_common.path_exempt.
CUR_LINES=$(git diff --numstat HEAD -- "${PATS[@]}" 2>/dev/null | awk -F'\t' '$1!="-"{s+=$1+$2} END{print s+0}')
BASE_NUM="/tmp/claude-baseline-${SID}.numstat"
BASE_LINES=0
[[ -f "$BASE_NUM" ]] && BASE_LINES=$(awk -F'\t' '$1!="-"{s+=$1+$2} END{print s+0}' "$BASE_NUM" 2>/dev/null || echo 0)
NET=$(( CUR_LINES - BASE_LINES ))
(( NET < 0 )) && NET=0

if (( NET >= MIN )); then
    if [[ "$ST" == "blocked" ]]; then
        echo "overridden" > "$STATE"   # stopped again -> sticky override, allow for the rest of the session
        exit 0
    fi
    echo "blocked" > "$STATE"
    jq -n --arg r "Code changed (~${NET} lines) but beads_rust shows no new/updated/closed step this session. Record progress in br (claim/update/close a step), or Stop again to override." \
        '{"decision":"block","reason":$r}'
    exit 0
fi
exit 0
