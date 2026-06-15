# ADR 0001 — Work tracker: beads_rust (`br`), not original beads (`bd`)

**Status:** Accepted · **Date:** 2026-06-15

## Context

Apogee is hook-driven: `br` is invoked on every edit, SessionStart, PreCompact, and Stop
(`br-edit-gate`, `br-branch-gate`, `br-capture-gate`, `br-prime`, `br-snapshot`, `br-progress-gate`,
`br-sig`), and `br-snapshot` commits `.beads/` JSONL through git. The question was whether to
standardize on the original `bd` instead.

Research (2026-06) showed this is **not** a "Rust vs Go for speed" choice — the two projects have
**diverged architecturally**:

- **`bd` (original, Steve Yegge)** moved to a **Dolt** backend (version-controlled SQL DB, embedded or
  server). The JSONL↔git sync was dropped; an engine/daemon dependency was added; the platform is
  actively migrating with regressions.
- **`br` (beads_rust)** **froze the "classic" SQLite + JSONL architecture**: a single static binary, no
  daemon, git-JSONL sync intact. Endorsed by Yegge; positioned as a stable snapshot.

> Note on confidence: specific figures from web research (stars, version numbers, issue IDs) are
> **unverified**. The decisive finding — the architectural split — is robust and matches what is
> already documented in `~/.claude/skills/br/references/INTEGRATION.md` ("Differences from bd (Go
> beads)", "binary is `br`, NEVER `bd`").

## Decision

**Stay on `br` (beads_rust). No migration.**

Reasons, specific to Apogee:

1. **Hooks fire on every action** → need sub-100ms cold start with no daemon. `bd`+Dolt adds per-call
   latency and deadlock risk; `br` is an instant static binary.
2. **Git-JSONL is core to the design** (`br-snapshot` commits `.beads/`). `bd` removed JSONL in favor
   of Dolt.
3. **`br robot-docs guide --no-db`** (static, DB-less mode) has no `bd` analog; switching would break
   `br-prime` on SessionStart/PreCompact.
4. **Infrastructure should be boring.** `br` is frozen-stable; `bd` is mid-Dolt-migration.
5. **Cost ≠ benefit.** The ~6 `br→bd` string swaps are trivial, but the move also brings data-format
   incompatibility (Dolt ≠ SQLite/JSONL), loss of `robot-docs --no-db`, and a new operational burden
   (Dolt) — for zero features this workflow needs.

## Revisit triggers

- A genuine need for **Linear/Jira sync** (an integration `bd` has and `br` does not), or
- **multi-writer Dolt branching** for concurrent multi-agent writes.

Neither applies to a solo workflow today.

## Consequences

- The `hooks/br/*` machinery stays as-is; `Bash(br:*)` remains in the allow-list.
- Apogee's tracker contract is the classic `.beads/` + `issues.jsonl` model, committed via git by the
  user (hooks never run git themselves).
