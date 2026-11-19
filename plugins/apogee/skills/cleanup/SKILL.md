---
name: cleanup
description: "Reclaim disk space that agent work leaves behind: linked git worktrees (of the repository and of every submodule), the stale records of worktrees deleted by hand, orphaned worktree directories, and the build directories (Rust target/, DerivedData) that make each copy 5–35 GB. Inventories first with a read-only script, deletes only what the user picks. Use when the disk fills up, when worktrees pile up after parallel agents, or when the user asks to clean up, tidy up or free space, in any language."
argument-hint: "[<path inside the repo>] [--no-size]"
---

# Cleanup

Agents that work in parallel each take a git worktree, and a worktree of a compiled project grows
its own build directory: a Rust workspace is 5–35 GB per copy. Nobody removes them when the work
is merged, and a directory deleted by hand leaves its record in git (`prunable` in
`git worktree list`). In a superproject every submodule has a gitdir of its own with its own list,
so the leftovers multiply. This skill finds all of it, says what is safe to delete and why, and
deletes only what the user picks.

Nothing is removed before the user has seen the inventory and chosen. Work that exists nowhere
else (uncommitted changes, commits on no base branch or remote) is never removed by default.

## 1. Inventory

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/cleanup/scripts/inventory.sh" [--no-size] [<path>]
```

Read-only. Started anywhere inside the repository (a linked worktree or a submodule included), it
finds the superproject's main checkout and walks it and every initialised submodule. Sizes come
from `du` and take a minute or two on a large tree; `--no-size` skips them. Output is one
tab-separated line per entry: `VERDICT SIZE PATH REF NOTE`.

| Verdict | Meaning | Default action |
|---|---|---|
| `PRUNE` | git records a worktree whose directory is gone | prune the record |
| `REMOVE` | clean, every commit on `develop`/`main`/`master` or a remote, not used recently | remove |
| `KEEP` | uncommitted changes, unpushed commits (its own, a submodule's inside it, or a nested worktree's), locked, or used recently: another session may be in it | leave; the note says why |
| `NESTED` | a submodule worktree inside another listed worktree | goes with its parent, which already accounts for it |
| `ORPHAN` | a directory in the repo whose `.git` file points at a gitdir that no longer exists | remove on request |
| `BUILD` | a Rust `target/` (next to a `Cargo.toml`) or `DerivedData/` of the main checkout | report only |

Show the user a summary, not the raw output: `PRUNE` as one count, then every other entry with
its size, ref and note, largest first, and the total that the default actions would free. The
untracked files that make a worktree `KEEP` are often screenshots or build output; list them
(`git -C <path> status --short | head -20`) so the user can judge.

## 2. Choose

One `AskUserQuestion`, multi-select, built from what the inventory found (omit empty groups):

- Prune the N stale records (recommended; touches no files).
- Remove the `REMOVE` worktrees, with their sizes (recommended).
- Remove the `ORPHAN` directories.
- Specific `KEEP` worktrees, each named with what would be lost (its note). Offer one only after
  the user has seen its untracked files or unpushed commits; never recommend one.
- `BUILD` directories: deleting one costs a full rebuild, and a concurrent agent may be building
  into it. Offer only when the user asked for space beyond the worktrees.

## 3. Execute

One state-changing command per step, each path named in full.

- **Prune**, for each gitdir named in the `PRUNE` notes:
  `git --git-dir=<gitdir> worktree prune -v`.
- **Remove a worktree**: `git -C <main checkout of its repo> worktree remove <path>`. Without
  `--force` git refuses a dirty tree, which is the safety net if something changed since the
  inventory. A worktree that contains submodules is refused with "working trees containing
  submodules cannot be moved or removed": re-run the inventory for it, confirm it is still
  `REMOVE`, then delete the directory by its path and prune the superproject's gitdir and every
  submodule gitdir that listed a worktree inside it.
- **Orphans and build directories**: delete the directory by its path.
- A deletion the permission layer refuses stays refused: report the path and give the user the
  exact command to run.

## 4. Report

Re-run the inventory with `--no-size` to confirm the result, then report in a few lines: what was
pruned and removed, what was kept and why, and the space freed (`df -h <volume>` before and
after). Suggest nothing else unless asked.
