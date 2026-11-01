---
name: init
description: "Bootstrap a project's Apogee context: research the codebase, fill docs/apogee/ai-context and the root CLAUDE.md, seed a CLAUDE.md per first-level submodule. Run once per project, in Plan Mode."
argument-hint: "[--migrate] [notes]"
effort: high
disable-model-invocation: true
---

# Init Command

Bootstrap a project's Apogee context: research the codebase, plan, then fill the full doc set
(`docs/apogee/ai-context/*` + root `CLAUDE.md`) and seed a flat `CLAUDE.md` in each first-level
submodule. Designed to run inside Plan Mode (toggle with Shift+Tab).

**Usage:** `/apogee:init [--migrate] [notes]`

Run this once on a new project (or after adding submodules). Optional `[notes]` steer focus
(e.g. "this is a mobile app", "skip the legacy/ dir"). `--migrate` converts an existing project's
`CLAUDE.md` to the project-only layout (section "Migrate" below) and stops.

**What goes into `CLAUDE.md`.** Only this project's facts, settled decisions and its own rules or
exceptions, in the scaffold's sections (Project, Operator Model, Key Architecture Decisions,
Project Rules, Testing, Privacy & Security, Bilingual Documentation). Apogee's general rules and
tone are not written there: they come from the plugin's `rules/RULES.md` and `rules/SOUL.md`,
injected at every session start (ADR 0009).

---

## Migrate (`--migrate`)

For a project set up before 4.0, whose `CLAUDE.md` still carries Apogee's general sections
(typically "Critical Rules", "Communication Style", "Tool Usage Rules", "Coding Standards").

1. Read the project's `CLAUDE.md` and the plugin's rules:
   `${CLAUDE_PLUGIN_ROOT}/rules/RULES.md` and `${CLAUDE_PLUGIN_ROOT}/rules/SOUL.md`.
2. Classify every line of those general sections: **toolkit** (restates something in RULES.md or
   SOUL.md, in any wording or version) or **project** (a fact, constraint or exception that
   belongs to this project only: a test command, a naming rule, "never touch `legacy/`", a
   deliberate deviation from a toolkit rule).
3. Show the plan: toolkit lines to drop, project lines to keep and where they go (Project Rules,
   Testing, …). Ask for confirmation; this is the user's file.
4. Rewrite `CLAUDE.md` into the scaffold layout
   (`${CLAUDE_PLUGIN_ROOT}/../../scaffold/CLAUDE.md` is not reachable from a project, so use the
   section list above), preserving every project line verbatim. Sections that end up empty keep
   only their heading and a one-line comment.
5. Report what was removed and what was kept. Stop; the rest of init does not run.


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
"Create Missing Files" step) to populate the core docs and fill the root `CLAUDE.md`'s project
sections from the actual codebase (project facts only, see "What goes into CLAUDE.md"). **A core doc is MISSING when it does not exist OR still carries the `apogee:scaffold-stub`
sentinel** (`setup.sh` scaffolds these template stubs — placeholders, not real docs). Treat a stub as
create-from-scratch: replace its entire content with researched project context and drop the sentinel;
refine only docs that lack it. Do not restate that skill's ownership/density rules here — defer to it (single source of
truth: each fact in exactly one doc; document only what can't be inferred from the code).

**Submodules (first-level, non-clobbering).** For each submodule path: if `<path>/CLAUDE.md` does
**not** already exist, create a **flat** one — minimal and self-contained:

- **Purpose** — 1–2 lines on what this submodule is and why the parent depends on it.
- **Structure** — only the non-obvious key dirs/entry points (skip what's clear from a glance).
- **Rules** — constraints specific to this submodule (build/test quirks, what not to touch).
- **Pointer** — a closing line: `Submodule of <parent-repo>; shared conventions live in the parent CLAUDE.md.`

Keep it short — a flat working file, not the full root template. Never overwrite an existing
`CLAUDE.md` in a submodule.

A submodule is its own git repo, so the parent's `.git/info/exclude` does not cover it. Nothing to
do by hand: the plugin's SessionStart hook re-asserts the AI-tooling exclude list (`CLAUDE.md`,
`GEMINI.md`, `docs/apogee/`, `.claude/`, `.beads/`, `.scratch/`) for the parent and every first-level
submodule at the start of each session, so a submodule `CLAUDE.md` created here stays out of git
from the next session on. Do not verify it, do not stage it, do not add it to `.gitignore`.

**Index.** `docs/apogee/README.md` is the index `/apogee:prime` reads. Drop its scaffold sentinel
and list whatever already exists under `docs/apogee/` beyond `ai-context/` (one line each); leave
the optional-directories table as guidance.

**Finish.** Load the freshly written core docs (as `/apogee:prime` would) so the session continues
primed, then summarize what was created vs skipped (and any submodules left untouched).
---

**Notes / focus:** $ARGUMENTS
