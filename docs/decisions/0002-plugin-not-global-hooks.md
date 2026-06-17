# ADR 0002 — Package as a plugin, not globally-wired hooks

**Status:** Accepted · **Date:** 2026-06-15

## Context

The workflow machinery (beads/`br` gates, git-flow & git-commit enforcement, idea-mcp guards, the hard
review→docs Stop gate, the language guard, the MCP secret-scan) was originally wired **globally** in
`~/.claude/settings.json` with absolute paths into `~/.claude/hooks/*`. Problems:

- gates were imposed everywhere, including throwaway dirs with no project;
- the machinery was duplicated per project (`<project>/.claude/`);
- it was hard to version and update coherently;
- there was no clean boundary between "personal preferences" and "project machinery".

Claude Code's plugin system supports installing a plugin **once** and merely *enabling* it per project
(`enabledPlugins`), with bundled hooks/skills/commands and `${CLAUDE_PLUGIN_ROOT}` for script paths.
Plugin hooks fire **in addition to** user hooks.

## Decision

Repackage the machinery as the **`apogee` plugin** served by a **local marketplace** (this repo), and
split responsibilities three ways:

1. **Machinery → plugin** (`plugins/apogee/`): hooks + commands + workflow skills. Installed once,
   enabled per project. Update once → every enabled project gets it.
2. **Content → scaffold** (`scaffold/`): `CLAUDE.md`, `GEMINI.md`, `docs/apogee/…`, copied into each
   project by `setup.sh` and owned by it. `docs/apogee/` is excluded via the host project's
   `.git/info/exclude` (zero git footprint from the toolkit).
3. **Preferences → stay global** in `~/.claude/settings.json`: `language`, `defaultMode`, `effortLevel`,
   `env`, baseline `permissions`. These cannot be delivered per project, so they remain personal.
   *(Baseline `permissions` amended 2026-06-17 — now delivered per-project; see the Amendment below.)*

Every gate hook **self-gates** (no-ops unless `.beads/`, `.idea/` + a running JetBrains IDE, or git-flow
config is present), so enabling the plugin globally reproduces the previous behavior minus the
per-project duplication.

## Migration sequencing (safety)

Build & validate the plugin first; **strip the global `hooks` block from `~/.claude/settings.json`
LAST**, only after the plugin is confirmed working — otherwise a window with no gates could open.
During validation, isolate by temporarily backing up and removing the global `hooks` block so plugin
hooks are tested cleanly (no double-fire / `.git/index.lock` races).

## What stays where (boundary)

| Concern | Home |
|---|---|
| Hooks, commands, workflow skills | `apogee` plugin (this repo) |
| Project docs / CLAUDE.md / GEMINI.md | scaffold → copied into the project |
| Universal skills (`br`, `git-commit`, `git-flow`, `idea-mcp`) | `~/.claude/skills/` (global, bare names — avoids `/apogee:` namespacing) |
| Language, mode, effort, env | `~/.claude/settings.json` (global) |
| Baseline `permissions`, `plansDirectory`, `autoMemoryDirectory` | per-project `TARGET/.claude/settings.local.json` (git-excluded) — *amended, see below* |

## Consequences

- Plugin-bundled commands/skills are namespaced: `/apogee:prime`, `/apogee:review-work`, etc.
- Updating the toolkit = bump `plugins/apogee/.claude-plugin/plugin.json` `version`, then
  `/plugin marketplace update apogee` (local marketplaces do not auto-update — upgrades are always
  intentional).
- Universal skills stay global on purpose: the git-enforcement hooks reference
  `~/.claude/skills/git-commit|git-flow`, and bare names preserve muscle memory.

## Amendment (2026-06-17) — baseline permissions delivered per-project

The original split (§3) kept baseline `permissions` global. In practice the plugin's skills need
allow-rules — `Bash(br:*)`, `Bash(agy:*)`, and the image-skill commands — to run without prompts, and
a fresh machine or new project had none, so the toolkit did not work out of the box. `setup.sh` now
writes a **personal, git-excluded** `TARGET/.claude/settings.local.json` carrying a baseline
`permissions.allow`, `plansDirectory` (`./.claude/plans`), and an **absolute** `autoMemoryDirectory`
(`TARGET/.claude/memory` — relative paths are not accepted for that key). The merge is non-clobbering
(existing keys win, the allow-list is unioned and de-duped). The file is added to `.git/info/exclude`,
consistent with `docs/apogee/`. Only `language`/`defaultMode`/`effortLevel`/`env` remain irreducibly
global. Opt out with `setup.sh --no-settings`.
