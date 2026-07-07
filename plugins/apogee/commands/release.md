# Release Command

Own the Apogee release lifecycle end to end: decide the version, bump it in lockstep across
both manifests, refresh the CHANGELOG, gate on `validate.sh`, commit the release prep, then
stop and surface the exact `git flow release|hotfix finish` for the user to run. Finishing and
pushing stay explicit user actions — this command never runs them itself.

**Context from user:** $ARGUMENTS

---

## Philosophy

Apogee's version lives in **four places that must stay in lockstep**: `plugin.json`
(`version`), `marketplace.json` (`plugins[0].version`), the git annotated tag, and the
`CHANGELOG.md` `## [x.y.z]` header. Every doc historically told you to bump only `plugin.json`
— `marketplace.json` drifted to being bumped by hand. This command's job is to make the
lockstep automatic instead of remembered.

Same rule as `/merge`: if you're tempted to silently paper over a problem (a failing
`validate.sh`, an ambiguous version bump, a dirty tree), STOP and surface it. A release is
semi-destructive once tagged — an easy mistake to avoid, an annoying one to unwind.

`release finish`/`hotfix finish` and `git push` run **only on explicit user request** (the
`enforce-git-flow-skill` hook already ASKs on `release finish`; push is manual after review
per this repo's `CLAUDE.md`). This command prepares everything up to that point and then stops.

---

## Self-guard (Apogee-only)

This command releases **Apogee itself** — it hardcodes `plugin.json` + `marketplace.json` +
`scripts/validate.sh`. It is not generic release tooling.

```bash
test -f plugins/apogee/.claude-plugin/plugin.json
```

If that file is absent (i.e. this isn't a checkout of the Apogee repo) → STOP: "This command
releases the Apogee toolkit itself; it doesn't apply here."

---

## $ARGUMENTS conventions

- An explicit version (`/apogee:release 1.9.0`) — skip the suggestion in Step 1, use this
  directly (still confirm with the user before bumping anything).
- A bump keyword (`/apogee:release major` / `minor` / `patch`) — apply to the last tag instead
  of the commit-scan suggestion.
- `hotfix` (`/apogee:release hotfix` or `/apogee:release hotfix 1.8.2`) — release off `main`
  instead of `develop`, via `git flow hotfix start`/`finish` instead of `release`.

If `$ARGUMENTS` is empty, run the normal suggestion flow in Step 1.

---

## Pre-flight

1. **Require git-flow.** Run:
   ```bash
   git config --get-regexp '^gitflow\.branch\.'
   ```
   Empty → STOP: this repo isn't git-flow-initialized; offer to run `git flow init -d` via the
   `apogee:git-flow` skill first, then re-invoke this command.

2. **Determine mode + base.** Default mode is `release` off `gitflow.branch.develop` (fallback
   `develop`); `hotfix` in `$ARGUMENTS` switches to `hotfix` off `gitflow.branch.master`
   (fallback `main`).

3. **Resume check.** Run `git branch --show-current`.
   - Already on a `release/<slug>` or `hotfix/<slug>` branch → **resume mid-flow**: skip Step 2
     (don't re-`start`), pick up at Step 3 with `<version>` = the branch's slug
     (`release/1.9.0` → `1.9.0`). Every step below is written to be idempotent for exactly
     this case — re-running this command on a partially-finished release branch must not
     duplicate a CHANGELOG section or create a redundant commit.
   - On `develop`/`main`/anything else → proceed from Step 1 (fresh release).

4. **Clean-tree guardrail** (only when starting fresh, not on resume — a resumed branch may
   legitimately have uncommitted manifest edits from a prior partial run, handled by later
   steps' idempotency). Dirty tree on a fresh start → STOP. Show `git status` + `git diff --stat`,
   offer: (a) commit named files, (b) discard, (c) abort. **Never `git add -A` or `git add .`.**

---

## Step 1: Decide the version

Skip this step entirely on resume (version is already fixed by the branch name).

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
   - `hotfix` mode → always **patch**, regardless of commit types (hotfixes are bugfixes off
     `main` by definition).

3. **Resolve the target version:**
   - `$ARGUMENTS` has an explicit version → use it verbatim.
   - `$ARGUMENTS` has a bump keyword (`major`/`minor`/`patch`) → apply that bump to `last`
     instead of the scanned suggestion.
   - Otherwise → use the scanned suggestion.
   - Tag format is bare `X.Y.Z` (matches existing tags — no `v` prefix).

4. **Confirm with the user** before proceeding — this is a deliberate decision, not a
   rubber-stamp. Show the suggested version, the reasoning (which commit types drove it), and
   the commit subjects considered.

---

## Step 2: Start the release branch

Skip if resuming (Pre-flight already detected the branch).

Via the **`apogee:git-flow` skill** (bundled with this plugin; if unavailable, run the `git flow` command
directly):
```
git flow release start <version>      # release mode, off develop
git flow hotfix start <version>       # hotfix mode, off main
```

---

## Step 3: Bump version — the lockstep core

Set `<version>` in **both** manifests:

- `plugins/apogee/.claude-plugin/plugin.json` → top-level `"version"`.
- `.claude-plugin/marketplace.json` → `.plugins[0].version`.

These two, plus the git tag (created at finish) and the CHANGELOG header (next step), are the
four lockstep points.

**Idempotency:** before editing, read each manifest's current version. If it already reads
`<version>`, leave that file untouched — this makes a re-run on a resumed branch a no-op here.

---

## Step 4: Refresh CHANGELOG

**Idempotency first:** check whether `CHANGELOG.md` already starts with `## [<version>]`. If
so, skip this entire step — the changelog was already refreshed by a prior partial run. Do
**not** prepend a duplicate section.

Otherwise, generate the entry:

1. **Range** = commits since the last tag (same scan as Step 1, or reuse its output):
   ```bash
   last=$(git describe --tags --abbrev=0 2>/dev/null)
   git log ${last:+$last..}HEAD --no-merges --format='%s'
   ```
2. **Group** the Conventional Commit subjects into [Keep a Changelog](https://keepachangelog.com/)
   sections, stripping the `type(scope):` prefix from each line:
   - `feat` → **Added**
   - `fix` → **Fixed**
   - `perf`, `refactor`, `docs` → **Changed**
   - `chore`, `style`, `ci`, `test` → omit (noise), unless user-visible.
3. **Write** a new section at the top of `CHANGELOG.md` (create the file with a Keep a
   Changelog + SemVer header if absent):
   ```markdown
   ## [<version>] - <YYYY-MM-DD>     # date from `date +%F`

   ### Added
   - <subject>

   ### Fixed
   - <subject>
   ```
   Skip empty sections. Do not rewrite or reorder existing released entries.

---

## Step 5: CI gate

Run:
```bash
bash scripts/validate.sh
```

- **Non-zero exit** → STOP. Surface the full output. **Leave the user on the release branch
  with the manifest/CHANGELOG edits in place** — do NOT abort the branch, discard the edits, or
  attempt an auto-fix. A git-flow release branch is a mutable staging area; the least
  surprising move is to let the user fix whatever `validate.sh` flagged and simply re-invoke
  this command, which resumes idempotently from Pre-flight's resume check.
- **Zero exit** → proceed to Step 6.

Do not commit anything before this gate passes.

---

## Step 6: Commit release prep

Via the **`apogee:git-commit` skill** (bundled with this plugin; if unavailable, `git commit -F <file>` directly),
following the two-commit pattern already used in this repo's history:

1. `docs(changelog): Update for <version>` — only if Step 4 actually wrote a new section
   (skip this commit if Step 4 was a no-op on resume).
2. `chore(release): Bump version to <version>` — only if Step 3 actually changed a manifest
   (skip this commit if both manifests were already at `<version>` on resume).

**Idempotency:** stage only the files each commit is about (never `git add -A`/`git add .`).
If there is nothing to commit for a step (already committed by a prior partial run), skip that
commit rather than erroring on an empty diff.

---

## Step 7: Stop before finish — surface

Do **not** run `release finish`/`hotfix finish` yourself. Report to the user:

- Version decided, and why (Step 1's reasoning).
- Both manifests + CHANGELOG confirmed at `<version>`.
- `validate.sh` passed.
- The exact command to finish, via the **`apogee:git-flow` skill**:
  ```
  git flow release finish -m "<version>" <version>
  git flow hotfix finish -m "<version>" <version>
  ```
- **Tag-editor gotcha:** `-m "<message>"` is required. `GIT_EDITOR=true` (or any editor that
  writes nothing) produces an empty tag message and a fatal error — always pass `-m` with real
  content.

Wait for the user to invoke it (themselves, or by asking you to run the `apogee:git-flow` skill).

---

## Step 8: Post-finish reminders

Once the user confirms `finish` succeeded (merge to `main` + annotated tag + back-merge to
`develop`), remind them of the two remaining manual steps — neither runs automatically:

1. **Push all three refs together:**
   ```bash
   git push origin main develop --tags
   ```
2. **Propagate to running Claude Code sessions:**
   ```
   /plugin marketplace update apogee
   /reload-plugins
   ```
   Local marketplaces don't auto-update — this step is what actually ships the bump to users.
