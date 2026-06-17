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
| Language, mode, effort, env, baseline permissions | `~/.claude/settings.json` (global) |

## Consequences

- Plugin-bundled commands/skills are namespaced: `/apogee:prime`, `/apogee:review-work`, etc.
- Updating the toolkit = bump `plugins/apogee/.claude-plugin/plugin.json` `version`, then
  `/plugin marketplace update apogee` (local marketplaces do not auto-update — upgrades are always
  intentional).
- Universal skills stay global on purpose: the git-enforcement hooks reference
  `~/.claude/skills/git-commit|git-flow`, and bare names preserve muscle memory.
