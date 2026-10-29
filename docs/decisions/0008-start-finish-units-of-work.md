# ADR 0008 — Every unit of work opens with `/apogee:start` and closes with `/apogee:finish`

**Status:** Accepted · **Date:** 2026-10-20

## Context

Until 3.1, opening a branch was the agent's own improvisation (the `git-flow` skill's command
map), closing it was `/apogee:merge`, a hotfix was a mode of `/apogee:release`, and research had no
machinery at all: findings lived in the chat and were lost with it. Each path applied the
branch rules (base, naming, the `br` link, no work on `develop` or `main`) differently, or not at
all. In practice changes landed on `develop` and had to be moved onto a branch after the fact.

`/apogee:merge` also had a latent conflict with ADR 0007: its "plain repo" mode ran
`git checkout main && git merge`, which the production-branch wall now denies.

## Decision

1. **Two entry points for all work.** `/apogee:start <type> <slug>` opens a unit of work,
   `/apogee:finish` closes it; the type is one of four:

   | Type | start | finish |
   |---|---|---|
   | `feature`, `bugfix` | `git flow <type> start` off a fresh `develop`, uncommitted changes carried along, branch published, `br` epic linked or created | review, `update-docs`, `public-docs update`, clean tree, test gate, `git flow <type> finish`, push `develop`, `br epic close-eligible` |
   | `hotfix` | `git flow hotfix start <version>` off `main` (version = last tag +patch unless given), published | review, then the shared release preparation; prints the operator's finish/push/publish commands and stops |
   | `research` | no branch: `docs/apogee/research/<date>-<slug>.md` with `status: open`, an index line, a `br` issue labelled `research` | conclusion and sources present, `status: done`, lasting facts promoted to `domain/` or `CLAUDE.md`, issue closed, follow-up `start` proposed |

   `finish` detects the type from the current branch (or the open research note); it needs no
   stored state.

2. **Research has no git branch.** AVH git-flow has no custom branch types, and the output lands
   in `docs/apogee/`, which is local-only (ADR 0007's companion decision on AI tooling), so a
   branch would carry nothing. The machinery is the note, the index and the tracker.

3. **Releases stay a separate entry point.** A release is a cut of `develop`, not a unit of work:
   `/apogee:release` decides the version and runs the same preparation the hotfix finish runs,
   from one shared reference (`skills/release/references/prepare-and-hand-over.md`), so the logic
   exists once.

4. **`git-flow` and `git-commit` stay as the lower layer.** `git-commit` is used on every commit
   between `start` and `finish`; the `git-flow` skill is the command reference those entry points
   read. Raw `git flow … start|finish` is not called directly.

5. **Guidance, not a gate.** The rule is written in the scaffold `CLAUDE.md` and referenced from
   every neighbouring skill (`run-plan`, `plan-feature`, `git-flow`, the unfinished-branch nudge).
   No hook enforces it: none of the bypasses is irreversible (ADR 0005). If agents are seen
   bypassing it, a context nudge on raw `git flow` commands is the next step, not a DENY.

6. **`/apogee:merge` becomes a deprecated alias** of `/apogee:finish` for one release, then goes.
   Its plain-repo mode is replaced by "push the branch and hand the merge to the operator".

## Consequences

- 4.0.0: the `merge` name, `/apogee:release hotfix`, and the plain-repo merge are breaking changes.
- `/apogee:run-plan` opens each epic with `start` and closes it with `finish`; the
  `APOGEE_RUN_PLAN=1` tag moves with the finish command and keeps its fail-closed check (ADR 0006).
- `setup.sh` allows pushing `hotfix/*` branches without a prompt.

## Amendment (2026-10-29) — the `merge` alias stays until the next major release

Decision 6 said the `/apogee:merge` alias lasts one release. It was not removed in 4.1.x; it now
stays until the next major release (5.0.0), where its removal is a breaking change like the
4.0.0 rename.
