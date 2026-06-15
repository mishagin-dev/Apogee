#!/usr/bin/env bash
#
# sync.sh — refresh an installed project from the Apogee toolkit.
#
# There are two independent update channels — they are NOT the same thing:
#
#   MACHINERY (hooks + commands + workflow skills) lives in the `apogee` plugin.
#   It is never copied into projects, so it has nothing to sync file-by-file.
#   To ship a machinery change: bump plugins/apogee/.claude-plugin/plugin.json
#   "version", then in each Claude session refresh the local marketplace:
#       /plugin marketplace update apogee
#       /reload-plugins
#   Every project with `apogee@apogee` enabled then picks up the new version.
#
#   CONTENT (CLAUDE.md, docs/apogee/*) was COPIED at setup and is owned by
#   the project. This script re-runs the scaffold copy (non-clobbering: existing
#   files are left untouched, only missing template files are added) so a project
#   can pull in NEW scaffold files without losing its customizations.
#
# Usage: ./sync.sh [TARGET_DIR]   (default: current dir)
#
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Re-run setup: scaffold copy is non-clobbering and the plugin-enable is idempotent.
exec "$REPO_DIR/setup.sh" "${1:-$PWD}"
