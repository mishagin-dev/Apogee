# Apogee — Architecture

Apogee is a personal Claude Code toolkit: a fork of the
[Claude Code Development Kit](https://github.com/peterkrueck/Claude-Code-Development-Kit) repackaged as
a **plugin + local marketplace**. Its job is to keep Claude Code coherent across sessions (durable
context + repeatable work loop) and to keep a disciplined workflow available via lifecycle hooks.
Since [ADR 0005](decisions/0005-enforcement-safety-only.md) those hooks mostly *inform* rather than
*block*: exactly two can refuse an action, and both defend outcomes that cannot be undone — a
secret leaving the machine, and anything reaching the production branch or a tag (ADR 0007).

## Three layers (the core model)

| Layer | What | Where it lives | Delivery |
|---|---|---|---|
| **Machinery** | hooks + commands + workflow skills | `plugins/apogee/` | installed once, **enabled** per project (`enabledPlugins`) — never copied |
| **Content** | `CLAUDE.md`, `GEMINI.md`, `docs/apogee/…` | `scaffold/` → host project | **copied** by `setup.sh`; owned by the project; kept out of git via the host's `.git/info/exclude` together with `.claude/` and `.beads/` (the plugin's `exclude-list.txt`, re-asserted every session start) — the repository holds code and project documentation only |
| **Preferences** | `language`, `defaultMode`, `effortLevel`, `env` | `~/.claude/settings.json` | stays global (can't be delivered per project) |
| **Per-project settings** | baseline `permissions.allow`, `plansDirectory`, `autoMemoryDirectory` | `TARGET/.claude/settings.local.json` | **written** (non-clobbering merge) by `setup.sh`; personal, git-excluded ([ADR 0002 Amendment](decisions/0002-plugin-not-global-hooks.md)) |

See [ADR 0002](decisions/0002-plugin-not-global-hooks.md) for why machinery is a plugin rather than
globally-wired hooks.

## Repository layout

```
Apogee/
├── .claude-plugin/marketplace.json   # local marketplace "apogee" → exposes the plugin
├── plugins/apogee/                   # THE PLUGIN (machinery)
│   ├── .claude-plugin/plugin.json    # name: apogee, version (hooks/hooks.json auto-loads by convention)
│   ├── hooks/
│   │   ├── hooks.json                # lifecycle wiring; all paths via ${CLAUDE_PLUGIN_ROOT}
│   │   ├── br/    # br-capture-gate (plan -> epic), br-prime (agent guide)
│   │   ├── git/   # enforce-git-flow-skill (the only Bash gate) + unfinished-branch-nudge, lib/
│   │   └── core/  # security-scan (+ config/sensitive-patterns.json), cleanup, apogee-session-start
│   ├── skills/    # update-docs, review-work, second-opinion, image-gen, image-edit, bg-remove,
│   │              #   public-docs, readme, symfony, ai-clean-room, br, git-commit, git-flow
│   │              #   + the entry points init, prime, plan-feature, release, merge, run-plan → /apogee:<name>
│   │              #   (skills, not commands/: Claude Code merged the two formats; user-only ones set
│   │              #   disable-model-invocation)
├── scaffold/                         # project CONTENT (copied per project)
│   ├── CLAUDE.md  GEMINI.md          # convention files (Claude + agy)
│   └── docs/apogee/ai-context/       # {spec,project-structure,progress,deployment-infrastructure}.md
├── tests/     # smoke-run-plan.sh: the hook backstop against real br + git-flow sandboxes
├── install.sh # online one-liner: clone the toolkit into ~/.apogee + run setup.sh
├── setup.sh   # scaffold (copy) + enable plugin (link)
├── sync.sh    # re-scaffold new template files into an installed project
└── docs/      # THIS documentation
```

## Path portability

All hook commands in `hooks/hooks.json` reference scripts via `${CLAUDE_PLUGIN_ROOT}` so they resolve
from the marketplace cache regardless of where the plugin is installed. Python hooks anchor their
internal imports on `os.path.dirname(os.path.abspath(__file__))` (e.g. `enforce-git-flow-skill.py`
imports `hooks/git/lib/gitflow_common.py`), so relocation never breaks imports.

There are **no cross-group imports left**. `hooks/core/lib/` existed to share helpers between the br,
review, idea and git brackets; ADR 0005 removed every consumer but one per helper, so the directory
was dissolved and each survivor moved into — or was inlined by — the hook that actually uses it.
Only bring a shared lib back when a third consumer genuinely appears. `scripts/validate.sh` verifies
that every `${CLAUDE_PLUGIN_ROOT}` path in `hooks.json` still resolves.

## Self-gating (why global-enable is safe)

Every hook no-ops unless its trigger is present in the project:

- **`.beads/`** → `br-capture-gate`, `br-prime`, `apogee-session-start`.
- **git-flow config** (`gitflow.branch.*`) → `enforce-git-flow-skill`, `unfinished-branch-nudge`.
- **any `mcp__` tool call, `WebFetch`, `WebSearch`, or an `agy` command via Bash** →
  `security-scan.sh` (the one unconditional hook).

So enabling the plugin globally behaves like the old global wiring — the machinery only engages in real
managed projects. A project is considered **Apogee-managed** when it has both `.beads/` **and**
`docs/apogee/` at the same root. Full catalog: [HOOKS.md](HOOKS.md).

## The work loop

One-time bootstrap: `/apogee:init` (research the codebase, fill `docs/apogee/ai-context` + root
`CLAUDE.md`, seed a flat `CLAUDE.md` in each first-level submodule). Then the recurring loop:

`/apogee:prime` (load `docs/apogee/ai-context` + beads state) → work (tracked in `br`, on a git-flow
branch) → `/apogee:review-work` → `/apogee:update-docs` → `/apogee:merge` (runs the docs/clean-tree
guardrails, then delegates to the `git-flow` skill).

Nothing forces that order any more — the Stop gate that did was removed by ADR 0005 after it spent
more releases being repaired than it spent catching mistakes. `/apogee:merge` still checks docs
freshness and a clean tree before finishing a branch, which is where the check has teeth without
being able to wedge a session. For unattended runs, `/apogee:run-plan` drives the whole loop itself.

## Tracker

Apogee standardizes on **`br` (beads_rust)** — the classic SQLite + JSONL architecture, single static
binary, git-JSONL sync. Rationale and revisit triggers: [ADR 0001](decisions/0001-tracker-beads-rust.md).
