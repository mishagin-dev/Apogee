#!/bin/bash
# track-file-touch.sh — Log files this session edits (PostToolUse on
# Edit|Write|MultiEdit|NotebookEdit). review-docs-gate.sh scopes its diff to
# this per-session manifest so another session's — or pre-existing — dirty
# state in the same working tree never counts toward this session's total.
# Ported from upstream CCDK's track-file-touch.sh. Fast, non-blocking, always
# exits 0.

set -euo pipefail

HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "unknown")
FILE_PATH=$(echo "$HOOK_INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // ""' 2>/dev/null || echo "")

# Nothing to record (missing jq, no path, or no session) — exit cleanly
[[ -z "$FILE_PATH" || "$SESSION_ID" == "unknown" ]] && exit 0

# Append to per-session manifest. Single-line writes are atomic; review-docs-gate.sh
# deduplicates with sort -u, so duplicate appends are harmless.
echo "$FILE_PATH" >> "/tmp/claude-touched-${SESSION_ID}.files" 2>/dev/null || true
exit 0
