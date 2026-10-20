---
description: "Autonomously drive a br-recorded plan epic by epic in a beads + git-flow project; pushes develop, never main or tags."
argument-hint: "[max-epics: <N>] [notes]"
---

# Run Plan Command

Drive a beads-recorded plan to completion autonomously: pick the next ready epic, open its
git-flow branch, implement and close every step, run the review→docs pipeline and the project's
test gate, finish the branch into develop, then move to the next epic — repeating with **no
per-micro-decision confirmation** (no "should I start this branch?", no "should I merge?"). The one
hard, non-negotiable exception: this command **never touches `main` or tags** -- it pushes
`develop` and work branches (ADR 0007), and the hook refuses anything beyond that. A conservative circuit
breaker (default: 3 epics per invocation) stops the loop periodically so you can check in; re-invoke
`/apogee:run-plan` to continue.

**Context from user:** $ARGUMENTS

---

## $ARGUMENTS conventions

One documented use for `$ARGUMENTS`:

- `max-epics: <N>` — the circuit-breaker cap for this invocation. Default 3; `max-epics: 0`
  means unlimited for this run. Example: `/apogee:run-plan max-epics: 1` to watch the very first
  autonomous epic closely before trusting the default cap.

Anything else in `$ARGUMENTS` is free-form context for you to factor into which epic you pick first
(e.g. "prioritize the auth epic") — it does not change any safety behavior below.

---

## Philosophy

This is the autonomous counterpart to the normal work loop (`/apogee:prime` → work, tracked in
`br` on a git-flow branch → `/apogee:review-work` → `/apogee:update-docs` → `/apogee:merge`) — it *is* that
loop, run end-to-end by the agent instead of pausing between each stage. It's also the intended
continuation of a Plan Mode approval in a git-flow project: `plugins/apogee/hooks/br/br-capture-
gate.py` (fires on `ExitPlanMode`) captures the approved plan into `br` as an epic + steps, then
hands off here instead of telling the agent to open the branch and implement by hand — approving
the plan already is the go-ahead to execute it, so this command should be the default next action,
not a separately-requested one. It only exists to eliminate confirmation friction on beads+git-flow
projects where a plan has already been approved and recorded as epics + steps. It does **not**
relax any of this repo's hard technical guardrails: a merge conflict, an unexpected dirty file, a
failing test, or a release/hotfix branch
still stop the loop exactly as they would in interactive use. Softening only applies to the
confirmation *prompts* that exist purely to ask "are you sure" on things the plan already answered —
not to correctness checks.

**This loop is now the only place with a hard backstop.** [ADR 0005](../../../docs/decisions/0005-enforcement-safety-only.md)
stripped Apogee's enforcement layer down to two safety gates, on the grounds that a recoverable
mistake made in front of a human does not need a wall. That reasoning does not extend here: an
unattended loop has no human to notice tracker drift, so the open-epic-steps DENY was kept —
narrowed to *only* the commands this command tags, and fail-closed. Every other rule the loop
follows (commit through the skill, one epic per branch) is prose you must actually follow; the
production-branch wall (push to `main`, tags, release finish) is the other thing that will stop you.

**Design record:** the reasoning behind the stateless command tag, the fail-closed backstop, the
no-exception clean-tree rule and the circuit-breaker default is recorded in
[ADR 0006](../../../docs/decisions/0006-run-plan-autonomy-design.md), together with the two
high-severity gaps the first implementation had. Don't relitigate any of it without a comparable
review; the regression coverage lives in `enforce-git-flow-skill.py --test` and
`tests/smoke-run-plan.sh`.

---

## Pre-flight

1. **Confirm this project is beads + git-flow.** Both `.beads/` and
   `git config --get-regexp '^gitflow\.branch\.'` non-empty are required. Missing either → refuse
   to start and say why (this Apogee repo itself, with beads deliberately inert, will correctly
   refuse here).
2. **Dependency graph must be sane.** Run `br dep cycles --json`. Non-empty → abort before touching
   anything; a broken dependency graph makes `br ready` unreliable, and there is nothing safe to
   automate on top of it.
3. **Resolve the circuit breaker and the test gate.** `max_epics` is the `max-epics:` value from
   `$ARGUMENTS`, default 3 (`0` = unlimited). The test gate is the project's full-suite command
   documented in the Testing section of its `CLAUDE.md` -- strip HTML comments before scanning,
   exactly as `/apogee:release` Step 5 does, because the scaffold ships that section as
   commented-out boilerplate. No command documented → there is no test gate; state that in the
   pre-flight summary rather than silently skipping it.
4. Initialize an in-context epic counter at 0 (tracked across this session's turns — no file
   needed, the whole loop runs within one continuous session).

---

## The autonomous tag

Every `git flow feature|bugfix start` and `git flow feature|bugfix finish` command this loop issues
**must** be prefixed with the literal string `APOGEE_RUN_PLAN=1`, e.g.:

```bash
APOGEE_RUN_PLAN=1 git flow feature start <epic-slug>
APOGEE_RUN_PLAN=1 git flow feature finish <epic-slug>
```

`enforce-git-flow-skill.py` checks for this literal prefix on the command string — it is a
stateless, per-command signal (no marker file, nothing to leak past this loop, nothing to clean up
on a crash), and it is the *only* thing that arms the open-children DENY: an untagged
`git flow feature|bugfix finish` is not checked at all.

The tag makes the hook **stricter**, never more permissive — there is nothing it lets you skip.
Tagging a command you are not issuing from this loop only exposes it to a fail-closed check, so
never use it outside an actual run.

---

## Main loop

Repeat until termination (see below). Each iteration:

1. **Pick the next epic.** `br ready --json` filtered to `type == epic` (check whether `br ready`
   takes a native `--type` filter; otherwise filter the JSON client-side). Prefer `br scheduler
   --json` if its ranking usefully covers epics, not just leaf issues — verify this before relying
   on it as the default; fall back to `br ready`'s own ordering otherwise. No ready epic → the loop
   is done (success termination).

2. **Open or resume the epic's branch.** If the epic's `external_ref` is already set and that
   branch exists locally, check it out. Otherwise:
   ```bash
   APOGEE_RUN_PLAN=1 git flow feature start <epic-slug>   # or `bugfix` for a bug-labeled epic
   br update <epicId> --external-ref <branch> --actor "${BR_ACTOR:-assistant}"
   ```
   Log it: `br comments add <epicId> --message "run-plan: opened branch <branch>"`.

3. **Drain the epic's steps.** Loop:
   - `br ready --json` filtered to `parent == epicId`. None left → break to step 4.
   - `br update <stepId> --claim --actor "${BR_ACTOR:-assistant}"`.
   - Implement the step (normal Edit/Write flow — nothing gates edits since ADR 0005; keeping the
     step `in_progress` and the branch linked to its epic is now discipline, and the finish-time
     DENY in step 5 is what catches it if you let that slip).
   - **Commit immediately via the `apogee:git-commit` skill, before moving to the next step.** This
     discipline is exactly what keeps the tree clean at merge time (Step 5's clean-tree guardrail
     has zero autonomous-mode exceptions — see Philosophy — so a dirty tree there means this step
     was skipped somewhere).
   - `br close <stepId> --suggest-next --actor "${BR_ACTOR:-assistant}"` (the `--suggest-next` flag
     directly returns newly-unblocked work).

4. **Epic-level checks — run proactively, before ever calling `/merge`.** No hook enforces this
   order any more (the review→docs Stop gate is gone), which makes running them here the only thing
   that keeps an unattended run honest:
   - Invoke the `apogee:review-work` skill.
   - Invoke the `apogee:update-docs` skill; commit any doc changes via `git-commit`.
   - Invoke `apogee:public-docs update`; it refreshes the human-facing docs whose `sources:` overlap
     the epic's changed files (a one-line no-op when the project has none) and commits them.
   - **If a test command was resolved in Pre-flight 3**, run it now. A failure halts here — the
     branch stays open, uncommitted work (if any) stays as-is, and this is surfaced to the user as a
     hard stop. **Closing br steps is not evidence the code actually works** — this check exists
     specifically because it isn't.

5. **Finish the branch.** Invoke `/apogee:merge`; when it reaches the Git Flow finish step, the
   underlying command must be tagged: `APOGEE_RUN_PLAN=1 git flow feature|bugfix finish <slug>`.
   Rule 1 (`enforce-git-flow-skill.py`'s release/hotfix DENY) never fires for feature/bugfix finish —
   confirmed by its regex, which only matches `(release|hotfix)`. The open-children DENY does apply
   here, fail-closed for this tagged command: if it can't positively confirm every step of this epic
   is closed, it refuses, and the loop halts with that reason surfaced.

6. **Publish develop.** If the repo has a remote (`git remote` non-empty): `git push origin develop`.
   In a superproject, push each submodule's work branch *before* the superproject (the git-flow
   skill's submodule rule), so no pushed commit references a submodule commit the remote lacks.
   Never `main`, never tags; the hook denies both, and that is by design, not a bug to route around.
   Log it: `br comments add <epicId> --message "run-plan: pushed develop"`.

7. **Close the epic**: `br epic close-eligible` (closes epics whose children are all closed —
   no custom logic needed).

8. **Increment the epic counter.** If it reaches `max_epics_per_invocation` (and the cap isn't 0),
   stop here (circuit-breaker termination) rather than continuing to the next epic.

---

## Termination

- **Success** — no ready epic remains.
- **Circuit breaker** — the epic cap was reached. Re-invoking `/apogee:run-plan` continues from
  wherever `br ready` picks back up.
- **`br dep cycles` becomes non-empty mid-run** — abort immediately; this is a safety check, not a
  softenable confirmation.
- **A genuine hard-stop fires**, exactly as in interactive use: a merge conflict, worktree+gitflow
  being unsupported, ANY dirty file at merge time (no exceptions — see Philosophy), a
  test-gate failure, or a release/hotfix epic (route to `/apogee:release`; the finish itself is
  the operator's — out of scope for this command).
- **The user interrupts the session.**

On every exit path, print a structured summary before returning control:
- Epics processed, branches opened/merged, steps closed, commits made.
- Any halt reason, verbatim, if the loop stopped on something other than success or the circuit
  breaker.
- **Always**, regardless of how the loop ended: whether `develop` is pushed (and if not, why --
  no remote, or a halt before step 6), and the reminder that releasing (`/apogee:release`, then
  the finish and push of `main` by the operator) is a separate, manual act.

---

## Audit trail

Log every major transition as a br comment rather than inventing a bespoke log file: branch opened,
each step claimed/closed, review/docs/test run, branch finished, epic closed —
`br comments add <id> --message "run-plan: ..."`. Inspectable afterward via `br comments list <id>`
or `br show <id> --json`. The first real use of this command on a project should be watched via this
audit trail rather than trusting the end-of-run summary alone.
