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
| `PreToolUse` / `mcp__.*`, `WebFetch`, `WebSearch`, `Bash` | `core/security-scan.sh` | **DENY** when the outbound payload contains a high-confidence credential | always for MCP and web tools; on `Bash` only for `agy` invocations |
| `PreToolUse` / `Bash` | `git/enforce-git-flow-skill.py` | **ASK** on `git flow release\|hotfix finish`; **DENY** an `APOGEE_RUN_PLAN=1`-tagged `feature\|bugfix finish` while the linked br epic has open steps | git-flow config |

**`security-scan.sh`** walks the entire `tool_input` (`jq -r '..|strings'`), one string value per
line, capped at 256 KB. Patterns live in `config/sensitive-patterns.json` and are high-confidence
only — vendor-prefixed tokens, PEM headers, credential-bearing URLs — plus a placeholder filter
applied to the matched token, so `postgres://user:password@localhost` and AWS's own
`AKIAIOSFODNN7EXAMPLE` stay quiet. This is precision over recall by design: a scanner that fires on
`password: str` gets switched off, and a switched-off scanner has zero recall. It covers every
surface this toolkit uses to hand data to an external service: MCP servers, `WebFetch`/`WebSearch`,
and the `agy` CLI (the second-opinion skill pipes code through a heredoc, which is part of the Bash
command string and therefore scanned). Other Bash commands are skipped. `--test` covers the pattern
cases and the `agy` detection.

**`enforce-git-flow-skill.py`** Rule 2b is the one deliberate **fail-closed** path in the toolkit: if
`br` cannot be queried, a tagged autonomous finish is refused rather than allowed. It applies *only*
to commands tagged `APOGEE_RUN_PLAN=1` by `/apogee:run-plan`. An interactive finish gets no check at
all — a human is present, and the failure it guards (tracker drift) is one `br update` to fix. An
unattended loop has no such backstop, which is exactly the test ADR 0005 uses for what earns a gate:
*is the outcome irreversible, and is a human present to catch it.* `--test` covers both rules;
`tests/smoke-run-plan.sh` drives the real script against real `br` + `git flow` sandboxes.

## Context hooks

| Event | Script | What it injects | Self-gate |
|---|---|---|---|
| `PostToolUse` / `ExitPlanMode` | `br/br-capture-gate.py` | Record the approved plan in `br` (epic + steps); in git-flow repos, hand execution to `/apogee:run-plan`. Silent when `tool_response` says the plan was not accepted | `.beads/` |
| `UserPromptSubmit` | `git/unfinished-branch-nudge.py` | Reminder (≤3/session) that a `feature/`/`bugfix/` branch is still open — or already merged into develop and just needs `git flow … finish` to delete it | git-flow config + an open branch |
| `SessionStart` | `core/apogee-session-start.py` | Re-asserts the AI-tooling exclude list (`config/exclude-list.txt`) in `.git/info/exclude` for the repo root and each first-level submodule, silently; then, on `startup`/`clear`, a directive to run `/apogee:prime` in a managed project | `docs/apogee/` for the excludes; `.beads/` + `docs/apogee/` for the directive |
| `SessionStart`, `PreCompact` | `br/br-prime.sh` | `br robot-docs guide --no-db`, so beads context survives compaction | `.beads/` |
| `SessionEnd` | `core/cleanup-session.sh` | Removes the per-session nudge counter | — |

Retired context hooks: `idea/idea-nudge.py` (the JetBrains MCP server and JetBrains' own plugin
describe their tools themselves; the one rule that mattered — load a schema with `ToolSearch`
first, use the tools only where the shell has no equivalent — is a line in `scaffold/CLAUDE.md`
§1) and `core/notify.sh` (Claude Code's own `inputNeededNotifEnabled` setting plays the cue).

## Triggers (summary)

- **`.beads/`** → `br-capture-gate`, `br-prime`.
- **git-flow config** → `enforce-git-flow-skill`, `unfinished-branch-nudge`.
- **`mcp__` tool call, `WebFetch`, `WebSearch`, `agy` via Bash** → `security-scan.sh`.

A project is **Apogee-managed** when it has `.beads/` **and** `docs/apogee/` at the same root.

There are no escape-hatch environment variables. `BR_GATE_OFF`, `REVIEW_GATE_OFF`, `IDEA_GATE_OFF`
and `TOOL_LANG_OFF` were removed with the gates they disabled; nothing reads them.

## Configuration

None. `hooks/core/config/sensitive-patterns.json` is the scanner's pattern list; the former
`pipeline.json` is gone — `/apogee:run-plan` takes its cap from `$ARGUMENTS` and its test gate from
the project's `CLAUDE.md` Testing section.
