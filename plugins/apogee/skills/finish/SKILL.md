---
name: finish
description: "Close the unit of work /apogee:start opened, and the only way work is closed in an Apogee project. feature/bugfix: review, docs, public docs, clean tree, git-flow finish into develop, push develop. hotfix: review, then the release preparation (version, CHANGELOG, gate, notes) and the operator's commands. research: check the note is complete, mark it done, propose the follow-up. Detects the type from the current branch."
argument-hint: "[research <slug>]"
---

# Finish

The exit that `/apogee:start` opens. One command closes any unit of work; what it does depends on
the type. The raw `git flow <type> finish` commands are this skill's internals; don't run them
directly. Nothing here reaches `main` or creates a tag: for a hotfix this command prepares and
hands the finish to the operator (ADR 0007).

**Context from user:** $ARGUMENTS

Same rule throughout: if you're tempted to silently paper over a problem (stale docs, a dirty
tree, a failing gate, open steps), STOP and surface it.

---

## Detect the type

1. `$ARGUMENTS` starts with `research` → **research**, the slug (if given) names the file.
2. Else `git branch --show-current`, matched against the git-flow prefixes
   (`git config --get-regexp '^gitflow\.prefix\.'`, defaults `feature/ bugfix/ hotfix/ release/`):
   `feature/` or `bugfix/` → **work branch**; `hotfix/` → **hotfix**; `release/` → **release**.
3. Else (on `develop`, `main`, or a repo without git-flow): look for research files with
   `status: open` in `docs/apogee/research/`. Exactly one → **research** on that file. Several →
   list them and ask which. None, in a git-flow repo → nothing to finish; say so. None, in a repo
   **without** git-flow on a non-default branch → **plain branch** (below).

---

## Work branch (feature / bugfix)

1. **Survey.** Base = `gitflow.branch.develop`. `git log <base>..HEAD --oneline`,
   `git diff <base> --stat`, `git status`. No commits and a clean tree → offer
   `git flow <type> delete <slug>` instead of a finish. Diffs over ~200 lines or 10 files: summarise
   through an `Explore` sub-agent rather than reading the whole diff here.
2. **Review loop.** Run `apogee:review-work <base>`: tests of the change, review of the whole
   branch, fixes committed on the branch, tests again. It stops the finish if its tests are still
   red after two repair rounds. Skip only if it already ran in this session and no code was
   committed after its last commit. Note the commit it ended on.
3. **Docs.** Skip if `apogee:update-docs` already ran in this session after the last code commit.
   Otherwise apply its "When to Skip" list; if the change is substantive, run
   `apogee:update-docs <base>`. Then, when any doc under `docs/` declares `sources:` overlapping
   the branch's changed files and was not itself touched on the branch, run
   `apogee:public-docs update`. `update-docs` edits local-only files (`docs/apogee/`, the root
   `CLAUDE.md`), so there is nothing to commit; only public-docs output under `docs/` (and a
   tracked `CLAUDE.md`, if the project tracks it) commits through `apogee:git-commit`.
4. **Clean tree.** `git status` must be empty. Dirty → STOP; show `git status` and
   `git diff --stat`, and offer: commit named files, discard, abort. **Never `git add -A`.** This
   has no exception, autonomous or not (ADR 0006): a dirty tree at this point means commit
   discipline broke somewhere.
5. **Tracker** (beads projects). The epic linked to this branch (`external_ref`) should have all
   steps closed. Open steps → close the ones actually done, ask about the rest; don't close
   unfinished work to get past this.
6. **Still current.** If code (not docs) was committed after the commit `review-work` ended on —
   typically by step 3 or 5 — re-run its step 4 (tests of the change) on the new head. Red → STOP
   on the branch. The full suite is not run here; it belongs to the release preparation and CI.
7. **Finish.** Via the `apogee:git-flow` skill's command map:
   ```bash
   git flow <type> finish <slug>
   ```
   Invoked from `/apogee:run-plan`'s loop, prefix it with `APOGEE_RUN_PLAN=1` (the hook then checks
   for open epic steps, fail-closed); never add the prefix outside that loop. A merge conflict →
   STOP, leave the tree as it is, report the files. Worktree + git-flow is unsupported by AVH →
   STOP and point at the main checkout.
8. **Publish.** If a remote exists: `git push origin develop`, and delete the remote work branch
   (`git push origin --delete <type>/<slug>`) if it was published. In a superproject, push each
   submodule's branch first. Never `main`, never tags.
9. **Close the epic** (beads): `br epic close-eligible`; log
   `br comments add <epicId> --message "finish: merged <branch> into develop"`.
10. **Report:** branch, commit count, one-line summary, docs touched, pushed or not, anything
    carried forward (low-severity review notes, skipped docs and why).

---

## Hotfix

Steps 1–6 of the work branch, with base = the production branch (so `review-work main`), then the
release preparation, whose CI gate runs the full suite:
follow sections A–G of
`${CLAUDE_PLUGIN_ROOT}/skills/release/references/prepare-and-hand-over.md` with `<type>` =
`hotfix` and `<version>` = the branch slug. That bumps the version, writes the CHANGELOG section,
runs the gate, commits the prep, writes the notes file to `$TMPDIR` and prints the operator's
three commands (finish, push, publish). Stop there: the finish merges into `main` and tags, and
the hook refuses it to an agent. After the hand-over, make no commit on the branch until the
operator says the finish has not been run.

## Release branch

A `release/<version>` branch is `/apogee:release`'s; running `finish` on it resumes the same
preparation: sections A–G of the reference with `<type>` = `release`.

---

## Research

1. **Completeness.** The file must have a non-empty **Conclusion** and **Sources** (or an explicit
   "no external sources" with the reason). Missing → finish the research first; don't mark an
   unanswered question done.
2. **Close it.** Frontmatter `status: done` plus `finished: <YYYY-MM-DD>`; in
   `docs/apogee/README.md` change the Index line's `(open)` to the one-line answer.
3. **Promote what lasts.** A conclusion that is a standing fact about the domain belongs in
   `docs/apogee/domain/`; a settled architectural choice belongs in `CLAUDE.md` §4 (or an ADR in
   the project). Move or link it; the research note stays as the record of how it was decided.
4. **Tracker** (beads): close the research issue with the conclusion as the reason.
5. **Follow-up.** If the conclusion calls for code, end the report with the exact next command,
   e.g. `/apogee:start feature <slug>`; don't start it unasked.

No git anywhere in this mode: `docs/apogee/` is local-only.

---

## Plain branch (repo without git-flow)

The production-branch wall (ADR 0007) applies in every repo with a `main`, so an agent never
merges into it. Steps 1–6 of the work branch with base = the default branch, then push the
branch (`git push -u origin <branch>`) and hand over: print `gh pr create --fill` (or the merge
command) for the operator. Offer to initialise git-flow for next time (the `apogee:git-flow` skill, `main` + `develop`); with git-flow, `finish` can
merge into `develop` on its own.
