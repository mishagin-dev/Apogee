---
name: review-work
description: "Review a work branch before it merges, as one loop: run the tests of the change, review the whole branch (built-in /code-review for bugs and security, an Apogee rules audit, an intent verdict against what was asked), fix the valid findings, re-run the tests. Called by /apogee:finish with the branch base; also on the user's request. Not for prose (README, docs): /apogee:readme has its own check."
argument-hint: "[base branch, default: develop (main on a hotfix branch)]"
user-invocable: true
---

# Review Work

One loop that leaves the branch reviewed, fixed and tested:

```
1. tests of the change          what is already broken
2. review the whole branch      bugs and security, rules, intent
3. fix                          valid high/medium findings, committed on the branch
4. tests of the change again    the fixes broke nothing (at most two repair rounds)
5. report
```

You are the judge throughout. Reviewers have fresh eyes and no conversation context; you have the
context and the authority to reject. The full test suite is not part of this loop: it runs in the
release preparation and in CI.

**Context from user:** $ARGUMENTS

---

## Step 0: Scope

- **Base.** `$ARGUMENTS` names it; otherwise the base of the current branch type: `main` (the
  production branch) on `hotfix/*`, `gitflow.branch.develop` (fallback `develop`) on anything else.
- **Range.** Everything the branch adds over its base, committed or not:

  ```bash
  git diff --stat <base>...HEAD; git diff <base>...HEAD     # committed on the branch
  git diff --stat HEAD;          git diff HEAD              # not committed yet
  ```

  Both empty → nothing to review; say so and stop.
- **Kind.** Changed files that are all prose or config (`*.md`, `docs/**`, `*.json`/`*.yml`/
  `*.toml` with no code next to them) → **prose branch**: skip `/code-review` and the tests (steps
  1, 2a, 4); run the rules audit and the intent verdict only.

---

## Step 1: Tests of the change (before)

Run the tests that cover what the branch changed, with the targeted form the project's `CLAUDE.md`
Testing section documents (HTML comments stripped); without one, the test files for the changed
code via the project's runner.

- **Failures are findings**, ahead of everything the reviewers produce.
- **Pre-existing failures** are not this branch's. When a test fails and checking is cheap, run the
  same tests on the base in a throwaway worktree (`git worktree add <tmp> <base>`, removed after);
  otherwise state "fails, origin unverified". Failures that also fail on the base are reported
  separately and not fixed here.
- **No tests cover the changed code** → a TESTS finding; continue.

---

## Step 2: Review the whole branch

### 2a. Bugs and security via `/code-review`

Invoke the built-in skill through the Skill tool: `skill: "code-review"` with args
`<effort> <base>...HEAD`, effort sized to the change: `low` under 50 changed lines, `medium`
under 400, `high` above. Always pass the explicit range: without a target `/code-review` reviews
only the commits ahead of the branch's upstream, and `/apogee:start` publishes the branch, so
already-pushed work would be left out. A range covers commits only, so commit pending changes
(step 0 lists them) through `apogee:git-commit` before this step.

`/code-review` runs as a background subagent and its findings arrive as a later notification.
Start it, run 2b and 2c while it works, and do not start step 3 before its findings are in. Take
its verified findings as the bug and security list.

If the Skill tool reports that `code-review` is not available in this client, fall back to the Bug
Hunter procedure in [references/legacy-parallel-reviewers.md](references/legacy-parallel-reviewers.md)
on the same range, and say so in the report.

### 2b. Rules audit

Spawn **one** read-only agent (`subagent_type: "Explore"`), named Rules Auditor, with the branch
diff, the step 1 test output, the contents of `${CLAUDE_PLUGIN_ROOT}/rules/RULES.md` pasted in (a
subagent cannot resolve the plugin path), and this brief:

```
You are a Rules Auditor. The toolkit rules (RULES.md) are pasted below; read CLAUDE.md for this
project's own rules, decisions and exceptions (CLAUDE.md wins on conflict), then check ONLY the diff
against these categories. Do not look for general bugs; another pass does that.

COMPLIANCE — violations of RULES.md and of the rules and decisions in CLAUDE.md. Cite the rule.
SIMPLICITY — a new abstraction, layer, option or flag with a single user or none; a generic
solution built for one case; speculative extensibility. Cite the line.
TESTS — new behaviour without tests; tests asserting exact strings where structure would do.
LANGUAGE — identifiers, comments and docs in English; no narrating comments.
AI TOOLING — nothing under .claude/, docs/apogee/, .beads/, .scratch/, or CLAUDE.md/GEMINI.md/AGENTS.md is
staged or referenced as a deliverable (these are local-only by decision).

Any claim about a third-party library or API must be checked against its current documentation via
Context7 (resolve-library-id, then query-docs) before you report it. Tag each such finding
[verified] or [unverified]; unverified claims are discarded by the judge.

For each finding: - [high|medium|low] `file:line` — what. **Rule:** which rule. [verified|unverified|n/a]
If a category has nothing, write "No issues found." Do not invent issues to seem thorough.
```

### 2c. Intent verdict

Compare what the branch does with what was asked:

- In a beads project: `br show <epicId> --json` for the epic linked to this branch
  (`external_ref`) and its steps.
- Otherwise: the Current Work section of `docs/apogee/ai-context/progress.md`, or the user's
  request in this session.

State **MATCHES**, **PARTIAL** (name what is missing), or **DRIFTED** (name what was done instead,
and whether it was asked for). Drift is a finding even with zero bugs.

---

## Step 3: Judge and fix

Combine the step 1 failures, the `/code-review` findings, the Rules Auditor's, and the verdict:

| Verdict | When | Action |
|---|---|---|
| Valid (high/medium) | The reasoning holds and you agree | Fix it now, on the branch |
| Valid (low) | Real but minor | Report; fix only if asked |
| False positive | The reviewer lacked context, or the behaviour is intentional | Reject with one line |
| Unverified | A library/API claim tagged `[unverified]` | Discard |

Each fix is committed through `apogee:git-commit` (`fix(<scope>): …`), one commit per finding or
per tight group. A PARTIAL verdict is fixed only when the missing part is small and clearly asked
for; otherwise it goes to the report for the user to decide.

---

## Step 4: Tests of the change (after)

Only when step 3 changed code. Re-run the step 1 tests, plus tests for whatever the fixes touched.

- Green → done.
- Red → repair and re-run, at most **two rounds**. Still red after the second → STOP: leave the
  branch as it is, report the failing tests and what was tried. Do not loop further, and do not
  re-run the review: the fixes are verified by tests, not by another review pass.

---

## Step 5: Report

```
## Review: <branch> vs <base>

Range: X files, Y lines. Intent: MATCHES | PARTIAL (…) | DRIFTED (…)
Tests of the change: before N passed / M failed → after N passed (or: no tests cover the change)

| # | Source | Verdict | Category | File | Issue | Action |
|---|--------|---------|----------|------|-------|--------|
| 1 | tests | Fixed | BUG | src/x.ts:42 | Null check missing | fix(x): … |
| 2 | rules | Rejected | SIMPLICITY | src/y.ts:10 | Intentional extension point (ADR 3) | — |
```

Pre-existing failures, deferred low findings and a large-fix warning (fixes over ~100 lines: "a
second review may be worth it") go below the table. No findings at all → one line.

The loop ends on the last commit it made; `/apogee:finish` uses that commit to know the review
and the tests are current.

## Rules

1. **Never skip the review**, and never replace it with "looks fine" from your own reading.
2. **Never accept findings blindly.** Reviewers hallucinate paths and misread intent.
3. **Reviewers are read-only.** You make the fixes, on the branch, committed via `git-commit`.
4. **Tests of the change, not the full suite.** The full suite is the release's and CI's.
5. **Two repair rounds, then stop.** A loop that does not converge is a finding for the user.
