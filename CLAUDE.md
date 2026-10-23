# Apogee — developing the toolkit

<!-- This file holds THIS project's facts, decisions and exceptions, and nothing else.
     Apogee's general rules (work loop, git, files, tools, code standards) and its tone come from
     the plugin itself (rules/RULES.md and rules/SOUL.md), injected at every session start, and
     update with the plugin. Anything written here overrides them for this project.
     Written by /apogee:init, kept current by /apogee:update-docs; Apogee never rewrites it on
     update. -->

## 1. Project

This repo IS the toolkit (a Claude Code plugin + its GitHub marketplace), not a project that uses it.
Read `docs/ARCHITECTURE.md` first.

## 2. Operator Model

- **Solo, AI-agent-driven.** The user directs and reviews; Claude + sub-agents write the code. Build
  effort is cheap — the real cost is maintenance, debuggability, and decision overhead.
- **Judge by maintenance burden, not build effort.** "Too much code for a solo dev" is not a valid
  critique; pick architectures on technical merit.

## 3. Key Architecture Decisions

Settled decisions live in `docs/decisions/` (ADRs). Don't relitigate them; cite the ADR instead.

- **Toolkit rules live in the plugin** (ADR 0009): `plugins/apogee/rules/RULES.md` (work loop,
  git, files, tools, code) and `SOUL.md` (tone, honesty, restraint), injected at session start.
  `scaffold/CLAUDE.md` is a project-only template; never put a general rule there.
- **Machinery vs content vs preferences** — respect the boundary (ADR 0002): hooks/skills go in
  `plugins/apogee/`; project templates in `scaffold/`; personal prefs stay in `~/.claude/settings.json`.

## 4. Project Rules

- **Beads stays inert; git-flow is enabled.** This repo has no `.beads/`, so the `br` machinery is a
  no-op here. git-flow IS configured. A release (`git flow release`, tags `<version>`) spans
  `main` + `develop` + the tag — all three must be pushed together
  (`git push origin main develop --tags`), by you as usual.
- **Dogfooding is live; the plugin is installed from the GitHub marketplace.** `apogee@apogee`
  is enabled globally from `mishagin-dev/Apogee`, so it is live in this repo too. Consequence:
  editing this working tree does NOT change running sessions. Machinery changes only take effect
  after `git push`, then `/plugin marketplace update apogee` + `/reload-plugins`. To exercise a
  change before it ships, run `claude --plugin-dir plugins/apogee` in a sandbox project. Verify
  hook changes with `scripts/validate.sh` and `tests/`, not by expecting live behavior to shift.
  The ADR 0002 migration is complete: the legacy global ccdk hook block is gone from
  `~/.claude/settings.json`. Don't reintroduce a global hook block or per-throwaway-project caution.
- Plugin/command/skill names are namespaced `/apogee:<name>`, including the four universal skills
  (`br`, `git-commit`, `git-flow`, `idea-mcp`), bundled under `plugins/apogee/skills/` since the
  ADR 0002 amendment (2026-07-07) — a project that installs the plugin gets them automatically, no
  separate global setup step. The old global `~/.claude/skills/` copies are left in place until
  manually cleaned up post-release (see the amendment for why).
- Tracker is `br` (beads_rust), not `bd` — ADR 0001. Don't reintroduce `bd` invocations.
- Apogee is its own project; CCDK (`peterkrueck/Claude-Code-Development-Kit`) is credited as the
  starting point it kept a couple of ideas from, and its copyright line stays in `LICENSE`. Never
  call Apogee a fork in docs or manifests.
- In this repo, commit only when asked (the scaffold's pre-authorization for feature branches
  is for host projects, not the toolkit itself). Commits go through the `git-commit` skill.
- Don't edit the user's global `~/.claude/` without explicit approval (it's machine-wide).
- Don't reintroduce per-project hook copying — machinery is the plugin, enabled not copied.

### Working on hooks

- All hook commands in `plugins/apogee/hooks/hooks.json` must use `${CLAUDE_PLUGIN_ROOT}/hooks/<group>/…`.
- Python hooks: anchor internal imports on `os.path.dirname(os.path.abspath(__file__))`, never on CWD or
  `${CLAUDE_PLUGIN_ROOT}` inside sub-scripts. A hook's helpers live in its own group dir
  (`hooks/git/lib/`). There is no shared cross-group lib any more — `hooks/core/lib/` was dissolved
  by ADR 0005 once its consumers went. If exactly one hook needs a helper, inline it; only bring a
  shared dir back when a *third* consumer actually appears.
- **The blocking surface is deliberately two hooks** (ADR 0005): `core/security-scan.sh` (DENY —
  secrets to external MCP servers) and `git/enforce-git-flow-skill.py` (DENY on `release|hotfix
  finish`, on any push/merge/tag touching `main` or tags, and on an `APOGEE_RUN_PLAN=1`-tagged
  finish with open epic steps). Everything else is
  context — nudges and injected directives. Before adding a gate, answer both questions ADR 0005
  used: *is the outcome irreversible*, and *is a human present to catch it*. If either is "no", the
  rule belongs in a SKILL.md or `plugins/apogee/rules/RULES.md`, not in a hook.
- Every hook must self-gate (no-op without `.beads/` / git-flow) and fail open. The
  one exception is Rule 2b, which fails *closed* precisely because it only runs unattended.

## 5. Testing

- After editing hooks, run `bash scripts/validate.sh` (py/sh/json syntax, `${CLAUDE_PLUGIN_ROOT}`
  hook-path resolution, the two `--test` self-tests, version lockstep, and the language-policy
  check; CI runs it too).

## 6. Privacy & Security

<!-- No project-specific security rules beyond the plugin's hooks (see §4, Working on hooks). -->

## 7. Bilingual Documentation

<!-- Not applicable: the project's docs ship in English only. -->
