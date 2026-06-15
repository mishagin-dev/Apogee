#!/bin/bash
# review-docs-gate.sh — Stop gate (G4): enforce the end-of-task review->docs pipeline.
#
# When the working tree has meaningful code changes (net >= review_threshold vs the git baseline),
# block the stop until BOTH skills have run THIS session, in order:
#   1) /review-work  (marker /tmp/claude-review-<sid>.done, set by skill-run-tracker.py)
#   2) /update-docs  (marker /tmp/claude-docs-<sid>.done)
# Once both markers exist -> allow. Hard enforcement WITH execution verification (markers), unlike
# the upstream advisory review-on-stop.sh that this replaces in the Stop wiring.
#
# Never traps: escape env REVIEW_GATE_OFF=1, and a per-phase backstop — after OVERRIDE repeats of the
# same missing-marker block (agent genuinely can't run the skill) it allows. Gated to beads projects.
# Part of the apogee plugin.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OVERRIDE=3

[[ "${REVIEW_GATE_OFF:-}" == "1" ]] && exit 0

INPUT="$(cat)"
SID="$(printf '%s' "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo unknown)"
CWD="$(printf '%s' "$INPUT" | jq -r '.cwd // ""' 2>/dev/null || echo "")"
[[ -z "$CWD" || ! -d "$CWD" ]] && CWD="$PWD"

# Gate to a beads project root.
dir="$CWD"; root=""
while [[ -n "$dir" && "$dir" != "/" ]]; do
    [[ -d "$dir/.beads" ]] && { root="$dir"; break; }
    dir="$(dirname "$dir")"
done
[[ -z "$root" ]] && exit 0

CONFIG="$SCRIPT_DIR/../core/config/pipeline.json"
[[ -f "$CONFIG" ]] && [[ "$(jq -r '.enabled // true' "$CONFIG" 2>/dev/null || echo true)" != "true" ]] && exit 0

THRESH=50
[[ -f "$CONFIG" ]] && THRESH="$(jq -r '.review_threshold // 50' "$CONFIG" 2>/dev/null || echo 50)"
REVIEW_CMD="/review-work"; DOCS_CMD="/update-docs"
if [[ -f "$CONFIG" ]]; then
    REVIEW_CMD="$(jq -r '.review_command // "/review-work"' "$CONFIG" 2>/dev/null || echo /review-work)"
    DOCS_CMD="$(jq -r '.docs_command // "/update-docs"' "$CONFIG" 2>/dev/null || echo /update-docs)"
fi

cd "$root" 2>/dev/null || exit 0
PATS=()
if [[ -f "$CONFIG" ]]; then
    while IFS= read -r p; do [[ -n "$p" ]] && PATS+=("$p"); done < <(jq -r '(.file_patterns // [])|.[]' "$CONFIG" 2>/dev/null)
fi
[[ ${#PATS[@]} -eq 0 ]] && PATS=("*.py" "*.ts" "*.tsx" "*.js" "*.swift" "*.go" "*.rs" "*.kt" "*.kts" "*.c" "*.cpp" "*.h" "*.java")

CUR_LINES=$(git diff --numstat HEAD -- "${PATS[@]}" 2>/dev/null | awk -F'\t' '$1!="-"{s+=$1+$2} END{print s+0}')
BASE_NUM="/tmp/claude-baseline-${SID}.numstat"
BASE_LINES=0
[[ -f "$BASE_NUM" ]] && BASE_LINES=$(awk -F'\t' '$1!="-"{s+=$1+$2} END{print s+0}' "$BASE_NUM" 2>/dev/null || echo 0)
NET=$(( CUR_LINES - BASE_LINES ))
(( NET < 0 )) && NET=0

STATE="/tmp/claude-revdocs-${SID}.state"
REVIEW_DONE="/tmp/claude-review-${SID}.done"
DOCS_DONE="/tmp/claude-docs-${SID}.done"

# Under threshold -> nothing to enforce.
if (( NET < THRESH )); then
    rm -f "$STATE"
    exit 0
fi

# Determine the next required phase.
PHASE=""; CMD=""
if [[ ! -f "$REVIEW_DONE" ]]; then
    PHASE="review"; CMD="$REVIEW_CMD"
elif [[ ! -f "$DOCS_DONE" ]]; then
    PHASE="docs"; CMD="$DOCS_CMD"
fi

# Both markers present -> allow.
if [[ -z "$PHASE" ]]; then
    rm -f "$STATE"
    exit 0
fi

# Per-phase repeat counter (anti-trap backstop).
CNT=0
if [[ -f "$STATE" ]]; then
    SC="$(cat "$STATE" 2>/dev/null || echo "")"
    [[ "${SC%%:*}" == "$PHASE" ]] && CNT="${SC#*:}"
fi
CNT=$(( CNT + 1 ))
if (( CNT >= OVERRIDE )); then
    rm -f "$STATE"
    exit 0   # backstop: don't trap the session if the skill can't be run
fi
echo "${PHASE}:${CNT}" > "$STATE"

if [[ "$PHASE" == "review" ]]; then
    REASON="End-of-task gate: this session changed ~${NET} lines of code. Run ${CMD} now to review the work, then stop again. (Required before finishing. Override: REVIEW_GATE_OFF=1, or stop $((OVERRIDE - CNT)) more time(s).)"
else
    REASON="Review done. Now run ${CMD} to update documentation for the ~${NET} changed lines, then stop again. (Required before finishing. Override: REVIEW_GATE_OFF=1, or stop $((OVERRIDE - CNT)) more time(s).)"
fi
jq -n --arg r "$REASON" '{"decision":"block","reason":$r}'
exit 0
