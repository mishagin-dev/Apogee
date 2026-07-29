# Apogee — Hook catalog

Every hook is wired in `plugins/apogee/hooks/hooks.json`, referenced via `${CLAUDE_PLUGIN_ROOT}`,
and fires only when the plugin is enabled. All of them **self-gate** (no-op unless the trigger
column is satisfied) and **fail open** (any parse/IO error exits 0, never blocking).

**Only two hooks can block anything** — see [ADR 0005](decisions/0005-enforcement-safety-only.md) for
why the other eleven gates were removed. The rest inject context: directives, reminders, priming.
Rules that used to be enforced now live in `scaffold/CLAUDE.md` §1 and the skills; they are still
rules, they just aren't walls.

## Blocking hooks (2)

| Event / matcher | Script (`hooks/…`) | Decision | Self-gate |
|---|---|---|---|
| `PreToolUse` / `mcp__` | `core/security-scan.sh` | **DENY** when the outbound payload contains a high-confidence credential | always (matches `mcp__`) |
| `PreToolUse` / `Bash` | `git/enforce-git-flow-skill.py` | **ASK** on `git flow release\|hotfix finish`; **DENY** an `APOGEE_RUN_PLAN=1`-tagged `feature\|bugfix finish` while the linked br epic has open steps | git-flow config |

**`security-scan.sh`** walks the entire `tool_input` (`jq -r '..|strings'`), one string value per
line, capped at 256 KB. Patterns live in `config/sensitive-patterns.json` and are high-confidence
only — vendor-prefixed tokens, PEM headers, credential-bearing URLs — plus a placeholder filter
applied to the matched token, so `postgres://user:password@localhost` and AWS's own
`AKIAIOSFODNN7EXAMPLE` stay quiet. This is precision over recall by design: a scanner that fires on
`password: str` gets switched off, and a switched-off scanner has zero recall. `--test` covers 18
cases (8 must fire, 10 must not).

**`enforce-git-flow-skill.py`** Rule 2b is the one deliberate **fail-closed** path in the toolkit: if
`br` cannot be queried, a tagged autonomous finish is refused rather than allowed. It applies *only*
to commands tagged `APOGEE_RUN_PLAN=1` by `/apogee:run-plan`. An interactive finish gets no check at
all — a human is present, and the failure it guards (tracker drift) is one `br update` to fix. An
unattended loop has no such backstop, which is exactly the test ADR 0005 uses for what earns a gate:
*is the outcome irreversible, and is a human present to catch it.* `--test` covers both rules.

## Context hooks

| Event | Script | What it injects | Self-gate |
|---|---|---|---|
| `PostToolUse` / `ExitPlanMode` | `br/br-capture-gate.py` | Record the approved plan in `br` (epic + steps); in git-flow repos, hand execution to `/apogee:run-plan` | `.beads/` |
| `UserPromptSubmit` | `idea/idea-nudge.py` | Reminder (≤3/session) to prefer `mcp__idea__*` over grep + whole-file reads | `.idea/` or `.iml` + running IDE |
| `UserPromptSubmit` | `git/unfinished-branch-nudge.py` | Reminder (≤3/session) that a `feature/`/`bugfix/` branch is still open — or already merged into develop and just needs `git flow … finish` to delete it | git-flow config + an open branch |
| `SessionStart` | `core/apogee-session-start.py` | Directive to run `/apogee:prime` in a managed project | `.beads/` + `docs/apogee/` |
| `SessionStart`, `PreCompact` | `br/br-prime.sh` | `br robot-docs guide --no-db`, so beads context survives compaction | `.beads/` |
| `Notification` | `core/notify.sh input` | Cross-platform audio cue when Claude needs input (`sounds/`) | — |
| `SessionEnd` | `core/cleanup-session.sh` | Removes the two per-session nudge counters | — |

## Triggers (summary)

- **`.beads/`** → `br-capture-gate`, `br-prime`.
- **`.idea/` or `*.iml` + a running JetBrains IDE** → `idea-nudge`.
- **git-flow config** → `enforce-git-flow-skill`, `unfinished-branch-nudge`.
- **`mcp__` tool call** → `security-scan.sh` (unconditional).

A project is **Apogee-managed** when it has `.beads/` **and** `docs/apogee/` at the same root.

There are no escape-hatch environment variables. `BR_GATE_OFF`, `REVIEW_GATE_OFF`, `IDEA_GATE_OFF`
and `TOOL_LANG_OFF` were removed with the gates they disabled; nothing reads them.

## Configuration

`hooks/core/config/pipeline.json` holds `run_plan.max_epics_per_invocation` (the autonomous-loop
circuit breaker) and `run_plan.test_command`. That is all it holds — the review thresholds and the
`file_patterns` list went with their consumers.
