#!/usr/bin/env bash
#
# setup.sh — install the Apogee toolkit into a project.
#
# Three clearly separated halves:
#   COPY     — project CONTENT is scaffolded (copied) into the target: CLAUDE.md, GEMINI.md,
#              docs/apogee/*, doc scaffolding dirs, assets/. Lives in the target's working tree
#              (the agent reads/writes it normally — an IDE with "respect gitignore" off still
#              shows it) but stays OUT of the host project's git history via .git/info/exclude:
#              it's personal AI-tooling context, not a project deliverable. Back it up yourself
#              (e.g. to a NAS) if you want it to survive a fresh clone.
#   ENABLE   — the MACHINERY (hooks + commands + workflow skills) is NOT copied. It
#              lives once in the `apogee` plugin (this repo is its local marketplace) and
#              is merely enabled for the project via `enabledPlugins`. Update once
#              (bump the plugin, `/plugin marketplace update apogee`) → every enabled
#              project gets it.
#   SETTINGS — a personal, git-excluded TARGET/.claude/settings.local.json carrying a
#              baseline permission allow-list (so the plugin's skills + the MCP servers it
#              leans on — idea, Context7 — run without prompts), a content-agnostic deny-list
#              (sudo, rm -rf, destructive git), plansDirectory, and an absolute
#              autoMemoryDirectory. Non-clobbering merge.
#
# Usage:
#   ./setup.sh [TARGET_DIR] [--per-project] [--no-scaffold] [--no-settings] [--init-tracker]
#     TARGET_DIR      project to set up (default: current dir)
#     --per-project   enable the plugin in TARGET/.claude/settings.json only
#                     (default: enable globally in ~/.claude/settings.json)
#     --no-scaffold   skip copying CLAUDE.md/GEMINI.md/docs/apogee (only enable the plugin)
#     --no-settings   skip writing TARGET/.claude/settings.local.json
#     --init-tracker  offer to run `br init` and `git flow init` so the gates engage
#
set -euo pipefail

# Append `pattern` to `dir`'s .git/info/exclude (local-only, uncommitted -- never touches the
# host's tracked .gitignore, so enabling Apogee leaves zero git footprint). Idempotent; no-op if
# `dir` isn't a git repo yet.
git_exclude() {
  local dir="$1" pattern="$2" comment="$3" exclude
  git -C "$dir" rev-parse --git-dir >/dev/null 2>&1 || { echo "  • $dir is not a git repo — skipped .git/info/exclude ($pattern)."; return 0; }
  exclude="$(cd "$dir" && git rev-parse --git-path info/exclude)"
  [[ "$exclude" = /* ]] || exclude="$dir/$exclude"
  mkdir -p "$(dirname "$exclude")"
  if [[ ! -f "$exclude" ]] || ! grep -qxF "$pattern" "$exclude" 2>/dev/null; then
    printf '\n# %s\n%s\n' "$comment" "$pattern" >> "$exclude"
    echo "  • $pattern added to .git/info/exclude ($dir)."
  else
    echo "  • $pattern already excluded ($dir)."
  fi
}

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

  # docs/apogee/ is Apogee's working memory, and CLAUDE.md/GEMINI.md are personal AI-tooling
  # context (not a project deliverable) -- keep all three out of the host project's git. See the
  # COPY note in the file header for why .git/info/exclude, not .gitignore.
  git_exclude "$TARGET" "docs/apogee/" "Apogee toolkit working memory (local-only)"
  git_exclude "$TARGET" "CLAUDE.md" "Apogee AI-tooling context (local-only)"
  git_exclude "$TARGET" "GEMINI.md" "Apogee AI-tooling context (local-only)"
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
if ! jq --arg key "${PLUGIN_NAME}@${MARKETPLACE_NAME}" \
   '.enabledPlugins = ((.enabledPlugins // {}) + {($key): true})' \
   "$SETTINGS" > "$tmp"; then
  rm -f "$tmp"; echo "  ! enabledPlugins merge failed (is $SETTINGS valid JSON?)" >&2; exit 1
fi
mv "$tmp" "$SETTINGS"
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
# Baseline permission allow-list so the plugin's skills (and the MCP servers it nudges the
# agent toward — idea, plugin-bundled Context7 — both stable-token, harmless when absent)
# run without prompts in acceptEdits/default sessions, a
# content-agnostic deny-list (sudo / rm -rf / destructive git — defense-in-depth that
# complements the hook gates), plus project-local plansDirectory and an absolute
# autoMemoryDirectory. Non-clobbering: existing keys win, the allow/deny lists are
# unioned, the dirs are set only if absent.
if [[ $DO_SETTINGS -eq 1 ]]; then
  echo "→ Writing personal settings.local.json (allow + deny, plans, memory)…"
  LOCAL="$TARGET/.claude/settings.local.json"
  mkdir -p "$(dirname "$LOCAL")"
  [[ -f "$LOCAL" ]] || echo '{}' > "$LOCAL"

  tmp="$(mktemp)"
  if ! jq --argjson baseline '["Bash(br:*)","Bash(agy:*)","Bash(git diff:*)","Bash(deno run:*)","Bash(rembg:*)","Bash(python3:*)","Bash(source:*)","mcp__idea__*","mcp__plugin_context7_context7__*"]' \
     --argjson denylist '["Bash(sudo:*)","Bash(rm -rf:*)","Bash(rm -fr:*)","Bash(rm -r -f:*)","Bash(rm -f -r:*)","Bash(git push --force:*)","Bash(git push -f:*)","Bash(git reset --hard:*)","Bash(git clean -f:*)","Bash(git checkout -- .:*)","Bash(git restore .:*)","Bash(git branch -D:*)"]' \
     --arg plans "./.claude/plans" \
     --arg mem   "$TARGET/.claude/memory" \
     '.permissions.allow = ((.permissions.allow // []) + $baseline | unique)
      | .permissions.deny  = ((.permissions.deny  // []) + $denylist | unique)
      | .plansDirectory //= $plans
      | .autoMemoryDirectory //= $mem' \
     "$LOCAL" > "$tmp"; then
    rm -f "$tmp"; echo "  ! settings merge failed (is $LOCAL valid JSON?)" >&2; exit 1
  fi
  mv "$tmp" "$LOCAL"
  echo "  • settings.local.json merged ($LOCAL)"

  # keep the personal file out of the host project's git (mirror docs/apogee/)
  git_exclude "$TARGET" ".claude/settings.local.json" "Apogee personal settings (local-only)"
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
