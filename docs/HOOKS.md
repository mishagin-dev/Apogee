# Apogee — Hook catalog

Every hook is wired in `plugins/apogee/hooks/hooks.json` and fires only when its plugin is enabled.
All gate hooks **self-gate** (no-op unless the trigger column is satisfied) and **fail open** (any
parse/IO error exits 0, never blocking) — the one deliberate exception is
`git/enforce-git-flow-skill.py`'s open-children check, which fails **closed** specifically for
`APOGEE_RUN_PLAN=1`-tagged autonomous finishes (see that row below): an unattended safety backstop
that failed open on its own infra errors would defeat its entire purpose. Scripts are referenced via
`${CLAUDE_PLUGIN_ROOT}`.

## By lifecycle event

### PreToolUse

| Matcher | Script (`hooks/…`) | What it does | Self-gate | Escape |
|---|---|---|---|---|
| `Bash` | `git/enforce-git-commit-skill.py` | Only `git commit -F <file>` / `--amend --no-edit` allowed; blocks ad-hoc `git commit -m` | any `git commit` | use the `git-commit` skill |
| `Bash` | `git/enforce-git-flow-skill.py` | ASK on `release`/`hotfix finish`; ASK on `feature`/`bugfix start` while another such branch is still open (bypassed when the command is tagged `APOGEE_RUN_PLAN=1`); DENY `feature`/`bugfix finish` when the linked br epic still has open steps (fail-open on a br query error for a plain manual finish, fail-**closed** when the command is `APOGEE_RUN_PLAN=1`-tagged — the /apogee:run-plan autonomous-execution safety backstop); deny commits/merges off git-flow branches | git-flow config | — |
| `Bash` | `lang/tool-lang-guard.py` | Deny an `agy`/`gemini` command whose prompt contains Cyrillic (external AI is a tool → English) | command invokes `agy`/`gemini` | `TOOL_LANG_OFF=1` |
| `Bash` | `idea/idea-bash-grep-guard.py` | Deny `grep`/`rg`/`ag`/`ack` used for symbol search (use idea-mcp) | `.idea/` + IDE | `IDEA_GATE_OFF=1` |
| `Grep` | `idea/idea-symbol-guard.py` | Deny native symbol search via Grep | `.idea/` + IDE | `IDEA_GATE_OFF=1` |
| `Glob` | `idea/idea-glob-guard.py` | Deny glob patterns used for symbol search | `.idea/` + IDE | `IDEA_GATE_OFF=1` |
| `Read` | `idea/idea-read-gate.py` | Budget blind full-file **code** reads (free: offset/limit, non-code, meta paths) | `.idea/` + IDE | `IDEA_GATE_OFF=1` |
| `Agent` | `idea/idea-agent-guard.py` | Deny subagent raw code search without idea-mcp | `.idea/` + IDE | `IDEA_GATE_OFF=1` |
| `mcp__` | `core/security-scan.sh` | Scan outbound MCP payloads for secrets (`config/sensitive-patterns.json`) | always (matches `mcp__`) | — |
| `Edit\|Write\|MultiEdit\|NotebookEdit` | `br/br-edit-gate.py` | Deny code edit when no `br` issue is `in_progress` | `.beads/` | `BR_GATE_OFF=1` |
| `Edit\|Write\|MultiEdit\|NotebookEdit` | `br/br-branch-gate.py` | Deny edits off a `feature/`/`bugfix/` branch linked to the active epic (submodule-aware: checks whichever repo actually contains the edited file, not the outer `.beads/` root) | `.beads/` + git-flow | `BR_GATE_OFF=1` |

### PostToolUse

| Matcher | Script | What it does | Self-gate |
|---|---|---|---|
| `mcp__idea__.*` | `idea/idea-usage-tracker.py` | Mark idea-mcp enforcement CONFIRMED on first successful idea call | `.idea/` + IDE |
| `ExitPlanMode` | `br/br-capture-gate.py` | Seed the approved plan into `br` (epic + steps) before edits; in git-flow repos, hand off execution to `/apogee:run-plan` instead of the agent implementing by hand | `.beads/` |
| `Skill` | `review/skill-run-tracker.py` | Drop markers when `/…:review-work` / `/…:update-docs` run (tolerant of plugin namespacing) | always |
| `Edit\|Write\|MultiEdit\|NotebookEdit` | `review/track-file-touch.sh` | Log touched files to a per-session manifest, scoping `review-docs-gate`'s diff | always |

### UserPromptSubmit

| Script | What it does | Self-gate |
|---|---|---|
| `idea/idea-nudge.py` | Soft reminder (≤3/session) to make the first idea-mcp call | `.idea/` or `.iml` + IDE |
| `git/unfinished-branch-nudge.py` | Soft reminder (≤3/session) that a `feature/`/`bugfix/` branch is still open, or already fully merged into develop and just needs `git flow ... finish` to delete it | git-flow config + an open branch |

### Stop

| Script | What it does | Self-gate | Escape |
|---|---|---|---|
| `review/review-docs-gate.sh` | HARD-block session end until `/…:review-work` then `/…:update-docs` ran (marker-verified, ordered); diff is scoped to this session's touched-file manifest, so other sessions'/pre-existing dirty state never counts | `.beads/` + diff ≥ threshold | `REVIEW_GATE_OFF=1` |
| `br/br-progress-gate.sh` | Block if code changed but `br` state didn't (via `br-sig.py` signature) | `.beads/` | `BR_GATE_OFF=1` |

### Notification

| Script | What it does |
|---|---|
| `core/notify.sh input` | Cross-platform audio cue when Claude needs input (`config/`, `sounds/`) |

### PreCompact

| Script | What it does | Self-gate |
|---|---|---|
| `br/br-prime.sh` | Re-inject `br robot-docs guide --no-db` so the agent keeps beads context after compaction | `.beads/` |

### SessionStart

| Script | What it does | Self-gate |
|---|---|---|
| `core/gated.sh core/snapshot-baseline.sh` | Capture a git diff baseline for the Stop gate | `.beads/` + `docs/apogee/` |
| `core/apogee-session-start.py` | Inject a directive to run `/apogee:prime` in a managed project | `.beads/` + `docs/apogee/` |
| `br/br-prime.sh` | Inject the beads agent guide | `.beads/` |
| `br/br-snapshot.sh` | Snapshot `br` state signature (baseline for the progress gate) | `.beads/` |
| `idea/idea-force-activate.py` | Arm idea-mcp enforcement (tentative) when `.idea/`/`.iml` + IDE present | `.idea/` or `.iml` + IDE |

### SessionEnd

| Script | What it does |
|---|---|
| `core/cleanup-session.sh` | Remove per-session temp files (`/tmp/claude-*`) |

## Triggers & escape hatches (summary)

- **`.beads/`** present → the `br/*` gates + `review-docs-gate` engage. Escape: `BR_GATE_OFF=1`,
  `REVIEW_GATE_OFF=1`.
- **`.idea/` + running JetBrains IDE** → the `idea/*` guards engage. Escape: `IDEA_GATE_OFF=1`;
  per-project opt-out: `~/.claude/hooks/idea-enforce.json` (machine-level config, kept global).
- **git-flow config** → `enforce-git-flow-skill` + `br-branch-gate` engage.
- **external-AI CLI** (`agy`/`gemini`) → `tool-lang-guard`. Escape: `TOOL_LANG_OFF=1`.

A project is **Apogee-managed** when it has `.beads/` **and** `docs/apogee/` at the same root.
