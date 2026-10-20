# ADR 0007 — Move the wall from "push" to "main": agents push develop and work branches, never the production branch or tags

**Status:** Accepted · **Date:** 2026-10-20

## Context

Until now the toolkit's git posture was "never `git push`", stated as prose in
`scaffold/CLAUDE.md` and in `/apogee:run-plan`, plus an ASK on `git flow release|hotfix finish`.
That blocked the one step that separates "autonomous" from "almost autonomous": a finished
feature or bugfix branch, merged into `develop` by git-flow, still sat unpushed until the operator
pushed by hand. In the operator's own words, the real pain in daily work is that the agent cannot
push and merge feature, bugfix and develop branches, so full autonomy never materialises.

The operator's actual requirement is narrower than "never push": **the agent must not be able to
release**. Nothing may reach `main`, no tag may be created or pushed, by an agent. Everything
below that line can be autonomous.

ADR 0005 reduced enforcement to outcomes that are irreversible and unattended. Pushing shared
history is irreversible; a release is the one git action the operator wants to keep in their own
hands even when present. This ADR therefore adds blocking rules, which deserves an explicit
justification: the new wall *enables* more autonomy than it removes. It replaces a broad prose
prohibition (no push at all) with a narrow enforced one (no `main`, no tags), and the broad
prohibition was the thing holding autonomy back.

## Decision

1. **Rule 3 in `enforce-git-flow-skill.py`: DENY anything that publishes or rewrites the
   production branch or a tag.** `git push` whose destination resolves to the production branch
   in any spelling (`main`, `HEAD:main`, `feature/x:main`, `refs/heads/main`, `:main`,
   `--delete main`, a bare `git push` while `main` is checked out); any push of tags (`--tags`,
   `--follow-tags`, `refs/tags/...`, a refspec naming an existing tag); `--all`, `--mirror`, any
   force push; `git merge` while the production branch is checked out, including
   `git checkout main && git merge ...` in one command; `git tag <name>` creation.
   The production branch is `gitflow.branch.master`, falling back to an existing `main` or
   `master`. **The rule applies in any git repo with such a branch, not only git-flow ones**: a
   submodule without git-flow config is still a repository with a `main`. This is the one
   deliberate exception to "every hook self-gates on git-flow config", justified by the same
   irreversibility that justifies the rule.

2. **Rule 1 changes from ASK to DENY.** `git flow release|hotfix finish` merges into the
   production branch and creates the tag; by decision the operator runs it in a terminal.
   `/apogee:release` keeps everything up to that point (version decision, lockstep bump,
   CHANGELOG, validate gate, release-prep commits) and ends by printing the exact `git flow ...
   finish -m "<v>" <v>` and `git push origin main develop --tags` commands.

3. **Everything below the wall is pre-authorized.** The scaffold `CLAUDE.md` says so in one
   place: committing finished work on a `feature/`/`bugfix/` branch through `apogee:git-commit`
   needs no question; after `git flow feature|bugfix finish`, push `develop`; push and delete work
   branches freely. `/apogee:run-plan` pushes `develop` after each finished epic when a remote
   exists. `/apogee:merge` does the same after an interactive finish.

4. **Defense in depth in `settings.local.json`.** `setup.sh` adds deny rules for the obvious
   spellings (`git push origin main`, `git push --tags`, `--all`, `--mirror`) and allow rules for
   the sanctioned forms (`git push origin develop`, `git push -u origin feature/...`,
   `git push origin --delete feature/...`), so sanctioned pushes never prompt and the common
   unsanctioned ones are refused by Claude Code itself even if the hook fails open. Prefix rules
   cannot parse refspecs, which is why the decision lives in the hook.

5. **Submodules.** In a superproject the work branch of a submodule is pushed *before* the
   superproject's branch, so the superproject never references a commit the remote does not
   have. Recorded in the git-flow skill; Rule 3 judges the repo a command targets via
   `effective_repo()`, so a push inside a submodule is checked against that submodule's `main`.

6. **A remote backstop is recommended but cannot distinguish the agent from the operator.** A
   hosting ruleset that blocks force pushes and deletions on `main` and protects tags is cheap
   and worth having. "Require a pull request" is not recommended: it breaks `git flow release
   finish`, which merges locally. The operator and the agent share credentials, so the remote
   cannot tell them apart; the local wall is the one that makes the distinction.

## Consequences

- Blocking hooks remain two scripts; rules go from three to four. `docs/HOOKS.md` lists them.
- The scaffold's "never `git push`" is gone, replaced by "never `main`, never tags". The
  "Always ask before: git commits" line is gone too; it was one of five overlapping
  formulations that the agent collapsed into "commits are forbidden here".
- `/apogee:release` no longer runs the finish. The ASK gate it relied on is now a DENY, so the
  command stops one step earlier and hands over two commands.
- `tests/smoke-run-plan.sh` expects a DENY (not an ASK) on `release finish`, and gains push cases.
- ADR 0006 §5 ("the loop never pushes") is superseded in part: the loop pushes `develop`.

## Revisit triggers

A sanctioned push refused by Rule 3 (a false positive on a refspec spelling) is fixed by
extending the parser and its tests, not by loosening the rule. Reopen the decision only if the
operator wants agents to release.
