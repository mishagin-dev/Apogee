# Release Command

Own a project's release lifecycle end to end: detect where its version lives, bump it (in
lockstep across every place found), refresh the CHANGELOG, gate on the project's test/validate
command, commit the release prep, then run `git flow release|hotfix finish` itself (the
`enforce-git-flow-skill` hook asks for confirmation since it touches the production branch).
Pushing stays a separate, explicit user action — this command never runs it.

**Context from user:** $ARGUMENTS

---

## Philosophy

A release keeps a small set of things in lockstep: wherever the version is declared (if
anywhere), the git annotated tag, and the `CHANGELOG.md` `## [x.y.z]` header. Where the version is
declared varies by project — Apogee's own release, for instance, keeps
`plugins/apogee/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` in lockstep;
plenty of projects (Go modules, a submodule tracked only by CHANGELOG + a README badge) don't
declare a version anywhere at all and rely on the tag alone. This command detects which case
applies instead of assuming one.

Same rule as `/merge`: if you're tempted to silently paper over a problem (a failing test gate, an
ambiguous version bump or version source, a dirty tree), STOP and surface it. A release is
semi-destructive once tagged — an easy mistake to avoid, an annoying one to unwind.

Only `git push` runs **on a separate, explicit user request** (manual after review, per this
project's own `CLAUDE.md`). `release finish`/`hotfix finish` runs directly once the user has asked
for this release — the `enforce-git-flow-skill` hook already ASKs for confirmation since it
touches the production branch, which is the actual safety gate; this command doesn't add a second
wait on top of it.

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
     duplicate a CHANGELOG section or create a redundant commit. Version-source detection
     (below) also re-runs on resume — it's read-only and cheap, and its result is needed by
     every later step regardless of how far a prior partial run got.
   - On `develop`/`main`/anything else → proceed from Step 1 (fresh release).

4. **Clean-tree guardrail** (only when starting fresh, not on resume — a resumed branch may
   legitimately have uncommitted manifest edits from a prior partial run, handled by later
   steps' idempotency). Dirty tree on a fresh start → STOP. Show `git status` + `git diff --stat`,
   offer: (a) commit named files, (b) discard, (c) abort. **Never `git add -A` or `git add .`.**

5. **Version-source detection.** Determine where (if anywhere) this project declares its version,
   and what tag-prefix convention it uses. This result feeds Steps 1, 3, 5, 7, and 8 below.

   a. **Apogee-plugin lockstep pair** — check first, most specific:
      `plugins/apogee/.claude-plugin/plugin.json` AND `.claude-plugin/marketplace.json` both
      present **and** `plugin.json`'s top-level `.name == "apogee"` (an identity check, not just
      path existence — a project that vendors/copies Apogee's plugin source into its own tree,
      rather than just enabling it, must not false-match this). Match → version source is these
      two files; this is "releasing Apogee itself."

   b. **Else scan standalone candidates**, in this order, for an EXISTING version field — never
      invent a new field in someone's manifest:
      - `package.json` → `.version` via `jq`. **Skip as unreliable** (don't count as a match) if
        `.version == "0.0.0"` or `.private == true` — the common signature of a monorepo/workspace
        root whose real version lives in `packages/*/package.json`. Surface a note instead: "root
        package.json looks like a private/workspace root — skipped; bump the real package by hand
        if that's where your version lives."
      - `composer.json` → `.version` via `jq`, only if the key is present (Composer projects often
        omit it deliberately — a missing key means "not a candidate," not "bump to null").
      - `pyproject.toml` → regex `^version = "..."` under `[project]` or `[tool.poetry]`. **Skip**
        if the file also contains `dynamic = [` with `"version"` listed — that's
        setuptools-scm/dynamic versioning; a static `version =` alongside it is a stale
        placeholder, not the source of truth.
      - `Cargo.toml` → regex `^version = "..."` under `[package]`.
      - `VERSION` or `VERSION.txt` → plain file content, trimmed.
      - `go.mod` present and none of the above matched → expected, not an error; Go modules don't
        carry a version field. Falls through to (c).

      If multiple candidates match with **differing** current values → STOP, list every match,
      ask the user which is authoritative (or whether to bump all of them). Don't guess.

   c. **If nothing matched** → **"CHANGELOG + git tag only" mode**. Surface this explicitly to the
      user in Step 1's confirmation ("no version manifest detected — this release is tracked via
      CHANGELOG.md + git tag only"), never as a silent no-op.

   d. **Tag-prefix inference:** if the repo already has tags, match the most recent tag's prefix
      style (`v1.2.3` vs `1.2.3`). If no tags exist yet (first release), default to bare `X.Y.Z`
      unless `go.mod` is present at the repo root, in which case default to `v`-prefixed (Go's
      convention for `go get` resolution).

   e. **README badge nudge:** grep `README.md` (if present) for a version-badge-like pattern
      (`shields.io`, `badge`, or the literal current version string, when one was found in
      5b/5c/5d). If found, note it for Step 1's confirmation and Step 7's final report:
      "possible version badge in README.md — update by hand if relevant." Never auto-edited —
      badge formats are too varied to safely template-edit.

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
   - `hotfix` mode → always **patch**, regardless of commit types (hotfixes are bugfixes off
     `main` by definition).

3. **Resolve the target version:**
   - `$ARGUMENTS` has an explicit version → use it verbatim.
   - `$ARGUMENTS` has a bump keyword (`major`/`minor`/`patch`) → apply that bump to `last`
     instead of the scanned suggestion.
   - Otherwise → use the scanned suggestion.
   - Apply the tag-prefix style resolved in Pre-flight 5d.

4. **Confirm with the user** before proceeding — this is a deliberate decision, not a
   rubber-stamp. Show:
   - The suggested version, the reasoning (which commit types drove it), and the commit subjects
     considered.
   - What Pre-flight 5 detected: which file(s) will be bumped (or "CHANGELOG + git tag only, no
     manifest found"), the tag-prefix style, and the README badge nudge if any.

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

## Step 3: Bump version

Write `<version>` into whatever Pre-flight 5 detected/the user confirmed:

- Apogee-plugin lockstep pair → both `plugin.json` (`.version`) and `marketplace.json`
  (`.plugins[0].version`).
- A standalone candidate (or several, if the user chose to bump multiple ambiguous matches) →
  each one, using its own format (`jq` for JSON, targeted regex replace for `pyproject.toml`/
  `Cargo.toml` to avoid reformatting the rest of the file, plain overwrite for `VERSION`/
  `VERSION.txt`).
- Nothing detected → skip this step entirely; the release is tracked via CHANGELOG + tag only.

**Idempotency:** before editing each file, read its current version. If it already reads
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

Run the project's own test/validate command, resolved via this fallback chain:

1. `scripts/validate.sh` present at the repo root → run it (covers Apogee's own repo unchanged).
2. Else, read the project's own `CLAUDE.md` for a "Testing" section and run the full-suite
   command it documents. **Strip HTML comments (`<!-- ... -->`) before scanning** — the scaffold
   template ships this section as commented-out boilerplate in every fresh project, and matching
   inside a comment would pick up placeholder text as a real command.
3. Else, ask the user what command constitutes the release gate for this project (or confirm
   there isn't one) — never silently skip.

- **Gate command fails / non-zero exit** → STOP. Surface the full output. **Leave the user on the
  release branch with the manifest/CHANGELOG edits in place** — do NOT abort the branch, discard
  the edits, or attempt an auto-fix. A git-flow release branch is a mutable staging area; the
  least surprising move is to let the user fix whatever failed and simply re-invoke this command,
  which resumes idempotently from Pre-flight's resume check.
- **Passes (or the user confirmed there's no gate)** → proceed to Step 6.

Do not commit anything before this gate passes.

---

## Step 6: Commit release prep

Via the **`apogee:git-commit` skill** (bundled with this plugin; if unavailable, `git commit -F <file>` directly):

1. `docs(changelog): Update for <version>` — only if Step 4 actually wrote a new section
   (skip this commit if Step 4 was a no-op on resume).
2. `chore(release): Bump version to <version>` — only if Step 3 actually changed a file
   (skip this commit if the version source was already at `<version>` on resume, or if there
   was no version source to bump).

**Idempotency:** stage only the files each commit is about (never `git add -A`/`git add .`).
If there is nothing to commit for a step (already committed by a prior partial run, or no
version source exists), skip that commit rather than erroring on an empty diff.

---

## Step 7: Finish

Report to the user first, reflecting what actually happened in this run (not a fixed template):

- Version decided, and why (Step 1's reasoning).
- What was bumped: either "plugin.json + marketplace.json confirmed at `<version>`" (Apogee's own
  repo), or the specific standalone file(s) bumped, or "no version manifest — CHANGELOG + git tag
  only" if Pre-flight 5c applied.
- CHANGELOG confirmed at `<version>`.
- Which CI-gate command was run (tier 1/2/3 from Step 5) and that it passed.
- The README badge nudge, if Pre-flight 5e found one.

Then run the finish directly, via the **`apogee:git-flow` skill** (or `git flow ... finish`
directly if the skill isn't available):
```
git flow release finish -m "<version>" <version>
git flow hotfix finish -m "<version>" <version>
```

**Tag-editor gotcha:** `-m "<message>"` is required. `GIT_EDITOR=true` (or any editor that
writes nothing) produces an empty tag message and a fatal error — always pass `-m` with real
content.

The `enforce-git-flow-skill` hook ASKs for confirmation before this runs, since it touches the
production branch — that's the actual gate, not a separate "wait for the user" step in this
command. Once confirmed, `finish` merges to `main`, creates the annotated tag, and back-merges to
`develop` automatically.

---

## Step 8: Post-finish reminders

Once the user confirms `finish` succeeded (merge to `main` + annotated tag + back-merge to
`develop`), remind them of the remaining manual steps — none run automatically:

1. **Push all three refs together:**
   ```bash
   git push origin main develop --tags
   ```
2. **Publish the release on GitHub/GitLab.** Follow the `apogee:git-flow` skill's "Publishing the
   release (gh/glab)" procedure: it defers to CI if one already auto-publishes on tag push,
   otherwise creates the Release itself via `gh`/`glab` (detected from `remote.origin.url`) with
   notes drafted from the CHANGELOG entry just written.
3. **Only when Pre-flight 5a matched (releasing Apogee itself):** propagate to running Claude Code
   sessions:
   ```
   /plugin marketplace update apogee
   /reload-plugins
   ```
   Local marketplaces don't auto-update — this step is what actually ships the bump to users of
   the Apogee plugin. Skip this bullet entirely for any other project.
