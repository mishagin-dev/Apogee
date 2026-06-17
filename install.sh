#!/usr/bin/env bash
#
# install.sh — one-line online installer for the Apogee toolkit.
#
#   curl -fsSL https://raw.githubusercontent.com/mishagin-dev/Apogee/main/install.sh | bash
#
# It clones (or updates) the Apogee repo into a stable home, then hands off to
# setup.sh against the directory you ran it from:
#   CLONE   — git clone the toolkit into ${APOGEE_HOME:-~/.apogee}. This clone is
#             the local marketplace source; re-running the installer pulls latest.
#   SET UP  — exec setup.sh <your-current-dir> [extra args]: scaffold the project
#             content + enable the apogee plugin (globally by default).
#
# Pass setup.sh flags/target through the pipe with `bash -s --`:
#   curl -fsSL …/install.sh | bash -s -- --per-project
#   curl -fsSL …/install.sh | bash -s -- /path/to/project --no-scaffold
#
# Env overrides: APOGEE_HOME (clone dir), APOGEE_BRANCH (default: main).
#
set -euo pipefail

REPO="mishagin-dev/Apogee"
BRANCH="${APOGEE_BRANCH:-main}"
APOGEE_HOME="${APOGEE_HOME:-$HOME/.apogee}"
INVOKED_PWD="$PWD"

# ---- prereqs ----
command -v git >/dev/null 2>&1 || { echo "git is required." >&2; exit 1; }
command -v jq  >/dev/null 2>&1 || { echo "jq is required (setup.sh uses it)." >&2; exit 1; }

echo "Apogee online installer"
echo "  repo:         $REPO@$BRANCH"
echo "  toolkit home: $APOGEE_HOME"
echo "  project:      $INVOKED_PWD"
echo

# ---- CLONE or UPDATE the toolkit (the local marketplace source) ----
if [[ -d "$APOGEE_HOME/.git" ]]; then
  echo "→ Updating existing toolkit clone…"
  git -C "$APOGEE_HOME" fetch --depth 1 origin "$BRANCH"
  git -C "$APOGEE_HOME" reset --hard -q FETCH_HEAD
else
  echo "→ Cloning the toolkit…"
  git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$APOGEE_HOME"
fi
echo

# ---- hand off to setup.sh against the invoking directory ----
# Explicit target first so a bare run sets up $PWD (not the clone); any
# user-supplied args (flags or an alternate target) still take effect after it.
exec "$APOGEE_HOME/setup.sh" "$INVOKED_PWD" "$@"
