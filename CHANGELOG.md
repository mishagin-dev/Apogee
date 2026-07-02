# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.0] - 2026-07-02

### Fixed

- `idea/` enforcement hooks are now subagent-safe: an `is_subagent()` carve-out (reads `agent_id`/`agent_type`) short-circuits all five PreToolUse guards, since subagents lack `mcp__idea__*` and could previously deadlock. The activation nudge and force-activate now require a JetBrains project marker (`.idea/` or `*.iml`) instead of firing machine-wide, and `idea-usage-tracker` drops over-generic failure markers that could false-deactivate enforcement on legitimate file content. Adds a `--test` self-test, wired into `validate.sh`.

## [1.6.0] - 2026-06-21

### Added

- Edit gates now exempt git-ignored files (e.g. `docs/apogee/**`, `.claude/*`) and any `CLAUDE.md`, so bootstrap commands like `/apogee:init` are no longer blocked on a base branch in beads + git-flow projects. Exemption logic is centralized in `gate_common.path_exempt`.

### Fixed

- `br-branch-gate` Rule B (epic `external_ref` mismatch) called an undefined `_deny`, swallowing a `NameError` so the rule never denied; it now calls the imported `deny`.

## [1.5.0] - 2026-06-19

### Added

- `scripts/validate.sh` one-command repo health check (py/sh/json syntax, `${CLAUDE_PLUGIN_ROOT}` hook-path resolution, `idea_symbols` self-test) and a GitHub Actions CI gate.

### Fixed

- `setup.sh` aborts loudly when a settings `jq` merge fails, instead of printing a false success over stale JSON.
- `install.sh` refuses to `reset --hard` the toolkit clone when it has uncommitted local changes.

### Changed

- Deduplicated the shared hook helpers (`beads_root`, deny/ask builders) into `hooks/core/lib/gate_common.py`.
- Manifest descriptions now list the `doc`/`readme` skills and the `init` command.
- `/apogee:merge` notes that `git-flow`/`git-commit` are global skills and spells out the CHANGELOG version extraction.

## [1.4.0] - 2026-06-18

### Added

- `/apogee:readme` — gold-standard README generator (interview + battle-tested patterns, validated via `review-work`).
- `/apogee:doc` — professional human-facing documentation generator (feature/API reference, code-map, usage guides).
- CHANGELOG generation in the release flow (`/apogee:merge` Step 4b) from Conventional Commits since the last tag.

### Changed

- Completed `feature`/`bugfix` branches are finished through `/apogee:merge` (decompose rule extended).
- Operator model documented in the toolkit's own `CLAUDE.md`.
