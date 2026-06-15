# Apogee — developing the toolkit

This repo IS the toolkit (a Claude Code plugin + local marketplace), not a project that uses it.
Read `docs/ARCHITECTURE.md` first.

## Critical rules

- **Bootstrap stays inert.** Keep this repo WITHOUT `.beads/` and WITHOUT git-flow config so Apogee's
  own gates self-gate to no-op while you build. If you add `.beads/`, develop with escape envs:
  `BR_GATE_OFF=1 REVIEW_GATE_OFF=1 IDEA_GATE_OFF=1 TOOL_LANG_OFF=1`.
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
- After editing hooks: `python3 -m py_compile` the `.py`, `bash -n` the `.sh`, `jq empty` the JSON, and
  verify every `${CLAUDE_PLUGIN_ROOT}` path in `hooks.json` resolves to an existing file.

## Conventions

- Plugin/command/skill names are namespaced `/apogee:<name>`. Universal skills (`br`, `git-commit`,
  `git-flow`, `idea-mcp`) intentionally stay GLOBAL in `~/.claude/skills/` (bare names).
- Tracker is `br` (beads_rust), not `bd` — ADR 0001. Don't reintroduce `bd` invocations.
- Attribution to upstream (`peterkrueck/Claude-Code-Development-Kit`) stays; the system name is Apogee.

## Decisions

Settled decisions live in `docs/decisions/` (ADRs). Don't relitigate them; cite the ADR instead.

## Don't

- Don't commit unless asked; never push. Commits go through the `git-commit` skill.
- Don't edit the user's global `~/.claude/` without explicit approval (it's machine-wide).
- Don't reintroduce per-project hook copying — machinery is the plugin, enabled not copied.
