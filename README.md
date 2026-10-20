<div align="center">

# Apogee

### Durable project memory and a safe, repeatable git workflow for Claude Code.

[![CI](https://github.com/mishagin-dev/Apogee/actions/workflows/validate.yml/badge.svg)](https://github.com/mishagin-dev/Apogee/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/mishagin-dev/Apogee)](https://github.com/mishagin-dev/Apogee/releases)
[![License: MIT](https://img.shields.io/github/license/mishagin-dev/Apogee)](LICENSE)

[Install](#install) · [See it work](#see-it-work) · [Getting started](#getting-started) · [How it works](#how-it-works) · [Docs](#documentation)

</div>

---

> [!IMPORTANT]
> Apogee is a Claude Code plugin that registers hooks and copies a few context files into your
> project. It makes no network calls of its own. It never commits its files to your repository:
> everything it writes is kept out of git through `.git/info/exclude`. Agents it guides can push
> `develop` and work branches, but a hook refuses anything that would reach `main` or create a tag.
> Disable it with `/plugin disable apogee@apogee`; full removal is [three steps](#uninstall).

```bash
curl -fsSL https://raw.githubusercontent.com/mishagin-dev/Apogee/main/install.sh | bash
```

---

## The problem

Claude Code starts every session from zero. It does not remember what the project is, what was
decided last week, or what is half-done, and it improvises git: work lands on whatever branch is
checked out, branches get named however, and an agent left alone long enough will merge and push
wherever it can.

If you have kept an architecture decision log, a `CONTRIBUTING.md`, or a git-flow convention, you
already know the fix: write the context down once and make the workflow a habit. Apogee does that
for an agent. It keeps a small set of project docs that every session loads, and routes every unit
of work through one entry and one exit on top of [git-flow](https://nvie.com/posts/a-successful-git-branching-model/)
(work branches merge into `develop`; `main` only receives releases), with issues tracked in
[`br`](https://github.com/Dicklesworthstone/beads_rust), a local issue tracker for agents.

It is a fork of the [Claude Code Development Kit](https://github.com/peterkrueck/Claude-Code-Development-Kit),
repackaged as a plugin instead of per-project file copies, with the git workflow and local-only
AI context added on top. It is a personal toolkit with opinionated
dependencies (git-flow AVH, the `br` tracker); read it as such.

---

## See it work

A feature, from an empty session to `develop` on the remote (an *epic* is a `br` issue grouping
the steps of one branch):

```text
> /apogee:prime
  Apogee: billing service. Stack: Symfony 8.1, PostgreSQL. Next up: invoice export (progress.md).
  Index: domain/vat-rules.md, design/design-system.md.

> /apogee:start feature invoice CSV export
  Opened feature/invoice-csv-export off develop at 4f2a91c, published to origin.
  Carried along: none.
  Epic bill-7 created and linked, step bill-7.1 claimed.
  Other open work: none.

  ... the agent implements, committing each step through apogee:git-commit ...

> /apogee:finish
  Review: 0 high, 1 low (noted). Intent: MATCHES.
  Docs: spec.md updated; public docs: docs/export.md refreshed (sources: src/Export/).
  Tests: symfony php bin/phpunit, 214 passed.
  Finished feature/invoice-csv-export into develop (6 commits), pushed develop, epic closed.
```

And the line it will not cross:

```text
> git push origin main
  Denied: This push targets 'main'. Publishing 'main' or tags is reserved for the operator
  (ADR 0007): push `develop` and work branches freely; for a release, /apogee:release prepares
  the branch and prints the finish and push commands to run in a terminal.
```

---

## Install

Requirements: Claude Code, `git`, `jq`. Optional, each unlocks one part: [git-flow AVH](https://github.com/petervanderdoes/gitflow-avh)
(the branch workflow), [`br`](https://github.com/Dicklesworthstone/beads_rust) (the issue tracker and `/apogee:run-plan`),
`agy` (independent second opinion), `gh` (publishing releases).

From the project you want to set up:

```bash
curl -fsSL https://raw.githubusercontent.com/mishagin-dev/Apogee/main/install.sh | bash
```

It clones the toolkit into `~/.apogee`, registers that clone as the `apogee` plugin marketplace
and sets up the current project. Restart Claude Code (or `/reload-plugins`). Only if the installer
printed a NOTE that it could not reach the `claude` CLI, register it once in a session:

```text
/plugin marketplace add ~/.apogee
/plugin install apogee@apogee
/reload-plugins
```

### What it touches

| Where | What | Reversible by |
|---|---|---|
| `~/.apogee/` | A clone of this repo, the source the plugin installs from | `rm -rf ~/.apogee` |
| `~/.claude/settings.json` | `enabledPlugins["apogee@apogee"] = true`; with `--per-project`, `<project>/.claude/settings.json` instead | `/plugin disable apogee@apogee` |
| Your project | `CLAUDE.md`, `GEMINI.md`, `docs/apogee/` (index, four context docs, six empty working-memory dirs), `.claude/settings.local.json` (permission baseline, `plansDirectory`, `autoMemoryDirectory`) | delete them; none are tracked |
| `.git/info/exclude` | Lines keeping the files above, plus `AGENTS.md`, `.claude/` and `.beads/`, out of git; never `.gitignore` | delete the lines |
| Repo setup | `git init`, `br init` (`.beads/`), `git flow init -d` (a `develop` branch, `gitflow.*` config) if missing; `--no-git-init`, `--no-tracker-init` to skip | see Uninstall |

Hooks run locally on tool calls; none of them sends data anywhere. The permission baseline
allows the plugin's own commands (`br`, `agy`, `git diff`, pushes of `develop` and work branches)
and the JetBrains and Context7 MCP tools,
and denies destructive ones (`sudo`, `rm -rf`, `git push --force`, `git reset --hard`, pushes of
`main` and tags).

<details>
<summary><b>Install from a local clone, per-project, or without scaffolding</b></summary>

```bash
/path/to/Apogee/setup.sh /path/to/project                  # enable globally (default)
/path/to/Apogee/setup.sh /path/to/project --per-project    # enable in this project only
/path/to/Apogee/setup.sh /path/to/project --no-scaffold    # plugin only, no CLAUDE.md / docs
```

Flags pass through the one-liner with `bash -s --`, e.g. `… | bash -s -- --per-project`.
`APOGEE_HOME` overrides the clone location. Full reference: [docs/INSTALL.md](docs/INSTALL.md).

</details>

<details>
<summary><b>Update</b></summary>

```bash
git -C ~/.apogee pull
```

Then, in Claude Code: `/plugin marketplace update apogee` and `/reload-plugins`. Existing
`CLAUDE.md` and docs in your projects are never overwritten; `sync.sh <project>` adds template
files that are new since you installed.

</details>

### Uninstall

1. `/plugin uninstall apogee@apogee` and `/plugin marketplace remove apogee`.
2. In each project, whatever you don't want to keep: `CLAUDE.md`, `GEMINI.md`, `docs/apogee/`,
   `.claude/settings.local.json` (or `.claude/` as a whole), `.beads/`, and the Apogee lines in
   `.git/info/exclude`. If setup initialised git-flow and you don't want it: `git config
   --remove-section gitflow.branch` and `--remove-section gitflow.prefix`, and delete `develop`.
3. `rm -rf ~/.apogee`.

---

## Getting started

1. **Once per project:** `/apogee:init` in Plan Mode. It reads the codebase and fills
   `docs/apogee/ai-context/` and `CLAUDE.md` with what it found, for you to approve.
2. **Every session:** `/apogee:prime`. In projects with both `.beads/` and `docs/apogee/`, a
   session-start hook reminds the agent to run it.
3. **Every piece of work:** `/apogee:start <type> <slug>`, work, `/apogee:finish`.

| Type | Opens | Finish does |
|---|---|---|
| `feature`, `bugfix` | A branch off a fresh `develop`, published, linked to a `br` epic | Review, docs, tests, merge into `develop`, push `develop` |
| `hotfix` | A branch off `main` with the next patch version | Review, version bump, CHANGELOG, then hands you the finish commands |
| `research` | A dated note in `docs/apogee/research/`, no branch | Checks the conclusion and sources, closes it, proposes the follow-up |

4. **Releases:** `/apogee:release [major|minor|patch]` prepares the release branch, CHANGELOG
   and release notes, then prints three commands for you to run:

   ```bash
   GIT_MERGE_AUTOEDIT=no git flow release finish -m "4.0.0" 4.0.0
   git push origin main develop --tags
   gh release create 4.0.0 --notes-file "$TMPDIR/apogee-release-4.0.0.md" --verify-tag
   ```

Plan Mode works too: approve a plan in a project with `br` and git-flow, and `/apogee:run-plan`
executes it epic by epic, unattended, through the same start/finish pair. It stops after three
epics by default (`max-epics:` to change); run it again to continue.

---

## How it works

Three layers with a hard boundary. The **plugin** (hooks and skills) is installed once and only
enabled per project, so an update reaches every project at once. The **content** (`CLAUDE.md`,
`docs/apogee/`) is copied into each project and owned by it, local-only. Your **preferences**
(language, model, effort) stay in your global Claude Code settings.

<details>
<summary><b>The hooks: two that block, the rest inform</b></summary>

The context hooks switch themselves off unless their trigger exists in the project (`.beads/`,
git-flow config, `docs/apogee/`), so enabling the plugin globally is safe. The two blocking hooks
are always on.

Two hooks can refuse an action, both guarding something that cannot be undone:

- **Secret scan.** A high-confidence credential (vendor-prefixed token, private key, credentialed
  connection string) in a call to an MCP server, a web fetch, or the `agy` CLI is denied.
- **Production-branch wall.** Any push whose destination is `main` or a tag, in any refspec
  spelling, any force push, a merge while `main` is checked out, `git tag <name>`, and
  `git flow release|hotfix finish` are denied to the agent, in every repo with a `main`.

Everything else injects context: the reminder to run `/apogee:prime`, keeping AI files out of
git, recording an approved plan in `br`, a reminder about open branches. Rules that are not
irreversible live in `CLAUDE.md` and the skills, where a human can override them.
Catalog: [docs/HOOKS.md](docs/HOOKS.md).

</details>

<details>
<summary><b>Working memory: docs/apogee</b></summary>

| Path | Holds |
|---|---|
| `README.md` | The index `/apogee:prime` reads: one line per file and when to read it |
| `ai-context/` | `spec.md`, `project-structure.md`, `progress.md`, `deployment-infrastructure.md` |
| `domain/` | Business rules the code does not explain |
| `design/` | Design sources and `design-system.md` |
| `diagrams/`, `research/`, `prompts/`, `reports/` | Schemas, dated research notes, reusable prompts, generated reports |

`/apogee:update-docs` keeps it current and pruned. Human-facing docs under `docs/` are a separate
job: `/apogee:public-docs`, where each doc declares the source paths it covers and `/apogee:finish`
refreshes the ones whose sources changed.

</details>

<details>
<summary><b>All skills</b></summary>

| Skill | Purpose |
|---|---|
| `/apogee:init`, `/apogee:prime` | Onboard a project once; load its context every session |
| `/apogee:plan-feature` | Plan in Plan Mode with parallel research and a second opinion |
| `/apogee:start`, `/apogee:finish` | Open and close every unit of work (feature, bugfix, hotfix, research) |
| `/apogee:release` | Prepare a release from `develop`; you run the finish |
| `/apogee:run-plan` | Execute an approved `br` plan unattended, epic by epic |
| `/apogee:review-work` | Built-in `/code-review` for bugs, plus a project-rules audit and an intent check |
| `/apogee:update-docs`, `/apogee:public-docs` | Agent context and human docs, respectively |
| `/apogee:second-opinion` | An independent model via `agy` for contested decisions |
| `/apogee:readme` | Write or validate a README like this one |
| `/apogee:ai-clean-room` | Black-box reimplementation procedure, manual only |
| `apogee:git-commit`, `apogee:git-flow`, `apogee:br`, `apogee:symfony-cli-workflow` | The lower layer the entry points use |

</details>

---

## FAQ

**Does it work without git-flow or `br`?** Mostly. Project memory, review, docs and research
notes work anywhere. Without git-flow, `finish` pushes the branch and leaves the merge to you;
`run-plan` needs both. The related context hooks stay off.

**Why can't the agent release?** By design: everything below `main` is autonomous, and the
release is kept for a human. The reasoning is recorded as an architecture decision record,
[ADR 0007](docs/decisions/0007-production-branch-wall.md).

**Will it commit `CLAUDE.md` into my repository?** No. AI tooling is local-only by decision; a
session-start hook re-asserts the excludes for the repo and its submodules.

---

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the three layers and the repository layout
- [docs/HOOKS.md](docs/HOOKS.md): every hook, its trigger and its decision
- [docs/INSTALL.md](docs/INSTALL.md): install, per-project enable, update, sync, uninstall
- [docs/decisions/](docs/decisions/): the eight ADRs, from the tracker choice to start/finish
- [CHANGELOG.md](CHANGELOG.md)

## Contributing

Issues and pull requests are welcome; this is a personal toolkit, so changes that fit its
opinions are the ones that land. `bash scripts/validate.sh` must pass.

## License

MIT, see [LICENSE](LICENSE).
