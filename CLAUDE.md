# Apogee — developing the toolkit

This repo IS the toolkit (a Claude Code plugin + local marketplace), not a project that uses it.
Read `docs/ARCHITECTURE.md` first.

## Operator model

- **Solo, AI-agent-driven.** The user directs and reviews; Claude + sub-agents write the code. Build
  effort is cheap — the real cost is maintenance, debuggability, and decision overhead.
- **Judge by maintenance burden, not build effort.** "Too much code for a solo dev" is not a valid
  critique; pick architectures on technical merit.

## Critical rules

- **Beads stays inert; git-flow is enabled.** Keep this repo WITHOUT `.beads/` so the `br` gates
  self-gate to no-op while you build (if you add it, develop with escape envs:
  `BR_GATE_OFF=1 REVIEW_GATE_OFF=1 IDEA_GATE_OFF=1 TOOL_LANG_OFF=1`). git-flow IS configured: commit
  only on gitflow branches via the `git-flow`/`git-commit` skills (the gate denies commits on
  `main`/`develop`). A release (`git flow release`, tags `<version>`) spans `main` + `develop` + the
  tag — all three must be pushed together (`git push origin main develop --tags`), by you as usual.
- **Don't dogfood until stable.** Don't enable the `apogee` plugin globally until it's validated on a
  throwaway project (see `docs/INSTALL.md` + ADR 0002). Strip the global `~/.claude/settings.json`
  hooks block LAST.
- **Language split.** Dialogue with the user in their language; code, comments, commit messages, docs,
  branch names, and anything sent to external tools (`agy`) — in **English**.
- **Machinery vs content vs preferences** — respect the boundary (ADR 0002): hooks/commands/skills go in
  `plugins/apogee/`; project templates in `scaffold/`; personal prefs stay in `~/.claude/settings.json`.

## Working on hooks

- All hook commands in `plugins/apogee/hooks/hooks.json` must use `${CLAUDE_PLUGIN_ROOT}/hooks/<group>/…`.
- Python hooks: anchor internal imports on `os.path.dirname(os.path.abspath(__file__))`, never on CWD or
  `${CLAUDE_PLUGIN_ROOT}` inside sub-scripts. Keep a hook's helpers in its own group dir (e.g.
  `hooks/idea/lib/`, `hooks/br/br-sig.py`).
- Every gate must self-gate (no-op without `.beads/` / `.idea/`+IDE / git-flow) and fail open.
- After editing hooks, run `bash scripts/validate.sh` (py/sh/json syntax, `${CLAUDE_PLUGIN_ROOT}`
  hook-path resolution, and the `idea_symbols` self-test; CI runs it too).

## Conventions

- Plugin/command/skill names are namespaced `/apogee:<name>`. Universal skills (`br`, `git-commit`,
  `git-flow`, `idea-mcp`) intentionally stay GLOBAL in `~/.claude/skills/` (bare names).
- Tracker is `br` (beads_rust), not `bd` — ADR 0001. Don't reintroduce `bd` invocations.
- Attribution to upstream (`peterkrueck/Claude-Code-Development-Kit`) stays; the system name is Apogee.
- **Decompose complex work.** A complex task or a batch of bugs is split into separate git-flow
  features (one logical change == one `feature/`/`bugfix/` branch via the `git-flow` skill), not
  crammed into one branch. Run them **sequentially** when they touch overlapping files (to avoid
  merge conflicts), or **in parallel** (separate branches/worktrees) when their file sets are
  disjoint. State the split and the chosen order before starting. When a branch's work is complete,
  finish it through `/apogee:merge` (docs/clean-tree guardrails, then delegates to the git-flow
  finish) — not hand-rolled merges; `release`/`hotfix` finish only on explicit request.

## Decisions

Settled decisions live in `docs/decisions/` (ADRs). Don't relitigate them; cite the ADR instead.

## Don't

- Don't commit unless asked; never push. Commits go through the `git-commit` skill.
- Don't edit the user's global `~/.claude/` without explicit approval (it's machine-wide).
- Don't reintroduce per-project hook copying — machinery is the plugin, enabled not copied.
