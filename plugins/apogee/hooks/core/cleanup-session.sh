#!/bin/bash
# cleanup-session.sh — Remove per-session temp files on SessionEnd
# Belt-and-suspenders: /tmp is also cleared on reboot for orphaned files.

set -euo pipefail

HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "unknown")

[[ "$SESSION_ID" == "unknown" ]] && exit 0

# The one surviving per-session file: the unfinished-branch nudge counter that stops the reminder
# after N firings. Everything else this used to clear belonged to hooks deleted by ADR 0005 or
# retired since (the idea nudge).
rm -f "/tmp/gitflow-nudge-${SESSION_ID}.count"
exit 0
