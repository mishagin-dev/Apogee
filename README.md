# Apogee

Personal Claude Code toolkit — a fork of the
[Claude Code Development Kit](https://github.com/peterkrueck/Claude-Code-Development-Kit)
repackaged as a **plugin + local marketplace**. Install the machinery once; enable it per project.

## What's here

```
.claude-plugin/marketplace.json   # local marketplace exposing the `apogee` plugin
plugins/apogee/                   # THE PLUGIN (machinery — installed once, linked per project)
  ├── hooks/                      # lifecycle gates: br/git-flow/idea/review + core advisory + lang guard
  ├── skills/                     # workflow skills: update-docs, review-work, second-opinion, deploy, image-*
  └── commands/                   # /apogee:prime, /apogee:plan-feature, /apogee:merge
scaffold/                         # project CONTENT (copied per project, gitignored in the host)
  ├── CLAUDE.md  GEMINI.md        # convention files (Claude + agy)
  └── docs/apogee/                # working-memory docs (spec, project-structure, progress, ...)
setup.sh                          # scaffold content (copy) + enable plugin (link)
sync.sh                           # re-scaffold new template files into an installed project
```

## Model

- **Machinery** (hooks + commands + workflow skills) lives in the `apogee` plugin. It is installed
  once and merely *enabled* per project via `enabledPlugins` — never copied. Update once → every
  enabled project gets it.
- **Content** (`CLAUDE.md`, `GEMINI.md`, `docs/apogee/*`) is *copied* into each project by `setup.sh`
  and owned by that project. `docs/apogee/` is added to the host project's `.gitignore`.
- Personal preferences (language, default mode, effort, env, baseline permissions) stay in
  `~/.claude/settings.json` — they can't be delivered per project.

## Install into a project

```bash
/path/to/Apogee/setup.sh /path/to/your-project            # enable globally (default)
/path/to/Apogee/setup.sh /path/to/your-project --per-project
```

Then, once, in an interactive Claude session:

```
/plugin marketplace add /path/to/Apogee
/plugin install apogee@apogee
/reload-plugins
```

## Update

Bump `plugins/apogee/.claude-plugin/plugin.json` `version`, then in any session:

```
/plugin marketplace update apogee
/reload-plugins
```

## Gates self-gate

Every hook no-ops unless its trigger is present (`.beads/`, `.idea/` + a running JetBrains IDE, or
git-flow config), so enabling the plugin globally is safe — the machinery only engages in real
projects. Escape hatches: `BR_GATE_OFF=1`, `REVIEW_GATE_OFF=1`, `IDEA_GATE_OFF=1`, `TOOL_LANG_OFF=1`.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — the three-layer model (plugin / scaffold / preferences) and repo layout
- [docs/HOOKS.md](docs/HOOKS.md) — full hook catalog: events, gating conditions, escape envs
- [docs/INSTALL.md](docs/INSTALL.md) — install, per-project enable, update, sync, uninstall
- [docs/decisions/](docs/decisions/) — ADRs: [0001 tracker = beads_rust](docs/decisions/0001-tracker-beads-rust.md), [0002 plugin not global hooks](docs/decisions/0002-plugin-not-global-hooks.md)

## Status

Built and statically validated (manifests, hook scripts, scaffold). **Pending:** live plugin
validation in a real session (`/plugin marketplace add` → `install` → `/reload-plugins`), then stripping
the legacy global `hooks` block from `~/.claude/settings.json` (do this LAST), then cleaning up the old
`Maestro/` bootstrap folder.
