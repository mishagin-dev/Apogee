# Apogee — Install, update, uninstall

Apogee separates **content** (copied into a project) from **machinery** (a plugin, enabled — not
copied). `setup.sh` does both halves; the plugin must also be registered once with Claude Code.

## One-time: register the marketplace + install the plugin

The plugin is installed from the GitHub marketplace, once per machine, in a Claude Code session:

```
/plugin marketplace add mishagin-dev/Apogee
/plugin install apogee@apogee
/reload-plugins
```

`apogee@apogee` is `<plugin>@<marketplace>`; both names come from the repo's manifests. Updates:
`/plugin marketplace update apogee`, then `/reload-plugins`; hook matchers are read at session
start, so open a new session (or reload) after an update. To try unreleased changes of the
toolkit itself, load the working tree for one session: `claude --plugin-dir plugins/apogee`.

## Quick: online one-liner (project setup)

From the project directory you want to set up:

```
curl -fsSL https://raw.githubusercontent.com/mishagin-dev/Apogee/main/install.sh | bash
```

`install.sh` clones the repo into a temporary directory, runs `setup.sh` against the current
directory (scaffold + enable), and deletes the clone. When the `claude` CLI is on PATH and the
`apogee` marketplace is not registered yet, `setup.sh` registers `mishagin-dev/Apogee` and installs
the plugin; an existing registration is never re-pointed.

Forward `setup.sh` flags or an explicit target through `bash -s --`:

```
curl -fsSL .../install.sh | bash -s -- --per-project
curl -fsSL .../install.sh | bash -s -- /path/to/project --no-scaffold
```

Env override: `APOGEE_BRANCH` (default `main`).

## Set up a project (local clone)

```
./setup.sh [TARGET_DIR] [--per-project] [--no-scaffold] [--no-settings]
           [--no-git-init] [--no-tracker-init]
```

| Flag | Effect |
|---|---|
| `TARGET_DIR` | project to set up (default: current dir) |
| *(default)* | enable the plugin **globally** in `~/.claude/settings.json` (`enabledPlugins["apogee@apogee"]=true`) |
| `--per-project` | enable only in `TARGET/.claude/settings.json` |
| `--no-scaffold` | skip copying content; only enable the plugin |
| `--no-settings` | skip writing `TARGET/.claude/settings.local.json` |
| `--no-git-init` | don't auto `git init` TARGET when it isn't a git repo yet |
| `--no-tracker-init` | don't auto `br init` / `git flow init -d` when TARGET has no `.beads/` or gitflow config yet |

What it does:

- **GIT INIT (auto):** if `TARGET` isn't a git repo yet, runs `git init` first — the
  `.git/info/exclude` writes below need a repo to write into. Skip with `--no-git-init`.
- **COPY (content):** `CLAUDE.md` + `GEMINI.md` at the project root (never clobbered if present);
  `docs/apogee/README.md` (the index `/apogee:prime` reads), `docs/apogee/ai-context/*.md`, and the
  empty working-memory directories `docs/apogee/{domain,design,diagrams,research,prompts,reports}/`
  so the layout is visible from day one. Existing files are preserved.
- **EXCLUDE:** appends the plugin's AI-tooling exclude list
  (`plugins/apogee/hooks/core/config/exclude-list.txt`: `docs/apogee/`, `CLAUDE.md`, `GEMINI.md`,
  `AGENTS.md`, `.claude/`, `.beads/`) to the project's `.git/info/exclude`. All of it is personal
  working state (worked with locally, an IDE with "respect gitignore" off still shows it), not a
  project deliverable, so none of it touches the host's committed `.gitignore` or its git history.
  The decision is deliberate: the repository holds code and project documentation only, and the
  tracker's JSONL is backed up with the rest of the local context rather than committed. Skipped
  with a notice if the target is not a git repo. The plugin's SessionStart hook re-asserts the same
  list on every session start, for the repo root and each first-level submodule, so paths created
  later (plans, memory, a submodule `CLAUDE.md`) never surface in `git status`.
- **TRACKER INIT (auto):** if `TARGET` has no `.beads/` yet, runs `br init`; if it has no
  `gitflow.*` config yet and the AVH `git-flow` binary is installed, initialises git-flow with
  `main` as the production branch (pinned before `git flow init -d`, whose own default on a
  zero-commit repo is `master`; an existing `master` is respected),
  (default branch/prefix conventions, non-interactive — works even on a brand-new zero-commit
  repo). Without the binary installed, prints a reminder instead. Skip both with
  `--no-tracker-init`.
- **ENABLE (machinery):** writes the `enabledPlugins` entry (global or per-project). No hooks/skills are
  copied — they live in the plugin.
- **SETTINGS (per-project):** writes/merges a personal `TARGET/.claude/settings.local.json` with a
  baseline `permissions.allow` (so the plugin's skills run without prompts — `Bash(br:*)`,
  `Bash(agy:*)`, the sanctioned `git push` forms (ADR 0007), plus `mcp__idea__*` and
  `mcp__plugin_context7_context7__*`), a content-agnostic
  `permissions.deny` (`sudo`, `rm -rf`, destructive git). Since [ADR 0005](decisions/0005-enforcement-safety-only.md)
  this deny list — enforced by Claude Code itself, not by Apogee — is the toolkit's primary guard
  against destructive commands; the hooks add exactly two checks on top of it,
  `plansDirectory` (`./.claude/plans`), and an absolute `autoMemoryDirectory` (`TARGET/.claude/memory`).
  Non-clobbering (existing keys win, allow/deny lists unioned); the file is added to
  `.git/info/exclude`. Skip with `--no-settings`. See
  [ADR 0002 Amendment](decisions/0002-plugin-not-global-hooks.md).

> Note: `setup.sh` also *attempts* the `claude plugin …` CLI if present; in headless contexts that CLI
> is unavailable, so it falls back to writing `enabledPlugins` directly and prints the `/plugin …`
> registration commands above.

## Update the machinery

The plugin is the single source. To ship a change:

1. Edit `plugins/apogee/…`.
2. Cut a release with the `/apogee:release` command (Apogee's own dev workflow): it decides the
   SemVer bump, keeps `plugins/apogee/.claude-plugin/plugin.json` `version` and the `apogee` entry
   of `.claude-plugin/marketplace.json` in lockstep, refreshes the CHANGELOG, gates on
   `scripts/validate.sh`, writes the release notes to `$TMPDIR`, and stops (ADR 0007).
3. The operator runs the three printed commands (finish, `git push origin main develop --tags`,
   `gh release create`), then in any session `/plugin marketplace update apogee` and
   `/reload-plugins`.

`/apogee:release` isn't Apogee-specific tooling — it detects where (if anywhere) a project
declares its version and generalizes accordingly, so the same command also drives releases in any
other project that has the plugin enabled.

Marketplaces do not auto-update by default, so upgrades are always intentional. Every project with
`apogee@apogee` enabled then runs the new version — no per-project copying. `scripts/validate.sh`
also asserts the two manifests and the CHANGELOG agree, so a version bump that misses one of them
fails CI.

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

The Apogee repo has no `.beads/`, so the beads-triggered hooks stay inert while you develop the
toolkit. It *is* a git-flow project, so `enforce-git-flow-skill.py` is live — which makes developing
here a genuine end-to-end test of the one interactive gate that ships. There are no escape
environment variables to set: ADR 0005 removed the gates that had them. See
[ADR 0002](decisions/0002-plugin-not-global-hooks.md) for the migration sequencing (strip global hooks
LAST).
