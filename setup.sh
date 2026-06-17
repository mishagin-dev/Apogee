#!/usr/bin/env bash
#
# setup.sh — install the Apogee toolkit into a project.
#
# Three clearly separated halves:
#   COPY     — project CONTENT is scaffolded (copied) into the target: CLAUDE.md,
#              docs/apogee/*, doc scaffolding dirs, assets/. Owned by the project.
#   ENABLE   — the MACHINERY (hooks + commands + workflow skills) is NOT copied. It
#              lives once in the `apogee` plugin (this repo is its local marketplace) and
#              is merely enabled for the project via `enabledPlugins`. Update once
#              (bump the plugin, `/plugin marketplace update apogee`) → every enabled
#              project gets it.
#   SETTINGS — a personal, git-excluded TARGET/.claude/settings.local.json carrying a
#              baseline permission allow-list (so the plugin's skills run without prompts),
#              plansDirectory, and an absolute autoMemoryDirectory. Non-clobbering merge.
#
# Usage:
#   ./setup.sh [TARGET_DIR] [--per-project] [--no-scaffold] [--no-settings] [--init-tracker]
#     TARGET_DIR      project to set up (default: current dir)
#     --per-project   enable the plugin in TARGET/.claude/settings.json only
#                     (default: enable globally in ~/.claude/settings.json)
#     --no-scaffold   skip copying docs/CLAUDE.md (only enable the plugin)
#     --no-settings   skip writing TARGET/.claude/settings.local.json
#     --init-tracker  offer to run `br init` and `git flow init` so the gates engage
#
set -euo pipefail

MARKETPLACE_NAME="apogee"
PLUGIN_NAME="apogee"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD_DIR="$REPO_DIR/scaffold"

# ---- args ----
TARGET="$PWD"
PER_PROJECT=0
DO_SCAFFOLD=1
DO_SETTINGS=1
INIT_TRACKER=0
for arg in "$@"; do
  case "$arg" in
    --per-project) PER_PROJECT=1 ;;
    --no-scaffold) DO_SCAFFOLD=0 ;;
    --no-settings) DO_SETTINGS=0 ;;
    --init-tracker) INIT_TRACKER=1 ;;
    -*) echo "Unknown flag: $arg" >&2; exit 2 ;;
    *)  TARGET="$(cd "$arg" 2>/dev/null && pwd || true)"
        [[ -z "$TARGET" ]] && { echo "Target dir not found: $arg" >&2; exit 2; } ;;
  esac
done

# ---- prereqs ----
command -v jq >/dev/null 2>&1 || { echo "jq is required." >&2; exit 1; }
[[ -d "$TARGET" ]] || { echo "Target is not a directory: $TARGET" >&2; exit 1; }
[[ "$TARGET" == "$REPO_DIR" ]] && { echo "Refusing to set up Apogee into itself." >&2; exit 1; }

echo "Apogee setup"
echo "  repo (marketplace): $REPO_DIR"
echo "  target project:     $TARGET"
echo "  enable scope:       $([[ $PER_PROJECT -eq 1 ]] && echo 'per-project' || echo 'global (~/.claude)')"
echo

# ---- COPY: scaffold project content ----
if [[ $DO_SCAFFOLD -eq 1 ]]; then
  echo "→ Scaffolding project content (copy)…"
  # CLAUDE.md + GEMINI.md (agy reads GEMINI.md as its convention file) — never clobber existing ones.
  for conv in CLAUDE.md GEMINI.md; do
    if [[ -f "$TARGET/$conv" ]]; then
      echo "  • $conv exists — left untouched."
    else
      cp "$SCAFFOLD_DIR/$conv" "$TARGET/$conv"
      echo "  • $conv created."
    fi
  done
  # docs/apogee/ai-context/* — preserve existing files, add missing ones.
  mkdir -p "$TARGET/docs/apogee/ai-context"
  for f in "$SCAFFOLD_DIR"/docs/apogee/ai-context/*.md; do
    base="$(basename "$f")"
    if [[ -f "$TARGET/docs/apogee/ai-context/$base" ]]; then
      echo "  • docs/apogee/ai-context/$base exists — skipped."
    else
      cp "$f" "$TARGET/docs/apogee/ai-context/$base"
      echo "  • docs/apogee/ai-context/$base created."
    fi
  done
  # empty scaffolding dirs (all under docs/apogee/ — the single Apogee dir) + assets
  for d in business design-brand legal open-issues; do
    mkdir -p "$TARGET/docs/apogee/$d"; [[ -e "$TARGET/docs/apogee/$d/.gitkeep" ]] || touch "$TARGET/docs/apogee/$d/.gitkeep"
  done
  mkdir -p "$TARGET/assets"; [[ -e "$TARGET/assets/.gitkeep" ]] || touch "$TARGET/assets/.gitkeep"
  echo "  • doc/asset scaffolding ensured."

  # docs/apogee/ is Apogee's working memory — keep it out of the host project's git.
  # Use .git/info/exclude (local, uncommitted) rather than .gitignore so the host's
  # tracked ignore file stays untouched — zero git footprint in the project.
  if git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
    EXCLUDE="$(cd "$TARGET" && git rev-parse --git-path info/exclude)"
    [[ "$EXCLUDE" = /* ]] || EXCLUDE="$TARGET/$EXCLUDE"
    mkdir -p "$(dirname "$EXCLUDE")"
    if [[ ! -f "$EXCLUDE" ]] || ! grep -qxF "docs/apogee/" "$EXCLUDE" 2>/dev/null; then
      printf '\n# Apogee toolkit working memory (local-only)\ndocs/apogee/\n' >> "$EXCLUDE"
      echo "  • docs/apogee/ added to .git/info/exclude."
    else
      echo "  • docs/apogee/ already excluded."
    fi
  else
    echo "  • $TARGET is not a git repo — skipped .git/info/exclude (docs/apogee/ untracked anyway)."
  fi
  echo
fi

# ---- ENABLE: register marketplace + enable the plugin (link, not copy) ----
echo "→ Enabling the apogee plugin (link)…"

# Best-effort: use the claude CLI if it exposes plugin management.
CLI_OK=0
if command -v claude >/dev/null 2>&1 && claude plugin --help >/dev/null 2>&1; then
  claude plugin marketplace add "$REPO_DIR" 2>/dev/null || true
  claude plugin install "${PLUGIN_NAME}@${MARKETPLACE_NAME}" 2>/dev/null && CLI_OK=1 || true
fi

# Reliable fallback / source of truth: write enabledPlugins into the chosen settings
# file. The plugin files are referenced from the marketplace cache, never copied here.
if [[ $PER_PROJECT -eq 1 ]]; then
  SETTINGS="$TARGET/.claude/settings.json"
else
  SETTINGS="$HOME/.claude/settings.json"
fi
mkdir -p "$(dirname "$SETTINGS")"
[[ -f "$SETTINGS" ]] || echo '{}' > "$SETTINGS"

tmp="$(mktemp)"
jq --arg key "${PLUGIN_NAME}@${MARKETPLACE_NAME}" \
   '.enabledPlugins = ((.enabledPlugins // {}) + {($key): true})' \
   "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"
echo "  • enabledPlugins[\"${PLUGIN_NAME}@${MARKETPLACE_NAME}\"] = true  ($SETTINGS)"

if [[ $CLI_OK -eq 0 ]]; then
  cat <<EOF

  NOTE: register the marketplace once in an interactive Claude session if not already:
        /plugin marketplace add $REPO_DIR
        /plugin install ${PLUGIN_NAME}@${MARKETPLACE_NAME}
        /reload-plugins
  After updating the plugin in this repo, refresh installed projects with:
        /plugin marketplace update $MARKETPLACE_NAME
EOF
fi
echo

# ---- SETTINGS: personal per-project settings.local.json (gitignored) ----
# Baseline permission allow-list so the plugin's skills run without prompts, plus
# project-local plansDirectory and an absolute autoMemoryDirectory. Non-clobbering:
# existing keys win, the allow-list is unioned, the dirs are set only if absent.
if [[ $DO_SETTINGS -eq 1 ]]; then
  echo "→ Writing personal settings.local.json (permissions, plans, memory)…"
  LOCAL="$TARGET/.claude/settings.local.json"
  mkdir -p "$(dirname "$LOCAL")"
  [[ -f "$LOCAL" ]] || echo '{}' > "$LOCAL"

  tmp="$(mktemp)"
  jq --argjson baseline '["Bash(br:*)","Bash(agy:*)","Bash(git diff:*)","Bash(deno run:*)","Bash(rembg:*)","Bash(python3:*)","Bash(source:*)"]' \
     --arg plans "./.claude/plans" \
     --arg mem   "$TARGET/.claude/memory" \
     '.permissions.allow = ((.permissions.allow // []) + $baseline | unique)
      | .plansDirectory //= $plans
      | .autoMemoryDirectory //= $mem' \
     "$LOCAL" > "$tmp" && mv "$tmp" "$LOCAL"
  echo "  • settings.local.json merged ($LOCAL)"

  # keep the personal file out of the host project's git (mirror docs/apogee/)
  if git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
    EXCLUDE="$(cd "$TARGET" && git rev-parse --git-path info/exclude)"
    [[ "$EXCLUDE" = /* ]] || EXCLUDE="$TARGET/$EXCLUDE"
    mkdir -p "$(dirname "$EXCLUDE")"
    if [[ ! -f "$EXCLUDE" ]] || ! grep -qxF ".claude/settings.local.json" "$EXCLUDE" 2>/dev/null; then
      printf '\n# Apogee personal settings (local-only)\n.claude/settings.local.json\n' >> "$EXCLUDE"
      echo "  • .claude/settings.local.json added to .git/info/exclude."
    else
      echo "  • .claude/settings.local.json already excluded."
    fi
  else
    echo "  • $TARGET is not a git repo — skipped .git/info/exclude."
  fi
  echo
fi

# ---- optional: init the work tracker so the gates engage ----
if [[ $INIT_TRACKER -eq 1 ]]; then
  echo "→ Tracker init (the gates self-gate to .beads/ + gitflow projects)…"
  ( cd "$TARGET" && command -v br >/dev/null 2>&1 && [[ ! -d .beads ]] && br init && echo "  • br init done." ) || true
  ( cd "$TARGET" && command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1 \
      && ! git config --get-regexp '^gitflow\.branch\.' >/dev/null 2>&1 \
      && echo "  • run 'git flow init' manually to enable the git-flow gate." ) || true
  echo
fi

echo "Done. Restart Claude (or /reload-plugins) in $TARGET for the plugin to take effect."
