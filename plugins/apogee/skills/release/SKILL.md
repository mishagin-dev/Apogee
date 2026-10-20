---
name: release
description: "Prepare a release: decide the version, bump it in lockstep, refresh the CHANGELOG, run the validate gate, commit the prep, then hand the git-flow finish and the push to the operator."
argument-hint: "[<version>|major|minor|patch]"
disable-model-invocation: true
---

# Release Command

Own a project's release lifecycle up to the finish: detect where its version lives, bump it (in
lockstep across every place found), refresh the CHANGELOG, gate on the project's test/validate
command, commit the release prep, write the release notes to a temp file, then **stop and hand
the finish to the operator**. By decision
([ADR 0007](../../../../docs/decisions/0007-production-branch-wall.md)) an agent never merges into
the production branch, never creates or pushes a tag: the `enforce-git-flow-skill` hook refuses
`git flow release|hotfix finish` outright. This command ends by printing the three commands the
operator runs in a terminal.

**Context from user:** $ARGUMENTS

---

## Philosophy

A release keeps a small set of things in lockstep: wherever the version is declared (if
anywhere), the git annotated tag, and the `CHANGELOG.md` `## [x.y.z]` header. Where the version is
declared varies by project — Apogee's own release, for instance, keeps
`plugins/apogee/.claude-plugin/plugin.json` and the `apogee` entry of `.claude-plugin/marketplace.json` in lockstep;
plenty of projects (Go modules, a submodule tracked only by CHANGELOG + a README badge) don't
declare a version anywhere at all and rely on the tag alone. This command detects which case
applies instead of assuming one.

Same rule as `/apogee:finish`: if you're tempted to silently paper over a problem (a failing test gate, an
ambiguous version bump or version source, a dirty tree), STOP and surface it. A release is
semi-destructive once tagged — an easy mistake to avoid, an annoying one to unwind.

The finish and the push are **not** this command's to run. `git flow release|hotfix finish`
merges into `main` and tags; `git push origin main develop --tags` publishes it. Both are reserved
for the operator (ADR 0007), and the hook denies them to an agent, so don't attempt them, don't
ask for permission to run them, and don't look for a workaround (no manual `git merge`, no `git
tag`): prepare everything, print the commands, stop.

---

## $ARGUMENTS conventions

- An explicit version (`/apogee:release 1.9.0`) — skip the suggestion in Step 1, use this
  directly (still confirm with the user before bumping anything).
- A bump keyword (`/apogee:release major` / `minor` / `patch`) — apply to the last tag instead
  of the commit-scan suggestion.
- `hotfix` → not here: a hotfix is a unit of work, opened with `/apogee:start hotfix` and closed with
  `/apogee:finish`, which runs the same preparation from the shared reference.

If `$ARGUMENTS` is empty, run the normal suggestion flow in Step 1.

---

## Pre-flight

1. **Require git-flow.** Run:
   ```bash
   git config --get-regexp '^gitflow\.branch\.'
   ```
   Empty → STOP: this repo isn't git-flow-initialized; offer to run `git flow init -d` via the
   `apogee:git-flow` skill first, then re-invoke this command.

2. **Base.** `gitflow.branch.develop` (fallback `develop`). `hotfix` in `$ARGUMENTS` → STOP and
   point at `/apogee:start hotfix`.

3. **Resume check.** Run `git branch --show-current`.
   - Already on a `release/<slug>` branch → **resume mid-flow**: skip Step 2 (don't re-`start`),
     pick up at Step 3 with `<version>` = the branch's slug
     (`release/1.9.0` → `1.9.0`). Every step below is written to be idempotent for exactly
     this case — re-running this command on a partially-finished release branch must not
     duplicate a CHANGELOG section or create a redundant commit. Version-source detection
     (below) also re-runs on resume — it's read-only and cheap, and its result is needed by
     every later step regardless of how far a prior partial run got.
   - On a `hotfix/<slug>` branch → STOP: finish it with `/apogee:finish`.
   - On `develop`/`main`/anything else → proceed from Step 1 (fresh release).

4. **Clean-tree guardrail** (only when starting fresh, not on resume — a resumed branch may
   legitimately have uncommitted manifest edits from a prior partial run, handled by later
   steps' idempotency). Dirty tree on a fresh start → STOP. Show `git status` + `git diff --stat`,
   offer: (a) commit named files, (b) discard, (c) abort. **Never `git add -A` or `git add .`.**
5. **Version-source detection** — section A of
   [references/prepare-and-hand-over.md](references/prepare-and-hand-over.md). Read-only, re-run on resume.

---

## Step 1: Decide the version

Skip the SemVer-suggestion part of this step entirely on resume (version is already fixed by the
branch name) — but still show the Version-source detection summary below, since the user should
see it even on resume.

1. **Scan commits since the last tag:**
   ```bash
   last=$(git describe --tags --abbrev=0 2>/dev/null)
   git log ${last:+$last..}HEAD --no-merges --format='%s'
   ```
   No tag yet → the whole history is scanned (first release).

2. **Suggest a SemVer bump** from the Conventional Commit subjects:
   - Any subject with `!` after the type/scope, or a `BREAKING CHANGE` footer → **major**.
   - Else any `feat:` subject → **minor**.
   - Else (`fix`, `perf`, `refactor`, `docs`, …) → **patch**.

3. **Resolve the target version:**
   - `$ARGUMENTS` has an explicit version → use it verbatim.
   - `$ARGUMENTS` has a bump keyword (`major`/`minor`/`patch`) → apply that bump to `last`
     instead of the scanned suggestion.
   - Otherwise → use the scanned suggestion.
   - Apply the tag-prefix style resolved in section A(d).

4. **Confirm with the user** before proceeding — this is a deliberate decision, not a
   rubber-stamp. Show:
   - The suggested version, the reasoning (which commit types drove it), and the commit subjects
     considered.
   - What section A detected: which file(s) will be bumped (or "CHANGELOG + git tag only, no
     manifest found"), the tag-prefix style, and the README badge nudge if any.

---

## Step 2: Start the release branch

Skip if resuming (Pre-flight already detected the branch).

Via the **`apogee:git-flow` skill** (bundled with this plugin; if unavailable, run the `git flow` command
directly):
```
git flow release start <version>
```

---

## Steps 3–8: Prepare and hand over

Follow sections B–G of [references/prepare-and-hand-over.md](references/prepare-and-hand-over.md)
with `<type>` = `release`: bump, CHANGELOG, CI gate, prep commits, notes file in `$TMPDIR`, the
three operator commands, then stop. The finish and the push are the operator's (ADR 0007).
