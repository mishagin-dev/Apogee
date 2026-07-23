# Run Plan Command

Drive a beads-recorded plan to completion autonomously: pick the next ready epic, open its
git-flow branch, implement and close every step, run the review→docs pipeline and the project's
test gate, finish the branch into develop, then move to the next epic — repeating with **no
per-micro-decision confirmation** (no "should I start this branch?", no "should I merge?"). The one
hard, non-negotiable exception: this command **never runs `git push`**. A conservative circuit
breaker (default: 3 epics per invocation) stops the loop periodically so you can check in; re-invoke
`/apogee:run-plan` to continue.

**Context from user:** $ARGUMENTS

---

## $ARGUMENTS conventions

One documented use for `$ARGUMENTS`:

- `max-epics: <N>` — override `pipeline.json`'s `run_plan.max_epics_per_invocation` for this
  invocation only (does not edit the config file). `max-epics: 0` means unlimited for this run.
  Example: `/apogee:run-plan max-epics: 1` to watch the very first autonomous epic closely before
  trusting the default cap.

Anything else in `$ARGUMENTS` is free-form context for you to factor into which epic you pick first
(e.g. "prioritize the auth epic") — it does not change any safety behavior below.

---

## Philosophy

This is the autonomous counterpart to the normal work loop (`/apogee:prime` → work, gated by `br` /
git-flow / idea → `/apogee:review-work` → `/apogee:update-docs` → `/apogee:merge`) — it *is* that
loop, run end-to-end by the agent instead of pausing between each stage. It only exists to eliminate
confirmation friction on beads+git-flow projects where a plan has already been approved (in Plan
Mode) and recorded as epics + steps. It does **not** relax any of this repo's hard technical
guardrails: a merge conflict, an unexpected dirty file, a failing test, or a release/hotfix branch
still stop the loop exactly as they would in interactive use. Softening only applies to the
confirmation *prompts* that exist purely to ask "are you sure" on things the plan already answered —
not to correctness checks.

**Design note (why this reads the way it does):** this command's design went through an adversarial
second-opinion review before being built, and the implementation went through a two-reviewer
code-review pass (Bug Hunter + Rules Auditor) afterward. The second-opinion reviewer correctly
rejected a stateful "autonomous mode" marker file (crash-unsafe — see `enforce-git-flow-skill.py`'s
module docstring for why), rejected an autonomous exception to the clean-tree guardrail (a dirty
file at merge time is a signal of a bug, not something to paper over), pushed the new
safety-backstop DENY rule from fail-open to fail-closed specifically for this command's tagged
invocations, and pushed the circuit-breaker default from unlimited to 3. The code review then found
(and the fixes are already in `enforce-git-flow-skill.py`) two high-severity gaps in the first
implementation of that backstop: it could be shadowed entirely by a compound Bash command
(`git flow feature start decoy && git flow feature finish <slug>` let an earlier rule's
unconditional exit skip the finish-side check — fixed by evaluating the backstop before any other
rule can short-circuit), and a slug-less `git flow feature finish` (valid AVH usage — operates on
the checked-out branch) bypassed the check entirely by returning "nothing to verify" instead of
resolving the current branch — fixed with an explicit fallback. All of this is reflected below and
covered by both `enforce-git-flow-skill.py --test` and `plugins/apogee/skills/git-flow/smoke-run-
plan.sh`; don't relitigate any of it without a comparable review.

---

## Pre-flight

1. **Confirm this project is beads + git-flow.** Both `.beads/` and
   `git config --get-regexp '^gitflow\.branch\.'` non-empty are required. Missing either → refuse
   to start and say why (this Apogee repo itself, with beads deliberately inert, will correctly
   refuse here).
2. **Dependency graph must be sane.** Run `br dep cycles --json`. Non-empty → abort before touching
   anything; a broken dependency graph makes `br ready` unreliable, and there is nothing safe to
   automate on top of it.
3. **Read the circuit-breaker config**: `pipeline.json`'s `run_plan.max_epics_per_invocation`
   (default 3; `0` means unlimited — only if the user has explicitly raised it, or passed
   `max-epics: 0` for this invocation via `$ARGUMENTS`) and `run_plan.test_command` (if set, gates
   every epic's finish; `null` skips that gate). A `max-epics:` value in `$ARGUMENTS` overrides the
   config file's value for this invocation only.
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
on a crash), and it is what lets Rule 2 bypass its "another branch is open" ASK and lets the new
open-children DENY apply its stricter fail-closed behavior instead of the ordinary fail-open one.
**Never use this prefix on any other command, and never use it outside of actually running this
loop** — it is not a general-purpose "skip confirmation" switch.

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
   - Implement the step (normal Edit/Write flow — `br-edit-gate`/`br-branch-gate` pass automatically
     since a step is `in_progress` and the branch is correctly linked to its epic).
   - **Commit immediately via the `apogee:git-commit` skill, before moving to the next step.** This
     discipline is exactly what keeps the tree clean at merge time (Step 5's clean-tree guardrail
     has zero autonomous-mode exceptions — see Philosophy — so a dirty tree there means this step
     was skipped somewhere).
   - `br close <stepId> --suggest-next --actor "${BR_ACTOR:-assistant}"` (the `--suggest-next` flag
     directly returns newly-unblocked work).

4. **Epic-level gates — run proactively, before ever calling `/merge`.** This is what satisfies
   `review-docs-gate.sh` without that hook ever needing to fire:
   - Invoke the `apogee:review-work` skill.
   - Invoke the `apogee:update-docs` skill; commit any doc changes via `git-commit`.
   - **If `pipeline.json`'s `run_plan.test_command` is set**, run it now. A failure halts here — the
     branch stays open, uncommitted work (if any) stays as-is, and this is surfaced to the user as a
     hard stop. **Closing br steps is not evidence the code actually works** — this gate exists
     specifically because it isn't.

5. **Finish the branch.** Invoke `/apogee:merge`; when it reaches the Git Flow finish step, the
   underlying command must be tagged: `APOGEE_RUN_PLAN=1 git flow feature|bugfix finish <slug>`.
   Rule 1 (`enforce-git-flow-skill.py`'s release/hotfix ASK) never fires for feature/bugfix finish —
   confirmed by its regex, which only matches `(release|hotfix)`. The new open-children DENY rule
   does apply here, fail-closed for this tagged command: if it can't positively confirm every step
   of this epic is closed, it refuses, and the loop halts with that reason surfaced.

6. **Close the epic**: `br epic close-eligible` (closes epics whose children are all closed —
   no custom logic needed).

7. **Increment the epic counter.** If it reaches `max_epics_per_invocation` (and the cap isn't 0),
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
  `test_command` failure, or a release/hotfix epic (route to `/apogee:release`, which keeps its own
  ASK gate — out of scope for this command).
- **The user interrupts the session.**

On every exit path, print a structured summary before returning control:
- Epics processed, branches opened/merged, steps closed, commits made.
- Any halt reason, verbatim, if the loop stopped on something other than success or the circuit
  breaker.
- **Always**, regardless of how the loop ended: how many commits are now sitting unpushed on
  `develop`, with an explicit "run `git push` when you're ready" line. This command never pushes,
  in any termination path.

---

## Audit trail

Log every major transition as a br comment rather than inventing a bespoke log file: branch opened,
each step claimed/closed, review/docs/test run, branch finished, epic closed —
`br comments add <id> --message "run-plan: ..."`. Inspectable afterward via `br comments list <id>`
or `br show <id> --json`. The first real use of this command on a project should be watched via this
audit trail rather than trusting the end-of-run summary alone.
