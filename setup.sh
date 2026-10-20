#!/usr/bin/env bash
#
# setup.sh — install the Apogee toolkit into a project.
#
# Three clearly separated halves:
#   COPY     — project CONTENT is scaffolded (copied) into the target: CLAUDE.md, GEMINI.md,
#              docs/apogee/ai-context/*. Lives in the target's working tree
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
#   ./setup.sh [TARGET_DIR] [--per-project] [--no-scaffold] [--no-settings]
#              [--no-git-init] [--no-tracker-init]
#     TARGET_DIR         project to set up (default: current dir)
#     --per-project      enable the plugin in TARGET/.claude/settings.json only
#                        (default: enable globally in ~/.claude/settings.json)
#     --no-scaffold      skip copying CLAUDE.md/GEMINI.md/docs/apogee (only enable the plugin)
#     --no-settings      skip writing TARGET/.claude/settings.local.json
#     --no-git-init      don't auto `git init` TARGET when it isn't a git repo yet
#     --no-tracker-init  don't auto `br init` / `git flow init -d` when TARGET has no .beads/ or
#                        gitflow.* config yet (git-flow only if the AVH binary is installed;
#                        otherwise a reminder is printed instead)
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
EXCLUDE_LIST="$REPO_DIR/plugins/apogee/hooks/core/config/exclude-list.txt"

# ---- args ----
TARGET="$PWD"
PER_PROJECT=0
DO_SCAFFOLD=1
DO_SETTINGS=1
DO_GIT_INIT=1
DO_TRACKER_INIT=1
for arg in "$@"; do
  case "$arg" in
    --per-project) PER_PROJECT=1 ;;
    --no-scaffold) DO_SCAFFOLD=0 ;;
    --no-settings) DO_SETTINGS=0 ;;
    --no-git-init) DO_GIT_INIT=0 ;;
    --no-tracker-init) DO_TRACKER_INIT=0 ;;
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

# ---- auto git init: a brand-new TARGET needs a repo before any .git/info/exclude write below
# (or the hooks' self-gating) can do anything. Safe and idempotent -- no-op if already a repo.
if [[ $DO_GIT_INIT -eq 1 ]] && command -v git >/dev/null 2>&1 \
   && ! git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
  ( cd "$TARGET" && git init -q )
  echo "→ git init: $TARGET was not a git repo -- initialized."
  echo
fi

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
  # docs/apogee/README.md (the index /apogee:prime reads) + ai-context/* — preserve existing
  # files, add missing ones. The working-memory directories are created empty up front (they are
  # git-excluded, so no .gitkeep is needed): a layout that exists is a layout that gets used.
  mkdir -p "$TARGET/docs/apogee/ai-context"
  for d in domain design diagrams research prompts reports; do
    mkdir -p "$TARGET/docs/apogee/$d"
  done
  echo "  • docs/apogee/{domain,design,diagrams,research,prompts,reports}/ ensured."
  if [[ -f "$TARGET/docs/apogee/README.md" ]]; then
    echo "  • docs/apogee/README.md exists — skipped."
  else
    cp "$SCAFFOLD_DIR/docs/apogee/README.md" "$TARGET/docs/apogee/README.md"
    echo "  • docs/apogee/README.md created."
  fi
  for f in "$SCAFFOLD_DIR"/docs/apogee/ai-context/*.md; do
    base="$(basename "$f")"
    if [[ -f "$TARGET/docs/apogee/ai-context/$base" ]]; then
      echo "  • docs/apogee/ai-context/$base exists — skipped."
    else
      cp "$f" "$TARGET/docs/apogee/ai-context/$base"
      echo "  • docs/apogee/ai-context/$base created."
    fi
  done
  # AI tooling is local-only by decision: the repository holds code and project documentation
  # only. The list (docs/apogee/, CLAUDE.md, GEMINI.md, .claude/, .beads/, ...) lives in the
  # plugin so the session-start hook can re-assert it later for the root and every first-level
  # submodule. See the COPY note in the file header for why .git/info/exclude, not .gitignore.
  while IFS= read -r pattern; do
    [[ -z "$pattern" || "$pattern" == \#* ]] && continue
    git_exclude "$TARGET" "$pattern" "Apogee: AI tooling is local-only by decision"
  done < "$EXCLUDE_LIST"
  echo
fi

# ---- ENABLE: register marketplace + enable the plugin (link, not copy) ----
echo "→ Enabling the apogee plugin (link)…"

# Best-effort: use the claude CLI if it exposes plugin management. `marketplace add` on an already
# registered name silently RE-POINTS that marketplace at the new source, so it only runs when the
# `apogee` marketplace is unknown or already points here -- running setup.sh from a dev checkout
# must not hijack an install that comes from ~/.apogee or GitHub.
CLI_OK=0
if command -v claude >/dev/null 2>&1 && claude plugin --help >/dev/null 2>&1; then
  KNOWN_SRC="$(jq -r --arg m "$MARKETPLACE_NAME" '.[$m].source | (.path // .repo // .url // empty)' \
    "$HOME/.claude/plugins/known_marketplaces.json" 2>/dev/null || true)"
  if [[ -z "$KNOWN_SRC" || "$KNOWN_SRC" == "$REPO_DIR" ]]; then
    claude plugin marketplace add "$REPO_DIR" 2>/dev/null || true
    claude plugin install "${PLUGIN_NAME}@${MARKETPLACE_NAME}" 2>/dev/null && CLI_OK=1 || true
  else
    echo "  • marketplace '$MARKETPLACE_NAME' is registered from $KNOWN_SRC — left as is (not re-pointed to $REPO_DIR)."
  fi
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

ENABLE_KEYS="[\"${PLUGIN_NAME}@${MARKETPLACE_NAME}\"]"
tmp="$(mktemp)"
if ! jq --argjson keys "$ENABLE_KEYS" \
   '.enabledPlugins = ((.enabledPlugins // {}) + ($keys | map({(.): true}) | add))' \
   "$SETTINGS" > "$tmp"; then
  rm -f "$tmp"; echo "  ! enabledPlugins merge failed (is $SETTINGS valid JSON?)" >&2; exit 1
fi
mv "$tmp" "$SETTINGS"
echo "  • enabledPlugins $ENABLE_KEYS = true  ($SETTINGS)"

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
# the primary destructive-command guard since ADR 0005), plus project-local plansDirectory and an absolute
# autoMemoryDirectory. Non-clobbering: existing keys win, the allow/deny lists are
# unioned, the dirs are set only if absent.
if [[ $DO_SETTINGS -eq 1 ]]; then
  echo "→ Writing personal settings.local.json (allow + deny, plans, memory)…"
  LOCAL="$TARGET/.claude/settings.local.json"
  mkdir -p "$(dirname "$LOCAL")"
  [[ -f "$LOCAL" ]] || echo '{}' > "$LOCAL"

  tmp="$(mktemp)"
  # Allow: the plugin's own tools plus the sanctioned push forms (ADR 0007: develop and work
  # branches are the agent's to push). Deny: destructive shell, and the obvious spellings of a
  # push to the production branch or of tags -- prefix rules can't parse refspecs, so the real
  # decision is hooks/git/enforce-git-flow-skill.py Rule 3; these are defense in depth.
  BASELINE='["Bash(br:*)","Bash(agy:*)","Bash(git diff:*)","Bash(git push origin develop:*)","Bash(git push origin feature/:*)","Bash(git push origin bugfix/:*)","Bash(git push -u origin feature/:*)","Bash(git push -u origin bugfix/:*)","Bash(git push origin --delete feature/:*)","Bash(git push origin --delete bugfix/:*)","Bash(git push -u origin hotfix/:*)","Bash(git push origin hotfix/:*)","mcp__idea__*","mcp__plugin_context7_context7__*"]'
  if ! jq --argjson baseline "$BASELINE" \
     --argjson denylist '["Bash(sudo:*)","Bash(rm -rf:*)","Bash(rm -fr:*)","Bash(rm -r -f:*)","Bash(rm -f -r:*)","Bash(git push --force:*)","Bash(git push -f:*)","Bash(git push origin main:*)","Bash(git push origin master:*)","Bash(git push --tags:*)","Bash(git push origin --tags:*)","Bash(git push --all:*)","Bash(git push --mirror:*)","Bash(git reset --hard:*)","Bash(git clean -f:*)","Bash(git checkout -- .:*)","Bash(git restore .:*)","Bash(git branch -D:*)"]' \
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
  echo
fi

# ---- tracker init: br + git-flow, both auto by default -- the hooks self-gate to .beads/ and
# gitflow.* config, so without this step they silently stay inert until someone remembers to run
# `br init`/`git flow init` by hand. `git flow init -d` just creates `develop` off current HEAD
# with AVH's default naming conventions (verified: works even on a brand-new, zero-commit repo)
# -- it doesn't touch existing history, so auto-running it is as low-risk as `br init`.
if [[ $DO_TRACKER_INIT -eq 1 ]]; then
  echo "→ Tracker init (the hooks self-gate to .beads/ + gitflow projects)…"
  ( cd "$TARGET" && command -v br >/dev/null 2>&1 && [[ ! -d .beads ]] && br init && echo "  • br init done." ) || true
  ( cd "$TARGET" && command -v git-flow >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1 \
      && ! git config --get-regexp '^gitflow\.branch\.' >/dev/null 2>&1 \
      && git flow init -d >/dev/null 2>&1 && echo "  • git flow init -d done." ) || true
  ( cd "$TARGET" && ! command -v git-flow >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1 \
      && ! git config --get-regexp '^gitflow\.branch\.' >/dev/null 2>&1 \
      && echo "  • git-flow (AVH) not installed -- run 'git flow init -d' by hand once it is, to enable the git-flow workflow." ) || true
  echo
fi

echo "Done. Restart Claude (or /reload-plugins) in $TARGET for the plugin to take effect."
