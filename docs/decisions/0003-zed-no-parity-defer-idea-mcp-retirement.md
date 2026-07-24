# ADR 0003 — No Zed IDE-intelligence tooling; keep idea-mcp as-is pending a JetBrains decision

**Status:** Accepted · **Date:** 2026-07-23

## Context

The user is trialing the Zed editor in parallel with JetBrains IDEs and has not committed to
migrating off JetBrains. Apogee's `idea/` hook group and `apogee:idea-mcp` skill exist specifically
to gate/steer the agent onto `mcp__idea__*` tools (symbol search, inspections, refactor/format, run
configs, DB introspection, PHP/Symfony/Doctrine/Twig introspection, Xdebug) — roughly 60 tools — when
a JetBrains IDE with the MCP plugin is active. Before investing further in that machinery, or
considering a Zed-equivalent, the open question was: **does Zed have (or is it building) anything
that lets an external agent query the editor for the same class of IDE intelligence that idea-mcp
provides?**

**Research summary (conducted this session, 2026-07-23):** Zed has no parity today and no roadmap
signal that it's coming.

- Zed's Agent Client Protocol (ACP — co-developed with JetBrains, registry live since 2026-01-28)
  solves the **opposite** integration direction: it lets Zed *host* an external agent's UI (the agent
  runs as its own subprocess with its own tools). It does not let an external agent query Zed for
  editor-owned intelligence.
- Zed has no first-party MCP/context server exposing diagnostics, symbol search, structural
  search/replace, refactoring, run configurations, or debugger control. A DAP-based debugger exists
  in the UI but exposes no external control API. There is no built-in DB client at all (a DB viewer
  panel is an unmerged community fork).
- An open, unresolved GitHub discussion (`zed-industries/zed#58546`, June 2026) confirms that even
  agents embedded via ACP cannot read Zed's own diagnostics.
- The one third-party reverse-bridge attempt (`denisfl/zed-mcp`) is an unmaintained 2-commit
  proof-of-concept exposing ~5 basic tools (file read/write, list dir, git branch) — no diagnostics,
  symbols, refactor, debugger, or DB support.

> Note on durability: this finding is not persisted anywhere else in the repo — Apogee has no
> separate research-notes store (`docs/apogee/open-issues/` is currently an empty placeholder). This
> ADR's Context section *is* the durable record of the finding; treat it as the citation rather than
> expecting a linked write-up elsewhere. If Zed's ACP later grows an "editor as tool provider"
> capability, re-run this research rather than looking for a prior artifact.

## Decision

1. **Do not build Zed-replacement tooling now.** There is nothing for it to call: no diagnostics,
   symbol, refactor, run-config, debugger, or DB surface exposed by Zed to external agents.
2. **Keep the existing `idea/` hook group, `lib/idea_symbols.py`, the `apogee:idea-mcp` skill, and
   all associated doc/permission references exactly as they are.** They cost nothing to leave in
   place: every `idea/*` guard self-gates on `.idea/`/`*.iml` **and** a running JetBrains process
   (`has_idea_project()`), so on Zed-only work (no `.idea/`, no JetBrains process) the entire group is
   already inert — this is standing behavior, not new mitigation.
3. **Defer any retirement of the JetBrains/idea-mcp machinery to an explicit future trigger**, not to
   this ADR or to "Zed adoption" in the abstract. See the retirement checklist below.

**Trigger condition for retirement:** the user explicitly confirms the JetBrains → Zed migration is
complete and asks for the retirement to proceed. (An earlier draft of this ADR also considered
"JetBrains confirmed inactive in every working project" as an alternative trigger; a second-opinion
review flagged it as unverifiable — nothing can actually check IDE activity across unrelated
projects, and `.idea/` directories linger as harmless artifacts long after a project stops being
opened in JetBrains, so that clause would either never fire or require error-prone guessing. It was
dropped in favor of this single explicit-confirmation trigger.)

Until that confirmation, no `idea/`-related file should be deleted, renamed, or functionally changed
as a side effect of Zed work.

## Consequences

- No new engineering work follows from this ADR. It records a negative result (don't build) and a
  deferred action (retirement), not a feature.
- The `idea/` hook group, `apogee:idea-mcp` skill, `mcp__idea__*` baseline permissions
  (`setup.sh`, this repo's own `.claude/settings.local.json`), and every doc reference to JetBrains
  (`docs/apogee/ai-context/spec.md`, `docs/ARCHITECTURE.md`, `docs/HOOKS.md`, `docs/INSTALL.md`,
  `README.md`, `scaffold/CLAUDE.md`, `scripts/validate.sh`) remain unchanged by this ADR.
- A full, ordered retirement checklist is captured below, ready to trigger as its own git-flow
  `feature/` branch once the trigger condition is met — it is not executed as part of this change.
- When retirement eventually executes, it should be recorded as an **Amendment to this ADR** (dated,
  in the style of ADR 0002's amendments) rather than a new ADR, since it is the direct resolution of
  the decision recorded here — unless retirement also motivates a distinct new architectural decision
  (e.g. adopting a Zed-side tool once/if one matures), in which case that gets its own ADR and this
  one is amended to cross-reference it.
- If Zed's ACP later grows an external "editor as tool provider" capability (early pressure exists in
  `zed-industries/zed#58546` and `#52688`, but nothing shipped or announced as of this writing), this
  decision should be revisited — record that as a dated Amendment here too, not a fresh research
  cycle that ignores this one.

## Deferred: JetBrains / idea-mcp retirement checklist

**Trigger (must be true before starting):** the user explicitly confirms the JetBrains → Zed
migration is complete and asks for the retirement to proceed. Until then, do not start this
checklist — the `idea/` machinery is self-gated and inert on Zed-only work, so there is no urgency or
harm in leaving it as-is.

**Execution model when triggered:** run as its own git-flow feature branch (e.g.
`feature/retire-idea-mcp`), one logical change, per this repo's CLAUDE.md "Decompose complex work"
rule — do not fold this into an unrelated change.

**On stale references:** the steps below cite file locations current as of 2026-07-23. This document
may sit untouched for months before its trigger fires, and the codebase will have moved on — **locate
every reference by search anchor (hook filename, tool name, config key) via `grep -n` at execution
time; do not trust the line numbers below verbatim.** They are included only to show scope and
current state, not as a literal edit script.

Ordering matters: `validate.sh`'s self-tests and `hooks.json` path-resolution check (Stage 4) will
fail CI if hook files are deleted before their references are removed. The order below removes
references to a thing *before* deleting the thing, and removes CI's knowledge of a self-test *before*
the tested file disappears — nothing is left half-wired at any intermediate commit.

### Step 1 — Stop validate.sh from exercising idea-specific self-tests

- `scripts/validate.sh`: remove from the self-test list (currently ~line 122)
  `plugins/apogee/hooks/idea/lib/idea_symbols.py`, and from the `--test`-mode list (currently ~lines
  127-128) `idea-usage-tracker.py` and `idea-agent-guard.py`.
- `scripts/validate.sh`: update the Stage 5 header comment (currently ~lines 11-12) to drop the
  `idea_symbols.py` mention.
- Run `scripts/validate.sh` locally to confirm Stage 5 still passes with the reduced list before
  moving on.

### Step 2 — Unwire the hooks (stop them firing) before deleting the files

- `plugins/apogee/hooks/hooks.json`: remove every entry pointing at `hooks/idea/*`:
  - `PreToolUse` / `Grep` → `idea-symbol-guard.py`
  - `PreToolUse` / `Glob` → `idea-glob-guard.py`
  - `PreToolUse` / `Bash` → `idea-bash-grep-guard.py`
  - `PreToolUse` / `Read` → `idea-read-gate.py`
  - `PreToolUse` / `Agent` → `idea-agent-guard.py`
  - `PostToolUse` / `mcp__idea__.*` → `idea-usage-tracker.py`
  - `UserPromptSubmit` → `idea-nudge.py` (keep the sibling `unfinished-branch-nudge.py` entry in the
    same block)
  - `SessionStart` → `idea-force-activate.py` (keep the other commands in that block)
- Re-run `scripts/validate.sh` Stage 4 (hook-path resolution) — it should still pass since the files
  still exist but are no longer referenced.

### Step 3 — Delete the hook files and shared lib

- Delete `plugins/apogee/hooks/idea/` in full: `idea-force-activate.py`, `idea-symbol-guard.py`,
  `idea-glob-guard.py`, `idea-bash-grep-guard.py`, `idea-read-gate.py`, `idea-agent-guard.py`,
  `idea-nudge.py`, `idea-usage-tracker.py`, `lib/idea_symbols.py`, and the `__pycache__/` alongside
  them.
- Re-run `scripts/validate.sh` in full (all stages) to confirm nothing dangling remains.

### Step 4 — Delete the skill

- Delete `plugins/apogee/skills/idea-mcp/` in full (`SKILL.md` + the stray `.DS_Store`).
- Update `plugins/apogee/.claude-plugin/plugin.json`'s `description` field — it currently lists
  `idea-mcp` among the bundled skills; drop it from the enumeration.
- **Re-run `scripts/validate.sh` again immediately after this step**, not just at the very end in
  Step 9, to catch any remaining hardcoded reference to the deleted skill before it compounds with
  the doc/permission edits in Steps 5-7.
- Grep `setup.sh` and `sync.sh` for any reference to the `idea-mcp` skill path itself (as opposed to
  the `mcp__idea__*` permission string handled in Step 5). Skills are plugin-bundled rather than
  scaffold-copied, so this is expected to find nothing — confirm rather than assume, since a stale
  reference here would silently break onboarding for new projects.

### Step 5 — Strip baseline permissions

- `setup.sh` (currently ~line 196): remove `"mcp__idea__*"` from the `--argjson baseline` array
  passed to `jq`. Also update the two explanatory comments above it (currently ~lines 19, 183) that
  name "idea" as one of the MCP servers the toolkit nudges the agent toward.
- This repo's own `.claude/settings.local.json`: remove `"mcp__idea__*"` from `permissions.allow`
  (this file is git-excluded/personal, so this edit does not go through a PR, but do it for
  consistency with what `setup.sh` will now write to *other* projects).
- Note for the user at execution time: existing `TARGET/.claude/settings.local.json` files in other
  projects (written by a prior `setup.sh` run) will still carry `mcp__idea__*` — this cleanup only
  changes what *future* `setup.sh`/`sync.sh` runs write; it does not retroactively edit
  already-scaffolded projects. Decide at that time whether a one-off cleanup pass across those
  projects is warranted.

### Step 6 — Update scaffold content (affects all future newly-scaffolded projects)

- `scaffold/CLAUDE.md` (currently ~line 16): remove the "idea-mcp first" bullet from Critical Rules.
- `scaffold/CLAUDE.md` (currently ~line 75): remove the "Code intelligence / refactoring (JetBrains)"
  row from the Tool Usage Rules table.
- Not urgent to do before the trigger fires: this text is already conditional ("only when the
  JetBrains IDE MCP is connected... ignore entirely when the IDE is absent"), so it doesn't mis-fire
  in Zed-only projects during any transition period — it's just dead text until retirement.

### Step 7 — Update documentation tables/prose

- `docs/apogee/ai-context/spec.md`: drop the `.idea/` + running-IDE clause from the self-gating
  sentence; drop `idea-mcp` from the bundled-skills row; remove the `idea/` row from the hooks-group
  table; drop `idea` from the workflow-loop sentence.
- `docs/ARCHITECTURE.md`: remove the `idea/` line from the repo-tree diagram; drop `idea-mcp` from
  the skills enumeration; remove the idea-guards import-anchoring example (or replace with a
  surviving example, e.g. `br` hooks); remove the `.idea/` + running-IDE self-gating bullet; drop
  `idea` from the workflow-loop sentence.
- `docs/HOOKS.md`: remove all `idea/*` rows from the PreToolUse/PostToolUse/UserPromptSubmit tables,
  and the `.idea/` + IDE bullet + `IDEA_GATE_OFF=1` escape-hatch line from the self-gating summary.
- `README.md`: remove "idea" from the hooks-directory comment; remove `.idea/` + running-IDE from the
  "Gates self-gate" sentence; drop `IDEA_GATE_OFF=1` from the escape-hatches list.
- `docs/INSTALL.md`: remove `mcp__idea__*` from the baseline-permissions description.
- `docs/apogee/ai-context/project-structure.md`: remove the `mcp__idea__*` row from the MCP servers
  table; drop `idea/` from the gate-groups directory comment; drop `idea-mcp` from the bundled-skills
  comment.
- `CHANGELOG.md`: do **not** edit historical entries — they document what was true at the time and
  are an accurate record. Instead add a **new** entry under the next release heading, e.g. under
  "Removed": "JetBrains/idea-mcp tooling (`hooks/idea/`, `skills/idea-mcp/`, baseline `mcp__idea__*`
  permissions) retired per ADR 0003 — JetBrains fully replaced by Zed in the user's workflow."

### Step 8 — Record the retirement decision

- Add a **dated Amendment to this ADR** stating retirement executed, citing that the user's explicit
  confirmation triggered it, and linking the CHANGELOG entry from Step 7.
- If ADR 0002's baseline-permissions Amendment (2026-06-17) still names `mcp__idea__*` as live
  rationale, add a short cross-reference there too ("superseded for `idea`, see ADR 0003 amendment")
  rather than rewriting that historical amendment.

### Step 9 — Final validation and merge

- Run `scripts/validate.sh` end-to-end (all stages) on the feature branch.
- Bump `plugins/apogee/.claude-plugin/plugin.json` version and the matching marketplace/CHANGELOG
  version header, per the existing release convention.
- Finish the branch through the normal git-flow release process used elsewhere in this repo (see the
  `merge`/`release` command conventions already in place) — not a hand-rolled merge.
