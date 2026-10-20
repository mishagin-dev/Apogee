# ADR 0006 — `/apogee:run-plan` autonomy design: stateless tag, fail-closed backstop, no clean-tree exception

**Status:** Accepted · **Date:** 2026-07-23 (recorded as an ADR 2026-10-20; previously an inline
design note in `commands/run-plan.md`)

## Context

`/apogee:run-plan` drives a `br`-recorded plan to completion without per-step confirmation in a
beads + git-flow project. Before it was built, its design went through an adversarial
second-opinion review, and the implementation went through a two-reviewer code review (Bug Hunter +
Rules Auditor). The decisions below came out of those reviews. They were kept as a 70-line note
inside the command file, which made the command read as history rather than instruction; this ADR
moves the record here so the command can stay operational.

## Decisions

1. **The autonomous signal is a literal command-string tag, `APOGEE_RUN_PLAN=1`, not a marker file
   or a session env var.** Hooks are separate processes per tool call, so nothing session-scoped is
   crash-safe: a marker file left behind by an interrupted run would keep later interactive
   commands under autonomous rules. A per-command prefix has nothing to leak and nothing to clean
   up. The tag only ever makes the hook *stricter*; there is nothing it lets the loop skip.

2. **The open-children DENY (Rule 2b in `enforce-git-flow-skill.py`) applies only to tagged
   finishes and fails closed.** Prose rules rely on a human backstop an unattended loop does not
   have: a model drifting over a long run will eventually believe an epic is complete, finish the
   branch, and compound the mistake across epics. If `br` cannot be queried, a tagged finish is
   refused rather than allowed. Untagged (interactive) finishes get no check at all. This is the
   refinement ADR 0005 adopted for its own cut criterion: *is the outcome irreversible, and is a
   human present to catch it.* The draft of ADR 0005 proposed replacing this backstop with a
   self-check inside the loop's prose; the second-opinion reviewer rejected that, and the rule
   survived on that argument.

3. **The clean-tree guardrail in `/apogee:merge` has no autonomous-mode exception.** A dirty file at
   merge time, even one the loop itself touched, means the loop's per-step commit discipline
   already broke somewhere. That is exactly the moment to stop and surface it, not to guess that
   whatever is lingering is safe to ship.

4. **The circuit breaker defaults to 3 epics per invocation**, not unlimited, so a human looks at
   the audit trail (`br comments list <epicId>`) periodically. Raised per invocation via
   `max-epics: <N>` in `$ARGUMENTS`; `0` is unlimited.

5. **`git push` and the release/hotfix lifecycle stay out of scope.** The loop never pushes and
   routes release/hotfix epics to `/apogee:release`. (Superseded in part by ADR 0007, which lets the
   loop push `develop` and work branches while keeping `main` and tags behind a wall.)

## Defects the code review found in the first implementation

Both are fixed in `enforce-git-flow-skill.py` and covered by its `--test` mode and by
`tests/smoke-run-plan.sh`:

- **Compound-command shadowing.** `git flow feature start decoy && git flow feature finish <slug>`
  let an earlier rule's unconditional exit skip the finish-side check. Fixed by evaluating the
  backstop before any other rule can short-circuit, and by never assuming a match is the only
  git-flow operation in the command.
- **Slug-less finish bypass.** `git flow feature finish` with no slug is valid AVH usage (it
  finishes the checked-out branch) and returned "nothing to verify". Fixed with an explicit
  current-branch fallback in `_finish_slug()`.

## Consequences

- `commands/run-plan.md` carries a two-line pointer to this ADR instead of the design note.
- Any change to the tag, the fail-closed behaviour, the clean-tree rule or the breaker default
  needs a review comparable to the one that produced them, and an amendment here.
