#!/usr/bin/env bash
#
# install.sh — one-line online installer for the Apogee toolkit.
#
#   curl -fsSL https://raw.githubusercontent.com/mishagin-dev/Apogee/main/install.sh | bash
#
# The plugin itself comes from the GitHub marketplace (mishagin-dev/Apogee); updates arrive through
# `/plugin marketplace update apogee`. This script only needs the repository for one thing: the
# project templates (scaffold/) and setup.sh that copies them. It clones the repo into a temporary
# directory, runs setup.sh against the directory you ran it from, and removes the clone.
#
# Pass setup.sh flags/target through the pipe with `bash -s --`:
#   curl -fsSL …/install.sh | bash -s -- --per-project
#   curl -fsSL …/install.sh | bash -s -- /path/to/project --no-scaffold
#
# Env overrides: APOGEE_BRANCH (default: main).
#
set -euo pipefail

REPO="mishagin-dev/Apogee"
BRANCH="${APOGEE_BRANCH:-main}"
INVOKED_PWD="$PWD"

command -v git >/dev/null 2>&1 || { echo "git is required." >&2; exit 1; }
command -v jq  >/dev/null 2>&1 || { echo "jq is required (setup.sh uses it)." >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "Apogee online installer"
echo "  repo:    $REPO@$BRANCH"
echo "  project: $INVOKED_PWD"
echo

git clone --quiet --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$WORK/apogee"

# Explicit target first so a bare run sets up $PWD; any user-supplied args (flags or an alternate
# target) still take effect after it.
"$WORK/apogee/setup.sh" "$INVOKED_PWD" "$@"
