# Init Command

Bootstrap a project's Apogee context: research the codebase, plan, then fill the full doc set
(`docs/apogee/ai-context/*` + root `CLAUDE.md`) and seed a flat `CLAUDE.md` in each first-level
submodule. Designed to run inside Plan Mode (toggle with Shift+Tab).

**Usage:** `/apogee:init [notes]`

Run this once on a new project (or after adding submodules). Optional `[notes]` steer focus
(e.g. "this is a mobile app", "skip the legacy/ dir").

---

## Phase 1 — Research (parallel)

Build an accurate picture of the project before writing anything. Dispatch sub-agents in parallel to
map: what the project is and does, the tech stack, the directory structure and entry points, and the
current status (read `git log` / open work). For unfamiliar libraries, frameworks, or platform
capabilities, use Context7 MCP first; WebSearch only if Context7 lacks coverage. Treat training data
as potentially stale.

Enumerate **first-level** git submodules (skip silently if there is no `.gitmodules`):

```bash
git config --file .gitmodules --get-regexp '^submodule\..*\.path$'
```

Each output line is `submodule.<name>.path <path>` — collect the `<path>` values. Do **not** recurse
into nested submodules.

## Phase 2 — Plan (in Plan Mode)

Present, for approval:

- **Understanding** — a concise summary of what the project is, its stack, and its current state.
- **Fill plan** — which of the 4 core docs (`spec.md`, `project-structure.md`, `progress.md`,
  `deployment-infrastructure.md`) and the root `CLAUDE.md` you will create or refine.
- **Submodules** — the list of first-level submodule paths that will receive a flat `CLAUDE.md`. Mark
  any that already have one — those are **skipped** (never overwritten).

For a large or unfamiliar codebase, optionally run `/apogee:second-opinion` on this plan to catch blind
spots. Then exit Plan Mode with the synthesized plan.

> If you are **not** in Plan Mode, present the same plan inline and ask for confirmation before writing.

## Phase 3 — Execute (after approval)

**Root docs + CLAUDE.md.** Follow the `/apogee:update-docs` skill's initial-creation path (its
"Create Missing Files" step) to populate the core docs and refine the root `CLAUDE.md` from the actual
codebase. Do not restate that skill's ownership/density rules here — defer to it (single source of
truth: each fact in exactly one doc; document only what can't be inferred from the code).

**Submodules (first-level, non-clobbering).** For each submodule path: if `<path>/CLAUDE.md` does
**not** already exist, create a **flat** one — minimal and self-contained:

- **Purpose** — 1–2 lines on what this submodule is and why the parent depends on it.
- **Structure** — only the non-obvious key dirs/entry points (skip what's clear from a glance).
- **Rules** — constraints specific to this submodule (build/test quirks, what not to touch).
- **Pointer** — a closing line: `Submodule of <parent-repo>; shared conventions live in the parent CLAUDE.md.`

Keep it short — a flat working file, not the full root template. Never overwrite an existing
`CLAUDE.md` in a submodule.

**Finish.** Load the freshly written core docs (as `/apogee:prime` would) so the session continues
primed, then summarize what was created vs skipped (and any submodules left untouched).

ultrathink

---

**Notes / focus:** $ARGUMENTS
