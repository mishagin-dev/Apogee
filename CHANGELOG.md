# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.13.0] - 2026-07-08

### Added

- `/apogee:release` is no longer Apogee-only: a new Version-source detection step (Pre-flight 5)
  finds where (if anywhere) any project declares its version — the Apogee-plugin lockstep pair,
  a standalone `package.json`/`composer.json`/`pyproject.toml`/`Cargo.toml`/`VERSION` file, or
  "CHANGELOG + git tag only" when none is found — and bumps accordingly instead of refusing to
  run outside this repo. Also infers the tag-prefix convention and nudges about a possible
  README version badge. The CI gate (Step 5) now falls back from `scripts/validate.sh` to a
  project's own `CLAUDE.md` Testing section, or asks the user, instead of hardcoding
  `validate.sh`. `/apogee:merge`'s release/hotfix redirect wording was generalized to match.

### Fixed

- `scaffold/CLAUDE.md`'s Communication Style section read as too clinical — it forbade basic
  courtesy like acknowledging thanks. Task-focused responses stay free of padding and unearned
  praise, but ordinary social exchanges now get a brief, genuine reply.

### Changed

- `scaffold/CLAUDE.md` gained a Communication Style section (dry, direct tone; fact → analysis →
  solution response shape) and extended Coding Standards with KISS/YAGNI/anti-overengineering
  rules and an explicit quality-priority order.

## [1.12.0] - 2026-07-07

### Added

- `.github/workflows/release.yml`: on every tag push, creates a GitHub Release with notes drawn from the matching CHANGELOG section (`gh release create --verify-tag`). No manual archive step — GitHub attaches the standard source zip/tar.gz automatically. This is the CI shape the `git-flow` skill's "Publishing the release" procedure already detects and defers to, so the local `gh`/`glab` fallback stays correctly inert for this repo.
- README badges (CI status, latest release, license) and an explicit License section.

## [1.11.0] - 2026-07-07

### Added

- The `git-flow` skill gained a "Publishing the release" procedure: after `finish` + push, detect the remote host (`github.com` → `gh`, `gitlab` → `glab`) and defer to CI if it already auto-publishes releases on tag push; otherwise create the release directly, with notes drafted from the CHANGELOG entry and rewritten into a short polished announcement. `/apogee:release`'s Step 8 now points at it.
- `/apogee:plan-feature` and `/apogee:prime` now size their context load to whether a task was given: a specified task skips `progress.md` (no "what's next" framing needed), no task loads it as before. `/plan-feature <task>` now front-loads the same grounding a separate `/prime` call used to, so the two no longer need to be run back-to-back.

## [1.10.1] - 2026-07-07

### Fixed

- `/apogee:release`'s own prose told the agent to stop and wait for the user to invoke `release finish`/`hotfix finish` themselves, duplicating the `enforce-git-flow-skill` hook's ASK confirmation with a second, redundant wait. The agent now runs `finish` directly once a release has been requested and `validate.sh` is green — the hook's ASK (it touches the production branch) is the actual safety gate. Only `git push` remains a distinct, explicit, manual step.
- `br-branch-gate.py` checked the outer workspace repo's branch even when the edited file lived inside a git submodule, which has its own independent branch/HEAD. This wrongly denied edits inside a submodule that was already properly on its own work branch (whenever the outer repo sat on `develop`/`main`), forcing pointless "umbrella" branches in the outer repo just to unblock the edit. The gate now resolves and checks whichever repo actually contains the edited file (`gate_common.git_root_for`).

## [1.10.0] - 2026-07-07

### Added

- `enforce-git-flow-skill.py` now ASKs before `git flow feature|bugfix start` when another such branch is already open (unfinished), instead of silently allowing work to pile up on parallel branches. A companion `unfinished-branch-nudge.py` (`UserPromptSubmit`) reminds the agent to surface any still-open branch to the user before starting new work — and separately flags branches whose content is already fully merged into `develop` (via some other means) as cleanup candidates, distinct from genuinely unfinished work.

### Fixed

- `review-docs-gate.sh`'s end-of-session diff is now scoped to a per-session manifest of touched files (written by a new `track-file-touch.sh`), so another session's — or pre-existing — dirty state in the same working tree can no longer inflate the line count and force `/review-work` + `/update-docs` for changes this session never made.
- The `git merge`-ref detection in `enforce-git-flow-skill.py` assumed the branch name was the last token of the command, so `git merge feature/x --no-ff -m "..."` (the shape this repo's own `merge.md` template uses) slipped past the deny rule undetected, letting a manual merge into `develop` leave the branch un-deleted. The check now scans every token after `merge` for a gitflow-prefixed ref, regardless of position.

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
