# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.9.0] - 2026-07-07

### Added

- New `/apogee:release` command owns the Apogee release lifecycle end to end: decides the SemVer bump from Conventional Commits since the last tag, bumps `plugin.json` and `marketplace.json` in lockstep, refreshes this changelog, and gates on `scripts/validate.sh` before committing — then stops and surfaces the exact `git flow release|hotfix finish` for you to run. `/apogee:merge`'s release/hotfix path now defers to it instead of generating the changelog itself.
- `scripts/validate.sh` gained a Stage 6 that fails CI if `plugin.json`, `marketplace.json`, and this changelog's top entry disagree — a hard backstop for the version lockstep.

### Changed

- The universal skills `br`, `git-commit`, `git-flow`, and `idea-mcp` are now bundled inside the plugin (`plugins/apogee/skills/`), namespaced `apogee:<name>`, instead of living only in `~/.claude/skills/` — a project that installs `apogee` now gets them automatically. ADR 0002 amended accordingly.

## [1.8.1] - 2026-07-04

### Fixed

- Removed the redundant `hooks` key from `plugin.json` — the plugin loader auto-loads `hooks/hooks.json` by convention, so declaring it in the manifest too caused a "Duplicate hooks file detected" load error on `/reload-plugins`.

## [1.8.0] - 2026-07-04

### Added

- br edit/branch gates now exempt non-code files (docs, markdown, configs, images) via a new `gate_common.is_code_file`, so service commands (`/apogee:update-docs`, `/apogee:readme`, `/apogee:doc`, image-*) and ordinary doc/config edits pass on base branches without a br step or a git-flow work branch; code edits stay fully enforced.

### Changed

- Removed a stale `README.md` note about cleaning up the `Maestro/` bootstrap folder — it no longer exists.

## [1.7.1] - 2026-07-03

### Fixed

- `/apogee:init` no longer treats scaffold stub docs (the `<!-- apogee:scaffold-stub -->` placeholders) as already-filled project context — stubs now count as missing, so `init` replaces them with real project context instead of skipping.
- The `git-commit` and `git-flow` enforcement hooks no longer false-match git operations mentioned inside another command's quoted/heredoc payload (e.g. an `agy` prompt discussing `git commit`). Payloads are now stripped before matching, so `/apogee:second-opinion` and similar tool calls are no longer blocked on `develop`.
- `idea-agent-guard` no longer hard-denies delegations whose prompt merely looks like code search. It now emits an `ask` (the user confirms legitimate external research / non-search work) and narrows the match: a search phrase triggers only with both a code symbol and a local-scope indicator (`in src`, `this repo`, a repo-relative path). Since `IDEA_GATE_OFF` doesn't propagate through the Agent tool, a hard `deny` previously trapped valid delegations such as external CVE research.

### Changed

- The git-ignored path exemption (edit gates skip ignored folders; Stop gates count only tracked code files) is now locked by a `gate_common` self-test wired into `validate.sh`, and the scaffold `CLAUDE.md` tells agents that a deliverable written to a git-ignored path needs no br step, git-flow branch, or commit.

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
