#!/bin/bash
# cleanup-session.sh — Remove per-session temp files on SessionEnd
# Belt-and-suspenders: /tmp is also cleared on reboot for orphaned files.

set -euo pipefail

HOOK_INPUT=$(cat)
SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "unknown")

[[ "$SESSION_ID" == "unknown" ]] && exit 0

# The two surviving per-session files: the nudge counters that stop each reminder
# after N firings. Everything else this used to clear belonged to the review/br
# gates deleted by ADR 0005.
rm -f "/tmp/gitflow-nudge-${SESSION_ID}.count" \
      "/tmp/idea-nudge-${SESSION_ID}.count"
exit 0
