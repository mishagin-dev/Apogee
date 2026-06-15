#!/bin/bash
# br-prime.sh — inject the beads_rust (`br`) agent guide on SessionStart / PreCompact.
#
# beads_rust replaced beads-Go: the binary is `br` (NEVER `bd`), and it has no `prime`
# command. The closest equivalent is `br robot-docs guide` — a concise, agent-oriented
# workflow guide (session-start commands, claim/close/sync protocol). Injecting it keeps the
# agent using br (not markdown TODOs), especially after context compaction.
#
# Run with `--no-db` so the guide is emitted statically (no SQLite/JSONL dependency, no stale-DB
# warnings, works regardless of the workspace DB state).
#
# Gated to beads projects: fires where a `.beads/` directory exists (walking up from the hook
# cwd) — br still uses `.beads/`. Silent no-op in a casual chat (no `.beads/`).
# NOTE: br never runs git; sync/commit of `.beads/` stays the user's job (git-flow/git-commit).

set -euo pipefail

INPUT_JSON="$(cat)"
HOOK_CWD="$(printf '%s' "$INPUT_JSON" | jq -r '.cwd // ""' 2>/dev/null || echo "")"
[[ -z "$HOOK_CWD" || ! -d "$HOOK_CWD" ]] && HOOK_CWD="$PWD"

# Walk up from cwd to a beads project root (a .beads/ directory).
dir="$HOOK_CWD"
root=""
while [[ -n "$dir" && "$dir" != "/" ]]; do
    if [[ -d "$dir/.beads" ]]; then root="$dir"; break; fi
    dir="$(dirname "$dir")"
done
[[ -z "$root" && -d "/.beads" ]] && root="/"

[[ -z "$root" ]] && exit 0                 # not a beads project -> no-op
command -v br >/dev/null 2>&1 || exit 0    # br CLI unavailable -> no-op

cd "$root" 2>/dev/null || exit 0
br robot-docs guide --no-db "$@" 2>/dev/null || true
exit 0
