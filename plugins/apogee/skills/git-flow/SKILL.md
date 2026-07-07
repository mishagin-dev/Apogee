---
name: git-flow
description: 'Drive the installed git flow binary (AVH Edition) for Git Flow branching: init a repo, start/finish/publish feature and bugfix branches, cut and finish a release with tag and back-merge, ship a hotfix, or open a support branch. Use when asked to run git flow, start or finish a feature/release/hotfix, cut a release, tag a version, or initialize Git Flow. Applies only inside a git repository.'
---

# Git Flow Skill

## Precondition — git repository required

This skill operates only inside a git repository. Before anything else, check:

!`git rev-parse --is-inside-work-tree 2>/dev/null && echo GIT_OK || echo NOT_A_GIT_REPO`

If the line above reads `NOT_A_GIT_REPO`, **stop immediately**: tell the user
this directory is not a git repository (offer `git init`, then `git flow init -d`),
and run none of the commands below.

Drive Git Flow through the **installed `git flow` binary** (AVH Edition 1.12.3,
`/opt/homebrew/bin/git-flow`) — not hand-rolled `git merge`/`tag` sequences. The
binary reads branch names and prefixes from local `gitflow.*` git config and
performs the merge + tag + back-merge + branch-delete steps atomically.

Paths below are relative to the repo root.

## Detect first

Confirm the binary and the repo's configured model before touching branches:

```bash
git flow version
git flow config
git status -sb
```

`git flow config` is the source of truth for this repo's production branch,
develop branch, and prefixes. If it errors or `develop` is missing, the repo
is not yet gitflow-initialized — run `git flow init -d` (the `-d` accepts
default conventions non-interactively) before any branch work.

> Check for remotes with `git remote`. If the output is empty, skip `publish`,
> `track`, and the `-p/--push` flags — they need an `origin`.

## Command map

`<name>` is a slug (`PROJ-142-login`); `<version>` is a version (`2.4.0`).
`finish` operates on the current branch's type and, by default, **merges,
tags (release/hotfix), back-merges, and deletes the branch**.

| Action | Command |
|---|---|
| Start feature (off `develop`) | `git flow feature start <name>` |
| Finish feature → `develop` | `git flow feature finish <name>` |
| Keep feature branch after finish | `git flow feature finish -k <name>` |
| Force a merge commit | `git flow feature finish --no-ff <name>` |
| Switch to a feature | `git flow feature checkout <name>` |
| List / delete feature | `git flow feature list` · `git flow feature delete <name>` |
| Start bugfix (off `develop`) | `git flow bugfix start <name>` |
| Finish bugfix → `develop` | `git flow bugfix finish <name>` |
| Start release (off `develop`) | `git flow release start <version>` |
| Finish release (merge `main` + tag + back-merge) | `git flow release finish -m "<msg>" <version>` |
| Finish release without a tag | `git flow release finish -n -m "<msg>" <version>` |
| Start hotfix (off `main`) | `git flow hotfix start <version>` |
| Finish hotfix (merge `main` + tag + back-merge) | `git flow hotfix finish -m "<msg>" <version>` |
| Start support branch (off a base) | `git flow support start <version> <base>` |
| Preview underlying git commands | append `--showcommands` to any subcommand |

`release finish`/`hotfix finish` require a tag message — pass `-m "<msg>"`
(non-interactive) or they open an editor. `support` has only `start` (no finish).

## Guardrails

- **Clean tree before `finish`.** Commit or stash first; `finish` aborts on a
  dirty working tree.
- **`finish` deletes the branch by default.** Pass `-k` (or `--keeplocal`) to
  keep it; the change is already merged regardless.
- **Opt out of automation when needed.** `-n` (release: skip tag), `-b` /
  `--nobackmerge` (skip back-merge into develop).
- **Dry-run by reading, not running.** `--showcommands` prints each underlying
  `git` call so you can confirm the branch pair before it merges.
- **No remote here** — never pass `-p`/`--push`, `publish`, or `track`.
- **Commits only inside gitflow branches.** Never commit directly on `main` or
  `develop`; always start a feature/bugfix/hotfix/release first.
- **`release finish` / `hotfix finish` — user request only.** These touch the
  production branch. Never run them autonomously; wait for the user to ask.
  The enforcement hook will surface a confirmation prompt in any case.

## beads link (CCDK / beads_rust projects)

In a beads project (a `.beads/` dir at the repo root), a git-flow work branch
maps **1:1 to a br epic** — one track == one epic == one feature/bugfix branch.
The link is the convention the branch gate (below) enforces:

- **Name the branch after the epic slug.** The epic is created with
  `br create … --slug <id>`; start the branch as `git flow feature start <id>`
  (or `bugfix` for a bug track) so the branch is `feature/<id>`.
- **Record the branch on the epic** right after starting it:

  ```bash
  br update <epicId> --external-ref <branch> --actor "${BR_ACTOR:-assistant}"
  ```

  (`br` never runs git; setting `external_ref` is a plain metadata write. Run
  `br sync --flush-only` and commit `.beads/` via the git-commit skill as usual.)
- **All steps of the epic** (its `parent-child` children) are implemented and
  committed on that one branch, then merged together at `git flow feature finish`.
- **Before `finish`,** the epic's steps should all be closed in br — the branch
  is the unit that merges, so leaving steps open breaks the 1:1 link.

## Enforcement hook (active)

A PreToolUse hook (`plugins/apogee/hooks/git/enforce-git-flow-skill.py`) is wired via
`hooks.json`. In gitflow-enabled repos it enforces five rules:

1. **ASK** — `git flow release finish` / `git flow hotfix finish`: surfaces a
   confirmation prompt (touches production branch).
2. **DENY** — `git commit` on a non-gitflow branch (`main`, `develop`, etc.).
3. **DENY** — `git merge` while the current branch is the production branch.
4. **DENY** — manual branch creation with a gitflow-prefixed name
   (`git checkout -b feature/...`, `git switch -c release/...`, etc.).
5. **DENY** — `git merge` of a gitflow-prefixed ref from any branch.

In repos without gitflow config the hook is completely inert.

A **companion edit-time gate** (`plugins/apogee/hooks/br/br-branch-gate.py`, on
`Edit|Write|MultiEdit|NotebookEdit`) enforces the same discipline at the source —
it **denies code edits** on a base branch (`main`/`develop`), and on a
feature/bugfix branch whose `external_ref` link (see "beads link" above) does not
match the active step's epic. It is active only in repos that are **both** beads
and gitflow initialized; inert elsewhere. Escape hatch: `BR_GATE_OFF=1`.

## Troubleshooting

- **Binary behavior in doubt** — validate it in a throwaway sandbox:

  ```bash
  bash plugins/apogee/skills/git-flow/smoke.sh
  ```

  It runs `init` + a feature round-trip + a release round-trip in a `mktemp -d`
  repo and prints `SMOKE OK`. Never touches your working tree.

- **Help/output is in Russian** (e.g. «Переключились на ветку…»): the host git
  is localized, so `git flow` status lines and `-h` text come out localized.
  The commands and flags are unchanged; `SMOKE OK` from the driver is the
  source of truth, not the chatter. Force English with `LC_ALL=C git flow …`.
- **`finish` opens vim** on a release/hotfix: you omitted `-m "<msg>"`. Re-run
  with an explicit message.
- **`Fatal: Not a gitflow-enabled repo yet`**: run `git flow init -d` first.
