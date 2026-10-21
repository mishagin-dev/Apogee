# ADR 0009 — Apogee's rules live in the plugin; a project's CLAUDE.md is project-only

**Status:** Accepted · **Date:** 2026-10-21

## Context

Until 3.x, `scaffold/CLAUDE.md` carried two owners in one file: Apogee's general rules (the work
loop, the git wall, the language split, local-only AI tooling, coding standards, the tool table,
the communication style) and the project's own facts (what it is, the operator model,
architecture decisions, the test command, privacy rules). `setup.sh` copies the file once and
never overwrites it; `/apogee:init` and `/apogee:update-docs` then edit it with project facts.

Every release changed the general rules. None of those changes could reach an existing project:
the file was already customized, so updating meant a hand merge in every project. Three of the
3.0.x patches were exactly that kind of rule change (dialogue language twice, commit
pre-authorization), each followed by "replace this line by hand in your projects".

## Decision

1. **The general rules move into the plugin**, split by kind:
   - `plugins/apogee/rules/SOUL.md` — how to be: voice and dialogue language, honesty, restraint.
   - `plugins/apogee/rules/RULES.md` — what to do: the work loop, git, files, tools, code.

   The split keeps the two independently editable: tone can change without touching policy.

2. **The SessionStart hook injects both** as `additionalContext` on every session source
   (`startup`, `resume`, `clear`, `compact`, `fork`); the hook runs again after compaction, so
   the rules are supplied anew. It does so in any directory that has `docs/apogee/` itself or in an
   ancestor (a project set up with Apogee, or one of its
   submodules). The injected text starts with: the project's `CLAUDE.md` overrides these rules
   wherever they disagree.

3. **`scaffold/CLAUDE.md` becomes a project-only template**: Project, Operator Model, Key
   Architecture Decisions, Project Rules (the project's own rules and deliberate exceptions to
   the toolkit's), Testing, Privacy & Security, Bilingual Documentation.

4. **`/apogee:init` and `/apogee:update-docs` write only project content** into `CLAUDE.md`. A rule
   that looks general is reported as a candidate for `RULES.md`, never written anywhere by them;
   `RULES.md` is changed only in the Apogee repository and shipped with a release. The plugin
   copy in a project is a cache that each update replaces.

5. **Migration is one command per existing project**: `/apogee:init --migrate` classifies the old
   general sections line by line, drops what `RULES.md`/`SOUL.md` already say, keeps project lines
   verbatim, and asks before rewriting.

Rejected: an `@import` of a file the hook copies into the project. It keeps the rules inside
`CLAUDE.md`'s loading path, but `CLAUDE.md` is read before the hook runs, so the first session
after an update would see the old copy, and it adds another local file to exclude.

## Consequences

- An update reaches every project at the next session, with no merge and no `sync.sh`.
- The token cost is unchanged: the same rules, injected instead of read from `CLAUDE.md`.
- `GEMINI.md` is not covered (`agy` does not see Claude's hooks); it carries almost no toolkit
  rules and changes rarely.
- The Rules Auditor in `review-work` receives `RULES.md` alongside the project's `CLAUDE.md`.
- 4.0.0 ships this together with ADR 0008; projects from 3.x need the one-time `--migrate`.
