---
name: start
description: "Open a git-flow work branch the right way: feature or bugfix off an up-to-date develop, carrying any uncommitted changes along, linked to its br epic in beads projects, published to the remote. Use when work on a new change begins, or when changes were made on develop and need a branch. Hotfixes are a release-lifecycle matter and go through /apogee:release hotfix."
argument-hint: "[feature|bugfix] <slug or short description> [epic: <br id>]"
---

# Start Command

The entry point that `/apogee:merge` closes. One logical change, one branch, opened here so the
rules that live in prose (base branch, naming, the br link, no work on `develop`) are applied
once, by this command, instead of remembered each time.

**Context from user:** $ARGUMENTS

---

## Parse the arguments

- **Type.** First token `feature` or `bugfix` → that type. Absent → `bugfix` when the rest reads as
  a defect ("fix", "bug", "broken", "regression", a br issue of type `bug`), else `feature`.
  `hotfix` → STOP and point at `/apogee:release hotfix`: a hotfix is cut off `main` with a version
  and finished by the operator; this command never touches the production branch.
- **Slug.** If the remaining text is already a slug (`[a-z0-9-]+`, no spaces) use it. Otherwise
  derive one: lowercase, words joined by `-`, articles and filler dropped, at most 40 characters,
  no trailing `-`. Show the derived slug in the report; don't ask for approval of it.
- **Epic.** `epic: <id>` names the br epic to link. Without it, in a beads project, look for an
  open epic whose slug or title matches (`br list --json`, `issue_type == "epic"`).

---

## Pre-flight

1. **Git repo + git-flow.** `git rev-parse --is-inside-work-tree`, then
   `git config --get-regexp '^gitflow\.branch\.'`. Not git-flow → offer `git flow init -d` (via
   the `apogee:git-flow` skill) and stop until the user agrees; never hand-roll `git checkout -b`.
2. **Where am I.** `git branch --show-current`.
   - On `develop` or the production branch: fine; uncommitted changes (staged or not) travel to
     the new branch, which is exactly the fix for "I edited on develop by mistake".
   - On another `feature/`/`bugfix/` branch **with** uncommitted changes: STOP. Those changes
     belong to that branch; commit them there (`apogee:git-commit`) or stash them deliberately
     first. Don't silently carry one branch's work into another.
   - On another work branch with a clean tree: proceed, `git flow ... start` branches off
     `develop` regardless of the current checkout.
3. **Open work branches.** `git branch --list 'feature/*' 'bugfix/*'`. Any open → list them in
   the report. Parallel branches are allowed when their file sets are disjoint (CLAUDE.md
   "Decompose complex work"); don't block, don't ask, just make the state visible.
4. **Fresh base.** If a remote exists (`git remote` non-empty): `git fetch origin develop` and,
   when `develop` is checked out and behind, `git merge --ff-only origin/develop`. A diverged
   `develop` (local commits not on the remote) is left alone and mentioned in the report; never
   rebase or reset here.

---

## Open the branch

```bash
git flow <type> start <slug>
```

Then, if a remote exists, publish it so the branch is visible and the first push later needs no
`-u`:

```bash
git push -u origin <type>/<slug>
```

Pushing a work branch is sanctioned by ADR 0007; only `main` and tags are walled off. No remote →
skip, say so.

---

## Link the tracker (beads projects only)

Skip entirely when there is no `.beads/` at the repo root.

- Epic found or given: `br update <epicId> --external-ref <type>/<slug> --actor "${BR_ACTOR:-assistant}"`.
- No epic: create one so the work exists as an issue before code changes (CLAUDE.md "Track work
  in br"): `br create "<title from the description>" -t epic --slug <slug> --json`, then link it
  as above. One child step is enough to start (`br create "<first step>" -t task --parent
  <epicId> --json`); the plan can add more.
- Claim the first ready step: `br update <stepId> --claim --actor "${BR_ACTOR:-assistant}"`.
- Log it: `br comments add <epicId> --message "start: opened branch <type>/<slug>"`.

`br` never runs git and `.beads/` is local-only; nothing to commit here.

---

## Report

Four lines, no more:

- Branch opened (`<type>/<slug>` off `develop` at `<short sha>`), published or not.
- Uncommitted changes carried along, if any (`git status --short` count).
- Epic linked / created / none (not a beads project).
- Other open work branches, if any.

Then continue with the work. Commits go through `apogee:git-commit`; the branch is finished with
`/apogee:merge`. Nothing here needs confirmation: opening a branch is reversible with
`git flow <type> delete <slug>`.
