# Apogee — developing the toolkit

This repo IS the toolkit (a Claude Code plugin + its GitHub marketplace), not a project that uses it.
Read `docs/ARCHITECTURE.md` first.

## Operator model

- **Solo, AI-agent-driven.** The user directs and reviews; Claude + sub-agents write the code. Build
  effort is cheap — the real cost is maintenance, debuggability, and decision overhead.
- **Judge by maintenance burden, not build effort.** "Too much code for a solo dev" is not a valid
  critique; pick architectures on technical merit.

## Critical rules

- **Beads stays inert; git-flow is enabled.** This repo has no `.beads/`, so the `br` machinery is a
  no-op here. git-flow IS configured: commit only on gitflow branches via the `git-flow` /
  `git-commit` skills. Since ADR 0005 nothing *blocks* a commit on `main`/`develop` — the rule holds
  because it's written here, not because a hook enforces it. A release (`git flow release`, tags
  `<version>`) spans `main` + `develop` + the tag — all three must be pushed together
  (`git push origin main develop --tags`), by you as usual.
- **Dogfooding is live; the plugin is installed from the GitHub marketplace.** `apogee@apogee`
  is enabled globally from `mishagin-dev/Apogee`, so it is live in this repo too. Consequence:
  editing this working tree does NOT change running sessions. Machinery changes only take effect
  after `git push`, then `/plugin marketplace update apogee` + `/reload-plugins`. To exercise a
  change before it ships, run `claude --plugin-dir plugins/apogee` in a sandbox project. Verify
  hook changes with `scripts/validate.sh` and `tests/`, not by expecting live behavior to shift.
  The ADR 0002 migration is complete: the legacy global ccdk hook block is gone from
  `~/.claude/settings.json`. Don't reintroduce a global hook block or per-throwaway-project caution.
- **Language split.** Dialogue with the user in the language Claude Code is configured with (the
  `language` setting), including the captions on tool calls; code,
  comments, commit messages, docs, branch names, and anything sent to external tools (`agy`) — in
  **English**. An English-heavy context is never a reason to answer in English.
- **Machinery vs content vs preferences** — respect the boundary (ADR 0002): hooks/skills go in
  `plugins/apogee/`; project templates in `scaffold/`; personal prefs stay in `~/.claude/settings.json`.

## Working on hooks

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
  rule belongs in a SKILL.md or `scaffold/CLAUDE.md`, not in a hook.
- Every hook must self-gate (no-op without `.beads/` / git-flow) and fail open. The
  one exception is Rule 2b, which fails *closed* precisely because it only runs unattended.
- After editing hooks, run `bash scripts/validate.sh` (py/sh/json syntax, `${CLAUDE_PLUGIN_ROOT}`
  hook-path resolution, the two `--test` self-tests, version lockstep, and the language-policy
  check; CI runs it too).

## Conventions

- Plugin/command/skill names are namespaced `/apogee:<name>`, including the four universal skills
  (`br`, `git-commit`, `git-flow`, `idea-mcp`), bundled under `plugins/apogee/skills/` since the
  ADR 0002 amendment (2026-07-07) — a project that installs the plugin gets them automatically, no
  separate global setup step. The old global `~/.claude/skills/` copies are left in place until
  manually cleaned up post-release (see the amendment for why).
- Tracker is `br` (beads_rust), not `bd` — ADR 0001. Don't reintroduce `bd` invocations.
- Apogee is its own project; CCDK (`peterkrueck/Claude-Code-Development-Kit`) is credited as the
  starting point it kept a couple of ideas from, and its copyright line stays in `LICENSE`. Never
  call Apogee a fork in docs or manifests.
- **Decompose complex work.** A complex task or a batch of bugs is split into separate git-flow
  features (one logical change == one `feature/`/`bugfix/` branch opened with `/apogee:start`), not
  crammed into one branch. Run them **sequentially** when they touch overlapping files (to avoid
  merge conflicts), or **in parallel** (separate branches/worktrees) when their file sets are
  disjoint. State the split and the chosen order before starting. When a branch's work is complete,
  close it with `/apogee:finish` (review, docs, clean tree, git-flow finish, push `develop`) — not
  hand-rolled merges. `/apogee:release` prepares a release and stops; the `release`/`hotfix`
  finish and the push of `main` + tags are the operator's, in a terminal (ADR 0007). Pushing
  `develop` and work branches is allowed.

## Decisions

Settled decisions live in `docs/decisions/` (ADRs). Don't relitigate them; cite the ADR instead.

## Don't

- In this repo, commit only when asked (the scaffold's pre-authorization for feature branches
  is for host projects, not the toolkit itself); never push. Commits go through the `git-commit`
  skill.
- Don't edit the user's global `~/.claude/` without explicit approval (it's machine-wide).
- Don't reintroduce per-project hook copying — machinery is the plugin, enabled not copied.
