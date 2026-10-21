---
name: review-work
description: Review uncommitted code changes before they merge. Delegates bug and security hunting to Claude Code's built-in /code-review, then runs an Apogee rules audit (CLAUDE.md compliance, test coverage, language, no AI-tooling files staged) and an intent verdict against what was actually asked (the br epic/step, progress.md, or the request). Use after completing substantial implementation work, before /apogee:finish, and inside /apogee:run-plan.
user-invocable: true
---

# Review Work

Three passes, each with a different question:

1. **Is it correct?** Bugs and security: delegated to the built-in `code-review` skill.
2. **Does it follow the rules?** A read-only Rules Auditor agent against the project's `CLAUDE.md`
   and Apogee's `RULES.md`.
3. **Is it what was asked?** An intent verdict against the recorded plan.

You are the judge of all three. Reviewers have fresh eyes and no conversation context; you have the
context and the authority to reject.

## Step 1: Capture the scope

```bash
git diff --stat HEAD
git diff HEAD
```

Nothing changed → say so and stop. If the project's `CLAUDE.md` documents a test command (its
Testing section, HTML comments stripped) and source files changed, run the targeted tests now;
failures are the first finding, ahead of everything below.

## Step 2: Bugs and security via `/code-review`

Invoke the built-in skill through the Skill tool: `skill: "code-review"`, with an effort level
sized to the diff (`low` under 50 changed lines, `medium` under 400, `high` above). It reviews the
working-tree diff by default and reports verified findings; take those as the bug/security list.

If the Skill tool reports that `code-review` is not available in this client, fall back to the
Bug Hunter procedure in [references/legacy-parallel-reviewers.md](references/legacy-parallel-reviewers.md)
and say so in the report.

## Step 3: Rules audit

Spawn **one** read-only agent (`subagent_type: "Explore"`), named Rules Auditor, with the full diff,
the test output, the contents of `${CLAUDE_PLUGIN_ROOT}/rules/RULES.md` pasted in (a subagent cannot
resolve the plugin path), and this brief:

```
You are a Rules Auditor. The toolkit rules (RULES.md) are pasted below; read CLAUDE.md for this
project's own rules, decisions and exceptions (CLAUDE.md wins on conflict), then check
ONLY the diff against these categories. Do not look for general bugs; another pass does that.

COMPLIANCE — violations of RULES.md and of the rules and decisions in CLAUDE.md (architecture decisions,
conventions, constraints). Cite the rule.
TESTS — do the changes touch shared modules or critical paths? If so, do corresponding tests exist,
and are assertions structural rather than exact-string?
LANGUAGE — identifiers, comments and docs in English; no narrating comments.
AI TOOLING — nothing under .claude/, docs/apogee/, .beads/, or CLAUDE.md/GEMINI.md/AGENTS.md is
staged or referenced as a deliverable (these are local-only by decision).

Any claim about a third-party library or API must be checked against its current documentation via
Context7 (resolve-library-id, then query-docs) before you report it. Tag each such finding
[verified] or [unverified]; unverified claims are discarded by the judge.

For each finding: - [high|medium|low] `file:line` — what. **Rule:** which rule. [verified|unverified|n/a]
If a category has nothing, write "No issues found." Do not invent issues to seem thorough.
```

## Step 4: Intent verdict

Compare what the diff does with what was asked:

- In a beads project: `br show <stepId> --json` (and the parent epic) for the step being
  implemented.
- Otherwise: the Current Work section of `docs/apogee/ai-context/progress.md`, or the user's request
  in this session.

State one of: **MATCHES**, **PARTIAL** (name what is missing), **DRIFTED** (name what was done
instead and whether it was asked for). Drift is a finding in its own right, even with zero bugs,
because it is the failure no reviewer of the diff alone can see.

## Step 5: Judge and act

Combine `/code-review`'s findings, the Rules Auditor's, and the intent verdict. For each finding:

| Verdict | When | Action |
|---|---|---|
| Valid (high/medium) | The reasoning is sound and you agree | Fix it now |
| Valid (low) | Real but minor | Note it to the user; fix only if asked |
| False positive | The reviewer lacked context, or the behaviour is intentional | Reject with one line |
| Unverified | A library/API claim tagged `[unverified]` | Discard |

Present:

```
## Code Review Results

Reviewed X files, Y lines changed. Intent: MATCHES | PARTIAL (…) | DRIFTED (…)

| # | Source | Verdict | Category | File | Issue | Action |
|---|--------|---------|----------|------|-------|--------|
| 1 | code-review | Fixed | BUG | file.ts:42 | Null check missing | Fixed |
| 2 | rules | Rejected | COMPLIANCE | config.ts:10 | Not a violation | False positive |
```

No findings at all → one line, move on.

## Rules

1. **Never skip the review**, and never replace it with "looks fine" from your own reading.
2. **Never accept findings blindly.** Reviewers hallucinate paths and misread intent.
3. **Reviewers are read-only.** You make the fixes, on the work branch, committed via `git-commit`.
4. **Test output is the first finding** when tests fail.
5. **Context7 for API claims.** An unverified claim about a library is not a finding.
