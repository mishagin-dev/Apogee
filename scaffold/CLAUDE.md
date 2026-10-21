# [Project Name]

<!-- This file holds THIS project's facts, decisions and exceptions, and nothing else.
     Apogee's general rules (work loop, git, files, tools, code standards) and its tone come from
     the plugin itself (rules/RULES.md and rules/SOUL.md), injected at every session start, and
     update with the plugin. Anything written here overrides them for this project.
     Written by /apogee:init, kept current by /apogee:update-docs; Apogee never rewrites it on
     update. -->

## 1. Project

<!-- One paragraph: what this is, who uses it, what must never break. Details belong in
     docs/apogee/ai-context/spec.md, not here. -->

## 2. Operator Model

<!-- Describe how you and Claude collaborate. Optional but valuable for
     solo / AI-agent-driven workflows.

Example:

- **Role split.** I'm the decision-maker, director, and reviewer. AI agents
  (Claude + sub-agents) write the code. Build effort ≈ zero; cost is
  maintenance, debuggability, and decision overhead.
- **Evaluate by maintenance burden, not build effort.** "Too much code for
  a solo dev" is not a valid critique — pick libraries and architectures on
  technical merit.
- **Boundaries:** always ask before breaking changes, deleting files, and
  architecture decisions worth ≥1 day of rework to undo. -->

## 3. Key Architecture Decisions

<!-- Document settled decisions here so Claude doesn't relitigate them.
     Include brief rationale for each. -->

<!-- Tip: Also list decisions that are SETTLED so Claude doesn't relitigate them.
     Example: "REST over GraphQL — decided, don't suggest changing." -->

<!--
Example:
- **Authentication**: JWT tokens with refresh rotation. Why: stateless, scales horizontally.
- **Database**: PostgreSQL with RLS on all tables. Why: row-level security eliminates auth middleware bugs.
- **State management**: Server-side only. Why: single source of truth, no sync bugs.
-->

## 4. Project Rules

<!-- Rules specific to this project, including deliberate exceptions to Apogee's RULES.md or
     SOUL.md (they win over the plugin's rules on conflict). Leave empty if there are none.

Example:
- Commit only when asked in this repo (overrides the pre-authorized commits).
- Never touch `legacy/`; it is frozen until the migration ADR lands.
- Swift files: PascalCase.
-->

## 5. Testing

<!-- How to run the tests. The agent runs the targeted form on its own work (every feature,
     bugfix and hotfix, and before /apogee:finish); the full suite runs in /apogee:release and in
     CI. List the targeted form first. -->

<!--
Example:
```bash
npx vitest run <path>   # Targeted: tests for what you changed (finish)
npm test                # Full suite (release gate, CI)
```

**When to run which tests:**
| What changed | Run |
|---|---|
| Shared utilities | Unit tests |
| API endpoints | E2E tests |
| Database schema | Integration tests |
| Before deployment | All suites |
-->

## 6. Privacy & Security

<!-- Document non-negotiable security rules for your project. -->

<!--
Example:
- Audio/media NEVER stored — processed in memory, deleted immediately
- No user accounts — anonymous identity via device UUID
- Never log personal data or audio content
- Never reveal system internals (stack traces, DB schemas) in error messages
- Input validation on all external inputs
- RLS enabled on all database tables
-->

## 7. Bilingual Documentation

<!-- Only fill this in if the project ships user-facing docs in more than one
     language. Applies to the project's own docs (README.md, docs/*.md) —
     NEVER to docs/apogee/ (Apogee's own git-excluded AI working memory) and
     NEVER to code: identifiers, comments, and commit messages stay English
     per §1 regardless of this section. -->

<!--
Example:
- **File naming**: one file per language, English is the base name, others
  suffixed with the ISO 639-1 code — `README.md` / `README.ru.md`,
  `docs/setup.md` / `docs/setup.ru.md`.
- **English is canonical.** Every other language file is a translation of it;
  when English content changes, update the paired translation(s) in the same
  commit — a stale translation is a bug, not a follow-up task.
- **Cross-link the pair.** Each file links to its counterpart(s) near the top,
  e.g. `*Read this in: [English](README.md) | [Русский](README.ru.md)*`.
-->
