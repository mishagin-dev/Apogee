# Prime Command

Load core context for the project.

**Usage:** `/prime [--deploy] [task]`

## Routing

Parse `$ARGUMENTS` as whitespace-separated tokens:
1. **Flag:** if any token equals `--deploy` (case-insensitive), set `deploy_mode = true` and remove it from the token list.
2. **Task:** remaining tokens are the user's task (if any).

`--deploy` may appear anywhere in the arguments (e.g. both `/prime --deploy` and `/prime fix login bug --deploy` are valid).

**Why the flag exists:** `deployment-infrastructure.md` is operational reference (accounts, secrets, hosting, CI/CD) — stable and often large. Loading it on every routine `/prime` wastes context. Read it only when actively touching deploy/infra/CI work.

**Why `progress.md` is conditional too:** it's "what's been happening" — recent changes, known issues/blockers, next-step framing. That's exactly what you need to decide *what* to work on next — and irrelevant noise once a task is already specified. A given task needs orientation (what this project is, how it's structured), not a status report.

**Important:** Paths below are written as plain text (not `@`-references) on purpose — the harness auto-expands every `@`-mention in a slash-command body before routing runs, which would unconditionally read every listed file and defeat the conditional `--deploy` load.

## Files to load (parallel — single message, multiple Read calls)

1. `docs/apogee/ai-context/spec.md`
2. `docs/apogee/ai-context/project-structure.md`
3. *(only if no task was given in `$ARGUMENTS`)* `docs/apogee/ai-context/progress.md`
4. *(only if `deploy_mode`)* `docs/apogee/ai-context/deployment-infrastructure.md`

**If a core doc is missing or still a scaffold stub** (it carries the `apogee:scaffold-stub` sentinel — `setup.sh` creates these placeholders), it isn't fatal — the project isn't initialized yet. **Do not load a stub as real context** (it's generic placeholder text): note which docs are absent or stub-only and suggest running `/apogee:init` to research the codebase and fill them, then continue with whatever real context is available.

## Response

After reading, briefly confirm:
- What this project is
- Current status and recent progress, immediate priorities or blockers — *only if `progress.md`
  was actually loaded (i.e. no task was given); don't claim to know this when it wasn't read*
- Whether `--deploy` was active (or note it was skipped if the user might want infra context)

Then process the user's request: $ARGUMENTS
