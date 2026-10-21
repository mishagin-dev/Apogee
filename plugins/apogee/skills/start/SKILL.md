---
name: start
description: "Open a unit of work the right way, and the only way work is opened in an Apogee project: feature or bugfix branch off an up-to-date develop, hotfix branch off main with its version, or a research note with no branch at all. Carries uncommitted changes along, links the br epic in beads projects, publishes the branch. Closed by /apogee:finish."
argument-hint: "[feature|bugfix|hotfix|research] <slug or description> [epic: <br id>] [version: <x.y.z>]"
---

# Start

The entry point that `/apogee:finish` closes. Every unit of work goes through this pair, so the
rules that live in prose (base branch, naming, the br link, no work on `develop` or `main`) are
applied once, here, instead of remembered each time. The raw `git flow <type> start` commands are
this skill's internals; don't run them directly.

**Context from user:** $ARGUMENTS

---

## Parse the arguments

- **Type.** First token `feature`, `bugfix`, `hotfix` or `research` → that type. Absent → infer:
  a defect ("fix", "bug", "broken", "regression", a br issue of type `bug`) → `bugfix`; a question
  to answer rather than code to write ("investigate", "compare", "evaluate", "research", "which
  … should we") → `research`; otherwise `feature`. A hotfix is never inferred: it touches the
  production line, so it must be asked for by name.
- **Slug.** If the remaining text is already a slug (`[a-z0-9-]+`) use it. Otherwise derive one:
  lowercase, words joined by `-`, filler dropped, at most 40 characters. Show it in the report;
  don't ask for approval.
- **Epic.** `epic: <id>` names the br epic to link. Without it, in a beads project, look for an
  open epic whose slug or title matches (`br list --json`, `issue_type == "epic"`).
- **Version** (hotfix only). `version: <x.y.z>`, else the last tag with the patch number bumped
  (`git describe --tags --abbrev=0`, keeping its `v` prefix style). The hotfix branch is named
  after the version, as git-flow expects; the slug goes into the br epic title and the report.

---

## Pre-flight (branch types)

Skip for `research`.

1. **Git repo + git-flow.** `git rev-parse --is-inside-work-tree`, then
   `git config --get-regexp '^gitflow\.branch\.'`. Not git-flow → offer to initialise it (the
   `apogee:git-flow` skill's "Detect first": `main` + `develop`) and stop until the user agrees; never hand-roll `git checkout -b`.
2. **Where am I.** `git branch --show-current`.
   - On `develop` or the production branch: fine; uncommitted changes (staged or not) travel to
     the new branch, which is exactly the fix for "I edited on develop by mistake".
   - On another work branch **with** uncommitted changes: STOP. Those changes belong to that
     branch; commit them there (`apogee:git-commit`) or stash them deliberately first.
   - On another work branch with a clean tree: proceed.
3. **Open work.** `git branch --list 'feature/*' 'bugfix/*' 'hotfix/*'`. Any open → list them in the
   report. Parallel feature/bugfix branches are fine when their file sets are disjoint. A second
   open **hotfix** → STOP: git-flow allows one at a time; finish the open one first.
4. **Fresh base.** If a remote exists: `git fetch origin`, then fast-forward the base branch
   (`develop` for feature/bugfix, the production branch for hotfix) when it is checked out and
   behind: `git merge --ff-only origin/<base>`. A diverged base is left alone and reported; never
   rebase or reset here.

---

## Open: feature / bugfix

```bash
git flow <type> start <slug>
git push -u origin <type>/<slug>        # only if a remote exists
```

## Open: hotfix

```bash
git flow hotfix start <version>         # branches off the production branch
git push -u origin hotfix/<version>     # only if a remote exists
```

Starting a hotfix only creates a branch from `main`; nothing reaches `main` until the operator
runs the finish that `/apogee:finish` prepares (ADR 0007). Fix the defect with small commits on
this branch; the version bump and CHANGELOG are `/apogee:finish`'s job, not the first commit's.

## Open: research

No branch, no git: the output lands in `docs/apogee/research/`, which is local-only (a
ceremony-free deliverable, CLAUDE.md §1). Create

```
docs/apogee/research/<YYYY-MM-DD>-<slug>.md
```

with this skeleton, filled from the request:

```markdown
---
status: open
started: <YYYY-MM-DD>
question: "<the question, one sentence>"
---

# <Title>

## Question
## Context            <!-- why it is asked now, constraints, what is already decided -->
## Findings           <!-- evidence, each claim with its source -->
## Options            <!-- when there is a choice: trade-offs, not a survey -->
## Conclusion         <!-- the answer, and what it means for the project -->
## Sources
```

Add one line to `docs/apogee/README.md`'s Index: path, the question, `(open)`. Then do the
research into that file, not into the chat: Context7 for library questions, WebSearch for the
rest, `apogee:second-opinion` for a contested trade-off. Code is not changed under a research
item; if the answer calls for code, `/apogee:finish` proposes the follow-up `start`.

---

## Link the tracker (beads projects only)

Skip when there is no `.beads/` at the repo root.

- **Branch types.** Epic found or given: `br update <epicId> --external-ref <branch>
  --actor "${BR_ACTOR:-assistant}"`. No epic: create one (`br create "<title>" -t epic --slug
  <slug> --json`, a hotfix's title carrying its version) plus one child step, link it, then claim
  the step: `br update <stepId> --claim --actor "${BR_ACTOR:-assistant}"`.
- **Research.** One issue, no epic: `br create "<question>" -t task -l research --json`, its
  `external_ref` set to the research file's path; claim it.
- Log it: `br comments add <id> --message "start: opened <branch or research file>"`.

`br` never runs git and `.beads/` is local-only; nothing to commit here.

---

## Report

Four lines, no more:

- What was opened: `<type>/<slug>` off `<base>` at `<short sha>` (published or not), or the
  research file path.
- Uncommitted changes carried along, if any.
- Epic / issue linked, created, or none (not a beads project).
- Other open work, if any.

Then continue with the work. Commits go through `apogee:git-commit`; the unit is closed with
`/apogee:finish`. Nothing here needs confirmation: a branch is reversible with
`git flow <type> delete <name>`, a research file with `rm`.
