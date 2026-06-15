# Apogee — Architecture

Apogee is a personal Claude Code toolkit: a fork of the
[Claude Code Development Kit](https://github.com/peterkrueck/Claude-Code-Development-Kit) repackaged as
a **plugin + local marketplace**. Its job is to keep Claude Code coherent across sessions (durable
context + repeatable work loop) and to enforce a disciplined workflow via lifecycle hooks.

## Three layers (the core model)

| Layer | What | Where it lives | Delivery |
|---|---|---|---|
| **Machinery** | hooks + commands + workflow skills | `plugins/apogee/` | installed once, **enabled** per project (`enabledPlugins`) — never copied |
| **Content** | `CLAUDE.md`, `GEMINI.md`, `docs/apogee/…` | `scaffold/` → host project | **copied** by `setup.sh`; owned by the project; `docs/apogee/` gitignored in the host |
| **Preferences** | `language`, `defaultMode`, `effortLevel`, `env`, baseline `permissions` | `~/.claude/settings.json` | stays global (can't be delivered per project) |

See [ADR 0002](decisions/0002-plugin-not-global-hooks.md) for why machinery is a plugin rather than
globally-wired hooks.

## Repository layout

```
Apogee/
├── .claude-plugin/marketplace.json   # local marketplace "apogee" → exposes the plugin
├── plugins/apogee/                   # THE PLUGIN (machinery)
│   ├── .claude-plugin/plugin.json    # name: apogee, version, hooks: ./hooks/hooks.json
│   ├── hooks/
│   │   ├── hooks.json                # lifecycle wiring; all paths via ${CLAUDE_PLUGIN_ROOT}
│   │   ├── br/    # beads_rust gates: edit/branch/capture/prime/progress/snapshot + br-sig
│   │   ├── git/   # enforce-git-commit-skill, enforce-git-flow-skill
│   │   ├── idea/  # JetBrains idea-mcp guards (+ lib/idea_symbols.py)
│   │   ├── review/# review-docs-gate, skill-run-tracker
│   │   ├── core/  # security-scan, snapshot-baseline, notify, cleanup, gated, apogee-session-start + config/ + sounds/
│   │   └── lang/  # tool-lang-guard (English-only for external-AI CLIs)
│   ├── skills/    # update-docs, review-work, second-opinion, deploy, image-gen, image-edit, bg-remove
│   └── commands/  # prime.md, plan-feature.md, merge.md  → /apogee:<name>
├── scaffold/                         # project CONTENT (copied per project)
│   ├── CLAUDE.md  GEMINI.md          # convention files (Claude + agy)
│   └── docs/apogee/                  # gitignored in the host project
│       ├── ai-context/{spec,project-structure,progress,deployment-infrastructure}.md
│       └── {business,design-brand,legal,open-issues}/
├── setup.sh   # scaffold (copy) + enable plugin (link)
├── sync.sh    # re-scaffold new template files into an installed project
└── docs/      # THIS documentation
```

## Path portability

All hook commands in `hooks/hooks.json` reference scripts via `${CLAUDE_PLUGIN_ROOT}` so they resolve
from the marketplace cache regardless of where the plugin is installed. Python hooks anchor their
internal imports on `os.path.dirname(os.path.abspath(__file__))` (e.g. the idea guards import
`hooks/idea/lib/idea_symbols.py`), so relocation never breaks imports. The one cross-group reference —
`review-docs-gate.sh` reading `../core/config/pipeline.json` — is relative and verified.

## Self-gating (why global-enable is safe)

Every gate hook no-ops unless its trigger is present in the project:

- **`.beads/`** → the `br/*` gates, `review-docs-gate`, `apogee-session-start`, `gated.sh`.
- **`.idea/` + a running JetBrains IDE** → the `idea/*` guards.
- **git-flow config** (`gitflow.branch.*`) → `enforce-git-flow-skill`, `br-branch-gate`.

So enabling the plugin globally behaves like the old global wiring — the machinery only engages in real
managed projects. A project is considered **Apogee-managed** when it has both `.beads/` **and**
`docs/apogee/` at the same root. Full catalog: [HOOKS.md](HOOKS.md).

## The work loop

`/apogee:prime` (load `docs/apogee/ai-context` + beads state) → work (gated by `br`/git-flow/idea) →
`/apogee:review-work` → `/apogee:update-docs` (the Stop gate enforces this order) →
`/apogee:merge` (verify-only in git-flow repos; delegates to the `git-flow` skill).

## Tracker

Apogee standardizes on **`br` (beads_rust)** — the classic SQLite + JSONL architecture, single static
binary, git-JSONL sync. Rationale and revisit triggers: [ADR 0001](decisions/0001-tracker-beads-rust.md).
