# Apogee — Install, update, uninstall

Apogee separates **content** (copied into a project) from **machinery** (a plugin, enabled — not
copied). `setup.sh` does both halves; the plugin must also be registered once with Claude Code.

## One-time: register the marketplace + install the plugin

In an interactive Claude session, register the marketplace from GitHub:

```
/plugin marketplace add mishagin-dev/Apogee
/plugin install apogee@apogee
/reload-plugins
```

`apogee@apogee` is `<plugin>@<marketplace>`; both names come from the repo's manifests
(`marketplace.json` → `name: "apogee"`), independent of how the marketplace was added.

For toolkit development, add the local clone instead so on-disk edits are picked up by
`/plugin marketplace update apogee`:

```
/plugin marketplace add /Volumes/DevSpace/Mine/active-projects/Apogee
```

This makes the `apogee` plugin available system-wide (cached by the marketplace; files are referenced,
never copied into projects). Commands appear namespaced: `/apogee:prime`, `/apogee:plan-feature`,
`/apogee:merge`; skills as `/apogee:review-work`, `/apogee:update-docs`, `/apogee:second-opinion`, etc.

## Quick: online one-liner

From the project directory you want to set up:

```
curl -fsSL https://raw.githubusercontent.com/mishagin-dev/Apogee/main/install.sh | bash
```

`install.sh` clones the toolkit into `$APOGEE_HOME` (default `~/.apogee`) — re-running pulls the latest
— then hands off to `setup.sh` against the current directory (scaffold + enable globally). That clone
doubles as the local marketplace source, so registration uses `~/.apogee` rather than the GitHub ref.

Forward `setup.sh` flags or an explicit target through `bash -s --`:

```
curl -fsSL .../install.sh | bash -s -- --per-project
curl -fsSL .../install.sh | bash -s -- /path/to/project --no-scaffold
```

Env overrides: `APOGEE_HOME` (clone dir), `APOGEE_BRANCH` (default `main`).

## Set up a project (local clone)

```
./setup.sh [TARGET_DIR] [--per-project] [--no-scaffold] [--init-tracker]
```

| Flag | Effect |
|---|---|
| `TARGET_DIR` | project to set up (default: current dir) |
| *(default)* | enable the plugin **globally** in `~/.claude/settings.json` (`enabledPlugins["apogee@apogee"]=true`) |
| `--per-project` | enable only in `TARGET/.claude/settings.json` |
| `--no-scaffold` | skip copying content; only enable the plugin |
| `--init-tracker` | offer `br init` and remind to run `git flow init` so the gates engage |

What it does:

- **COPY (content):** `CLAUDE.md` + `GEMINI.md` at the project root (never clobbered if present);
  `docs/apogee/ai-context/*.md` and the empty `docs/apogee/{business,design-brand,legal,open-issues}/`
  dirs; `assets/.gitkeep`. Existing files are preserved.
- **EXCLUDE:** appends `docs/apogee/` to the project's `.git/info/exclude` (the toolkit's working
  memory is local-only — kept out of git without touching the host's committed `.gitignore`). Skipped
  with a notice if the target is not a git repo.
- **ENABLE (machinery):** writes the `enabledPlugins` entry (global or per-project). No hooks/skills are
  copied — they live in the plugin.

> Note: `setup.sh` also *attempts* the `claude plugin …` CLI if present; in headless contexts that CLI
> is unavailable, so it falls back to writing `enabledPlugins` directly and prints the `/plugin …`
> registration commands above.

## Update the machinery

The plugin is the single source. To ship a change:

1. Edit `plugins/apogee/…` and bump `plugins/apogee/.claude-plugin/plugin.json` `version`.
2. In any session: `/plugin marketplace update apogee` then `/reload-plugins`.

Local marketplaces **do not auto-update**, so upgrades are always intentional. Every project with
`apogee@apogee` enabled then runs the new version — no per-project copying.

## Sync new scaffold templates into a project

```
./sync.sh [TARGET_DIR]
```

Re-runs the scaffold copy (non-clobbering: existing files untouched, only missing template files added)
so a project can pick up **new** scaffold files without losing customizations. Machinery is not synced
this way — that's `/plugin marketplace update`.

## Uninstall

- **From one project:** remove the `"apogee@apogee": true` entry from that project's
  `.claude/settings.json` (or `~/.claude/settings.json` if enabled globally), then `/reload-plugins`.
  The scaffolded `docs/apogee/`, `CLAUDE.md`, `GEMINI.md` are the project's own — delete if desired.
- **Disable everywhere:** `/plugin disable apogee@apogee` (turns off all of the plugin's hooks at once —
  plugin hooks are all-or-nothing).
- **Remove entirely:** `/plugin uninstall apogee@apogee` and `/plugin marketplace remove apogee`.

## Bootstrap note (developing Apogee itself)

The Apogee repo is intentionally **not** a `.beads/` or git-flow project, so its own gates stay inert
while you develop the toolkit. If you ever add `.beads/`, use the escape envs
(`BR_GATE_OFF=1 REVIEW_GATE_OFF=1 IDEA_GATE_OFF=1 TOOL_LANG_OFF=1`) for friction-free development. See
[ADR 0002](decisions/0002-plugin-not-global-hooks.md) for the migration sequencing (strip global hooks
LAST).
