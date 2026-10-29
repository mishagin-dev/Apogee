# Prepare and hand over a release or hotfix

Shared by `/apogee:release` (a `release/<version>` branch cut from `develop`) and `/apogee:finish`
on a `hotfix/<version>` branch. Both arrive here on the branch, with `<version>` fixed (the branch
slug). Everything below is idempotent: re-running on a partially prepared branch must not
duplicate a CHANGELOG section or create a redundant commit. The branch type (`release` or
`hotfix`) is the current branch's git-flow prefix and fills `<type>` in the printed commands.

## A. Version source

**Version-source detection.** Determine where (if anywhere) this project declares its version,
and what tag-prefix convention it uses. The result feeds every step below.

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
   user in the version confirmation ("no version manifest detected — this release is tracked via
   CHANGELOG.md + git tag only"), never as a silent no-op.

d. **Tag-prefix inference:** if the repo already has tags, match the most recent tag's prefix
   style (`v1.2.3` vs `1.2.3`). If no tags exist yet (first release), default to bare `X.Y.Z`
   unless `go.mod` is present at the repo root, in which case default to `v`-prefixed (Go's
   convention for `go get` resolution).

e. **README badge nudge:** grep `README.md` (if present) for a version-badge-like pattern
   (`shields.io`, `badge`, or the literal current version string, when one was found in
   (b)/(c)/(d)). If found, note it for the version confirmation and the F report:
   "possible version badge in README.md — update by hand if relevant." Never auto-edited —
   badge formats are too varied to safely template-edit.

---

## B. Bump version

Write `<version>` into whatever section A detected/the user confirmed:

- Apogee-plugin lockstep pair → both `plugin.json` (`.version`) and `marketplace.json`
  (`.plugins[] | select(.name == "apogee") | .version`).
- A standalone candidate (or several, if the user chose to bump multiple ambiguous matches) →
  each one, using its own format (`jq` for JSON, targeted regex replace for `pyproject.toml`/
  `Cargo.toml` to avoid reformatting the rest of the file, plain overwrite for `VERSION`/
  `VERSION.txt`).
- Nothing detected → skip this step entirely; the release is tracked via CHANGELOG + tag only.

**Idempotency:** before editing each file, read its current version. If it already reads
`<version>`, leave that file untouched — this makes a re-run on a resumed branch a no-op here.

---

## C. Refresh CHANGELOG

**Idempotency first:** check whether `CHANGELOG.md` already starts with `## [<version>]`. If
so, skip this entire step — the changelog was already refreshed by a prior partial run. Do
**not** prepend a duplicate section.

Otherwise, generate the entry:

1. **Range** = commits since the last tag (reuse the scan from version selection):
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

## D. CI gate

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
- **Passes (or the user confirmed there's no gate)** → proceed to E.

Do not commit anything before this gate passes.

---

## E. Commit release prep

Via the **`apogee:git-commit` skill** (bundled with this plugin; if unavailable, `git commit -F -` directly,
the message in a quoted heredoc as in its step 5, no temp file):

1. `docs(changelog): Update for <version>` — only if C actually wrote a new section
   (skip this commit if C was a no-op on resume).
2. `chore(release): Bump version to <version>` — only if B actually changed a file
   (skip this commit if the version source was already at `<version>` on resume, or if there
   was no version source to bump).

**Idempotency:** stage only the files each commit is about (never `git add -A`/`git add .`).
If there is nothing to commit for a step (already committed by a prior partial run, or no
version source exists), skip that commit rather than erroring on an empty diff.

---

## F. Hand over the finish

Report to the user first, reflecting what actually happened in this run (not a fixed template):

- Version decided, and why.
- What was bumped: either "plugin.json + marketplace.json confirmed at `<version>`" (Apogee's own
  repo), or the specific standalone file(s) bumped, or "no version manifest — CHANGELOG + git tag
  only" if A(c) applied.
- CHANGELOG confirmed at `<version>`.
- Which CI-gate command was run (tier 1/2/3 from D) and that it passed.
- The README badge nudge, if A(e) found one.

**Write the release notes file.** Draft the release announcement from the CHANGELOG section
just written (or already present on resume): a lead sentence on what the release is about, then
the highlights grouped sensibly, in English, Markdown, no heading for the version itself (the tag
and the hosting platform add it). This is a short writing task, not a copy of the changelog
bullets. Write it to the user's temp directory, where the OS cleans it up on its own:

```bash
notes="${TMPDIR:-/tmp}/apogee-release-<version>.md"
```

Overwrite the file if it exists (a re-run regenerates it). The file is the release description on
the hosting platform; the tag message stays short (the version), as every tag before it.

Then print the exact commands for the operator and stop. The tree is on the release/hotfix branch
with the prep committed; nothing else is pending.

```
GIT_MERGE_AUTOEDIT=no git flow <type> finish -m "<version>" <version>
git push origin main develop --tags
gh release create <version> --notes-file "<notes path>" --verify-tag     # or: glab release create <version> -F "<notes path>"
```

`-m` is required: without it `finish` opens an editor, and an editor that writes nothing
(`GIT_EDITOR=true`) produces an empty tag message and a fatal error. `GIT_MERGE_AUTOEDIT=no`
keeps the two merge commits (into `main`, back into `develop`) from opening an editor too; a
GUI editor (`core.editor = zed --wait`) that closes without saving aborts the merge commit and
leaves `main` mid-merge, which the next `finish` refuses with "Index contains uncommited
changes". Recovery for that state: `git commit --no-edit --cleanup=strip` (the `--cleanup`
drops the template's `#` lines from the message), then re-run the finish. The third command publishes
the release with the notes file as its description; pick `gh` or `glab` from `remote.origin.url`
(the git-flow skill's "Publishing the release" procedure). If the project's CI already publishes a
release on tag push, print `gh release edit <version> --notes-file "<notes path>"` instead, so
the polished notes replace the generated ones rather than colliding with them.

Do not run any of them, even if asked in the same breath: the hook denies the finish and the push
to an agent ([ADR 0007](../../../../docs/decisions/0007-production-branch-wall.md)), and the point
of the wall is that no phrasing unlocks it.

**After the hand-over, the release branch is the operator's.** Make no further commit on it, not
even a one-line fix, until the operator says the finish has NOT been run yet. `git flow release
finish` checks out `main` and runs a merge in this same working tree; a `git commit` issued by the
agent while that merge is open completes the merge with the agent's message and staged files,
and the finish fails half-way (no tag, no back-merge). If something must change after the
hand-over, ask first, then re-run `/apogee:release` (release branch) or `/apogee:finish` (hotfix
branch), which resume idempotently.

## G. After the operator has finished

If the operator comes back in this session after running the finish and the push, the remaining
steps are:

1. **Publish the release.** The third command printed in F (`gh release create ...
   --notes-file`, or `glab`) does it; the notes file from F is the release description, no
   second draft. Verify with `gh release view <version>`.
2. **Only when A(a) matched (releasing Apogee itself):** propagate to running Claude Code
   sessions:
   ```
   /plugin marketplace update apogee
   /reload-plugins
   ```
   Marketplaces don't auto-update — this step is what actually ships the bump to users of the
   Apogee plugin. Skip this bullet entirely for any other project.
