# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.3.0] - 2026-11-01

Rules from an audit of what Claude Code's safety checks blocked across the operator's projects:
scratch probes outside the project, inline edits, chained deletions, printed secrets, encoded
blobs, and research briefs worded as attacks on what was the operator's own service.

### Added

- **Commands** (`RULES.md`): probes, helper scripts and temporary files go in the project's
  `.scratch/`, which Apogee now keeps out of git, instead of `/tmp`, `mktemp` or `.claude/` (a
  protected path whose writes are always reviewed). Files change through Edit and Write, not
  `python3 -` heredocs or `sed -i`; one state-changing action per command, deletions by named
  path; a denied action is not retried in another form; background work is awaited with Monitor,
  not `sleep`.
- **Encoded data**: no long base64 or hex strings in commands; data on disk is decoded by a short
  script in `.scratch/`, and files reach the user as files.
- **Secrets by shape, never by value**: env and config files are inspected by key names; secrets
  live in git-ignored local files the user fills in; what goes to `agy`, MCP or the web carries
  placeholders, and in infrastructure repos `agy` gets redacted excerpts instead of reading files
  with real hosts.
- **Security-sensitive work**: task and subagent briefs state the real context (whose service,
  own hosts, the goal) and scope work to documented behaviour, as a matter of accuracy, never to
  get past a check; a refusal or an empty subagent result after one is reported as blocked, not
  merged as "nothing found".

## [4.2.0] - 2026-10-30

### Added

- **Research runs in its own skill, `apogee:research`, with deep reasoning and a required second
  opinion.** `/apogee:start research` and `/apogee:finish` hand over to it, so they stay the only
  way a research item is opened and closed. The skill carries `ultrathink` and `effort: xhigh`,
  which raise reasoning for research only, not for every branch opened. Before concluding, it asks
  `agy` to challenge the findings and the draft conclusion and records each point and its
  resolution in the note's new **Second opinion** section (or `Unavailable: <reason>`); the close
  checks for it. ADR 0008 carries an amendment.

### Fixed

- **`second-opinion` was blocked in auto mode and its stdin variant sent no context.** `agy` now
  runs with `--mode plan`: it reads the project without approval prompts and cannot write files or
  run commands, where `--dangerously-skip-permissions` approved everything and is blocked by
  Claude Code's auto-mode classifier. `agy -p` ignores stdin, so the heredoc form delivered an
  empty context; context now goes inside the quoted prompt, where the secret scan also sees it.

## [4.1.2] - 2026-10-29

An audit of when and how each skill is invoked found these defects; all are fixed.

### Fixed

- **Hotfixes were routed to a skill that refuses them.** The `enforce-git-flow-skill` deny
  messages and `run-plan`'s stop rule sent a hotfix finish to `/apogee:release`; they now name
  `/apogee:finish` for hotfix branches. `run-plan`'s circuit breaker reads the `max_epics` it
  defines, and `plan-feature`/`run-plan` state that the agent records the approved plan in `br`
  (the plan-approval hook only supplies the commands).
- **`git-commit` could fail on an empty index.** When nothing is staged it now stages the
  commit's files by name and checks `git diff --cached --stat` first. The release reference's
  fallback commits through stdin like the skill.
- **`update-docs` relied on git for local-only files.** Its net-line audit counts lines with
  `wc -l`, it takes a base branch and reads the whole branch instead of the last commit, and its
  description no longer invites runs in the middle of a branch. `/apogee:finish` passes the base
  and no longer tests git history for docs that git cannot see.
- **`br` still described syncing `.beads/` through git.** The description, the sync-branch
  troubleshooting and the sample config now match the local-only rule; ADR 0001 carries an
  amendment.
- **`second-opinion` could leak secret files.** `agy` reads files itself, out of the secret
  scan's sight; the skill and `scaffold/GEMINI.md` now keep it away from `.env*`, keys and
  credential files. Follow-up rounds pass `--model` too.
- **Stale references:** the `merge` alias removal date (next major release, ADR 0008 amended),
  `/apogee:readme` and `/apogee:ai-clean-room` namespaces, the prime directive's tracker claim,
  the `git-flow` operator command count and its hardcoded binary path.

## [4.1.1] - 2026-10-23

### Fixed

- **`second-opinion` defaults to Gemini 4 Argon (Low).** The previous default, Gemini 3.1 Pro
  (Low), is no longer the current Pro-tier model in `agy`. `APOGEE_SECOND_OPINION_MODEL` still
  overrides it.

## [4.1.0] - 2026-10-22

### Added

- **Decisions are asked as a form.** `SOUL.md` routes every decision that is the user's through
  `AskUserQuestion`: concrete options, a one-line trade-off each, the recommended one first. A
  question in prose, or a list of questions closing a report, is no longer acceptable; prose
  remains only where the client has no such tool. The `release` skill no longer prescribes a
  lettered text menu for its dirty-tree choice.

## [4.0.1] - 2026-10-21

The first live run of the 4.0 work loop, in a sandbox project, found three defects; this release
fixes them and keeps the sandbox for the next runs.

### Fixed

- **Branches merged unreviewed.** `review-work` read only `git diff HEAD`, which is empty at
  `/apogee:finish` because every step is already committed. It now reviews the whole branch
  (`develop...HEAD`, or `main...HEAD` on a hotfix), passing that explicit range to `/code-review`
  (whose default target skips commits already pushed, and `/apogee:start` publishes the branch) and
  waiting for its background findings. It runs as one loop: tests of the change, review, fixes
  committed on the branch, tests again, at most two repair rounds. The rules audit gains a
  SIMPLICITY category. `/apogee:finish` calls it with the branch base and only re-tests if code was
  committed afterwards.
- **The full suite ran on every finish.** 4.0.0 turned the 3.x rule "full suite only before a
  release or when asked" into "before a finish or a release". The agent now runs the tests that
  cover its own change, at `finish` and in `run-plan`; the full suite runs in the release
  preparation and in CI. The scaffold Testing section asks for the targeted command first.
- **`git-commit` left a message file outside the project.** Its `f=$(mktemp) … git commit -F "$f"`
  pattern starts with an assignment, matches no permission rule, and in a headless run made the
  agent write the message next to the project. The skill now validates and commits from a quoted
  heredoc (`git commit -F -`), and addresses its scripts through `CLAUDE_PLUGIN_ROOT`.

### Changed

- `/apogee:readme` checks a README with its own independent fact-and-quality agent instead of
  `review-work`, which reviews code. `RULES.md` and `plan-feature` no longer ask for a separate
  review: it is part of `/apogee:finish`.

### Added

- `tests/sandbox/make-project.sh` builds a throwaway Apogee project (bare remote, `main` +
  `develop`, git-flow, `br`, a small unittest module, the scaffold) with the marketplace copy of the
  plugin disabled, for live runs with `claude --plugin-dir plugins/apogee`. It never touches the
  plugin registry.

## [4.0.0] - 2026-10-21

A major release with two breaking changes. Every unit of work now opens with `/apogee:start` and
closes with `/apogee:finish` ([ADR 0008](docs/decisions/0008-start-finish-units-of-work.md)), and
Apogee's general rules move out of each project's `CLAUDE.md` into the plugin, so they update with
it ([ADR 0009](docs/decisions/0009-rules-in-the-plugin.md)). Projects set up with 3.x run
`/apogee:init --migrate` once.

### Added

- **`/apogee:start` and `/apogee:finish`**, the only entry and exit for work. Four types:
  `feature` and `bugfix` (branch off a fresh `develop`, uncommitted changes carried along, branch
  published, `br` epic linked or created; finish runs review, docs, public docs, the clean-tree
  check and the test gate, merges into `develop` and pushes it), `hotfix` (branch off `main` with
  the next patch version; finish runs the release preparation and hands the operator the finish,
  push and publish commands), `research` (a dated note in `docs/apogee/research/` with no branch;
  finish checks the conclusion and sources, promotes lasting facts, proposes the follow-up).
  `/apogee:run-plan` opens and closes each epic through them.
- **Toolkit rules in the plugin**: `plugins/apogee/rules/SOUL.md` (voice, dialogue language,
  honesty, restraint) and `rules/RULES.md` (work loop, git, files, tools, code, shell output),
  injected by the SessionStart hook on every session source in projects with `docs/apogee/`. The
  project's `CLAUDE.md` overrides them.
- `/apogee:init --migrate` converts a 3.x `CLAUDE.md`: toolkit lines are dropped, project lines are
  kept verbatim, after confirmation.
- Shell output rules: filter before slicing, keep the tail of builds, tests and logs, never let a
  pipe hide a failing exit status.
- `symfony-cli-workflow` replaces the `symfony` skill: version-aware (8.1, 7.4 LTS, 6.4 LTS), with
  references and a project probe.
- ADR 0008 and ADR 0009.

### Changed

- **`/apogee:merge` is renamed `/apogee:finish`**; `merge` stays one release as a deprecated alias.
  Its plain-repository mode no longer merges into `main` (the wall denies it): it pushes the branch
  and hands the merge to the operator.
- **`/apogee:release hotfix` is replaced by `/apogee:start hotfix`.** `/apogee:release` covers the
  regular release from `develop`; its preparation lives in
  `skills/release/references/prepare-and-hand-over.md`, shared with the hotfix finish.
- **The scaffold `CLAUDE.md` is project-only** (Project, Operator Model, Key Architecture Decisions,
  Project Rules, Testing, Privacy & Security, Bilingual Documentation). `init` and `update-docs`
  write project facts only and report general rules as candidates for `RULES.md`.
- The plugin is installed and updated from the GitHub marketplace only. `install.sh` clones the
  templates into a temporary directory instead of keeping `~/.apogee`; `setup.sh` registers
  `mishagin-dev/Apogee` when no `apogee` marketplace is known and never re-points one.
- The Rules Auditor in `review-work` checks against `RULES.md` as well as the project's
  `CLAUDE.md`.
- README rewritten around the start/finish workflow, with a trust block, a what-it-touches table
  and an uninstall section. Apogee is described as its own project that started from CCDK; the
  `LICENSE` adds the project's copyright line above the CCDK one.

### Fixed

- `setup.sh` initialised git-flow with `master` on a fresh repository, whatever `git init -b` or
  `init.defaultBranch` said, because the branch did not exist yet. It now runs `git init -b main`
  and pins `gitflow.branch.master` before `git flow init -d`; an existing `master` is respected.
- The commit validator rejected `type(scope)!:`, the Conventional Commits breaking-change marker
  that `/apogee:release` looks for.

### Removed

- The "Use sub-agents for tasks spanning 3+ files" rule, and "always ask before git commits" from
  the Operator Model example (one of the formulations that made agents believe commits were
  forbidden).

## [3.0.2] - 2026-10-20

### Fixed

- The scaffold `CLAUDE.md` language rule said "user-facing dialogue in your working language",
  which a host project with an English-heavy context read as English. It now takes the dialogue
  language from Claude Code's own `language` setting (the user's language if unset), states that
  this covers tool-call and background-task captions too, and that English context is never a
  reason to drift. On disk and towards other tools: English, unchanged.

## [3.0.1] - 2026-10-20

### Fixed

- `setup.sh` creates the working-memory directories
  `docs/apogee/{domain,design,diagrams,research,prompts,reports}/` up front, so the layout is
  visible from the first session instead of existing only as a convention in the
  `docs/apogee/README.md` index. They are git-excluded with the rest of `docs/apogee/`.
- `/apogee:release` prints the finish with `GIT_MERGE_AUTOEDIT=no` and documents the recovery for a
  merge left open by a GUI editor (`git commit --no-edit --cleanup=strip`, then re-run the finish):
  on a machine with `core.editor = zed --wait`, the merge commit's editor aborted the finish
  half-way and the next attempt refused with "Index contains uncommited changes".

## [3.0.0] - 2026-10-20

A major release: the toolkit is re-aligned with the current Claude Code harness (skills instead
of commands, `effort` frontmatter, `claude plugin validate`, the built-in `/code-review`) and two
behaviours change in ways that are breaking for anyone relying on the old ones. **The release
finish is now refused to an agent, and the "never push" rule is replaced by a wall around `main`
and tags.** The full diagnosis behind this release is dated 2026-10-20; the decisions are
[ADR 0006](docs/decisions/0006-run-plan-autonomy-design.md) and
[ADR 0007](docs/decisions/0007-production-branch-wall.md).

### Added

- **The production-branch wall** (ADR 0007). `enforce-git-flow-skill.py` Rule 3 denies any
  `git push` whose destination resolves to the production branch in any spelling (`main`,
  `HEAD:main`, `feature/x:main`, `refs/heads/main`, `:main`, `--delete main`, a bare `git push`
  while `main` is checked out), any push of tags (`--tags`, `--follow-tags`, `refs/tags/...`, an
  existing tag by name), `--all`/`--mirror`/force pushes, `git merge` while `main` is checked out
  (also `git checkout main && git merge ...`), and `git tag <name>` creation. It applies in **any**
  repo with a `main`/`master`, git-flow or not, so a submodule is covered too. Everything below the
  wall is pre-authorized: `develop` and work branches are the agent's to push, publish and delete;
  `/apogee:run-plan` and `/apogee:merge` push `develop` after each finished branch; committing
  finished work on a `feature/`/`bugfix/` branch through `apogee:git-commit` needs no question.
  `setup.sh` adds allow rules for the sanctioned push forms and deny rules for the obvious
  unsanctioned spellings as defense in depth. Covered by `--test` (40 wall cases) and
  `tests/smoke-run-plan.sh`.
- **AI tooling is local-only, by decision.** One exclude list
  (`hooks/core/config/exclude-list.txt`: `docs/apogee/`, `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`,
  `.claude/`, `.beads/`) is written by `setup.sh` and re-asserted by the SessionStart hook for the
  repo root and each first-level submodule, so plans, memory and a submodule's `CLAUDE.md` never
  surface in `git status`. The scaffold `CLAUDE.md` states the decision so the agent stops checking
  whether these paths are tracked. `.beads/` is local-only: the `br` skill no longer commits it.
- **`public-docs` skill** (replaces `doc`): human-facing documentation under `docs/` where every
  generated doc declares the source paths it covers in `sources:` frontmatter. The new `update`
  mode refreshes only the docs whose sources changed and is invoked from `merge`, `run-plan` and
  `update-docs`, so public docs follow the code without anyone remembering to ask.
- **`docs/apogee/README.md` index**, loaded by `/apogee:prime` and maintained by `update-docs`,
  with optional `domain/`, `design/`, `diagrams/`, `research/`, `prompts/`, `reports/`
  directories replacing the unused `business/design-brand/legal/open-issues`.
- **`ai-clean-room` skill** (manual invocation only): a black-box clean-room procedure for
  reproducing a closed-source application's functionality without copying it.
- `validate.sh` Stage 8 runs `claude plugin validate --strict`; Stage 9 runs
  `tests/smoke-run-plan.sh` against real `br` + `git flow` sandboxes; both skip where the
  binaries are absent (CI). `apogee-session-start.py --test` covers the exclude maintenance.
- The secret scanner now covers `WebFetch`, `WebSearch` and `agy` invocations on the Bash surface
  (the second-opinion skill pipes code to an external model through a heredoc).
- `second-opinion` reads its model from `APOGEE_SECOND_OPINION_MODEL`.
- `/apogee:release` writes the release notes to `$TMPDIR/apogee-release-<version>.md` (the OS
  cleans it up) and prints the three operator commands: `git flow release finish -m "<version>"`
  (short tag message, as before), the push, and `gh release create --notes-file` pointing at the
  file, so the release description is never typed by hand and is no longer a copy of the
  changelog section.

### Changed

- **`/apogee:release` stops before the finish** and prints `git flow release finish` and
  `git push origin main develop --tags` for the operator; the hook denies both to an agent.
  Rule 1 is a DENY, no longer an ASK.
- **The six commands are skills** (`plugins/apogee/skills/<name>/SKILL.md`), as Claude Code now
  recommends; names are unchanged. `init` and `release` are user-invocable only; `merge` and
  `run-plan` stay model-invocable because the loop and the plan-approval handoff call them.
  Commands gained `description`, `argument-hint` and `effort: high` (replacing `ultrathink`).
- **`review-work` delegates bug and security hunting to the built-in `/code-review`** and keeps
  the Apogee-specific parts: a rules audit against `CLAUDE.md` whose library/API claims must be
  Context7-verified (`[unverified]` findings are discarded) and an intent verdict against the
  recorded plan. The previous parallel-reviewer procedure is kept as a reference.
- `/apogee:run-plan` takes its cap from `max-epics:` in the arguments (default 3) and its test gate
  from the project's `CLAUDE.md` Testing section; `pipeline.json` is gone, and with it the
  plugin-cache lookup. Its 70-line design note is now ADR 0006.
- `update-docs` ports two CCDK 3.2 rules ("the default for every line is DELETE", a net-line
  audit) and states the boundary with Claude Code's auto-memory.
- Rule 2b queries `br show` only for open epics instead of every issue in the backlog.
- `validate.sh` Stage 7 (language policy) is Python: BSD grep's `[а-я]` range matched every
  em-dash with `LANG` unset (614 false FAILs on a clean tree); allowlist entries no longer carry
  a line number. Stage 6 checks every marketplace entry against its `plugin.json`.
- `setup.sh` no longer re-points an already registered `apogee` marketplace at the directory it
  runs from, and no longer creates `assets/` in the host project.
- `br-capture-gate.py` reads `tool_response` and stays silent when the plan was not accepted.
- Skill and command bodies reference bundled files through `${CLAUDE_PLUGIN_ROOT}`; the
  frontmatter field is `user-invocable` (the underscore spelling was ignored).
- Stale references removed throughout: `idea-enforce.json`, the deleted language guard, the
  gemini-based fallback, `.claude/skills/...` paths, "Explore (Sonnet)".

### Removed

- `idea/idea-nudge.py` and the `idea-mcp` skill: the JetBrains MCP server and JetBrains' own
  plugin describe their tools; the one rule that mattered is a line in the scaffold `CLAUDE.md`.
- `core/notify.sh` and the sound files: Claude Code's `inputNeededNotifEnabled` plays the cue.
- The `deploy` template skill (a template cannot be customized per project from inside the
  plugin) and the image skills `image-gen`, `image-edit`, `bg-remove` (never used; graphics has
  better tools). Their tools (`deno`, `rembg`, `python3`, `source`) leave the permission baseline.
- `hooks/core/config/pipeline.json`; the empty `business/`, `design-brand/`, `legal/`,
  `open-issues/` scaffold directories; `assets/.gitkeep`.
- The "never `git push`" rule and "Always ask before: git commits" in the scaffold, superseded by
  the wall and the pre-authorization above.
- The `release.yml` workflow that published a GitHub Release from the CHANGELOG on tag push:
  the operator publishes with `gh release create` and the notes file. It also mislabelled
  "Latest" when two tags were pushed together.

## [2.1.0] - 2026-08-29

### Added

- **`symfony` skill** — drives a Symfony project through the official `symfony` CLI instead of
  bare `php bin/console` / `composer` / `vendor/bin/*`, on two measured grounds rather than
  style. Only `symfony console` resolves the project root, so bare `php` fails from any
  subdirectory (`Could not open input file: bin/console`); `symfony composer` and `symfony php`
  do **not** resolve it, which is the half nobody expects. And the CLI injects environment from
  running Docker services: a Flex `compose.override.yaml` publishes ports unpinned, so `.env`
  keeps the `5432` placeholder while Docker moves the real port on every `up` — observed
  shifting `32770` -> `32771` between two runs of the same project. Also records the MakerBundle
  traps that break agents outright: `--no-interaction` crashes the generator
  (`Typed property ...$controllerClassData must not be accessed before initialization`), and
  closing stdin on `make:entity` is a silent half-success that leaves the entity field-less.
  Ships with `smoke.sh`, which re-proves the `.env` divergence on the target project rather than
  asking the reader to trust the numbers. Verified end to end against Symfony 8.1.5, PHP 8.5.9
  and PostgreSQL in Docker.

### Changed

- **The idea nudge no longer recommends an unreachable path.** `mcp__idea__*` schemas are
  deferred, so a call without a prior `ToolSearch` fails outright — and 14 days of transcripts
  carried 119 `ToolSearch` calls with not one `select:mcp__idea__*`, i.e. the directive
  converted at zero. It now states that prerequisite. It also stops advertising search: a
  2026-08-25 measurement over 10 lookups replayed from real session history found the MCP search
  path 41% *more* expensive than grep, since `search_symbol` returns coordinates without symbol
  names and `search_text` without line content, so the small first response usually forces a
  second call. What the directive names now is only what has no shell equivalent — inspections,
  semantic rename, call graphs, IDE run configurations.
- Both plugin manifests list the new skill; `marketplace.json` also picks up `run-plan`, which
  had been missing from its command list since that command shipped.

## [2.0.1] - 2026-08-29

### Fixed

- **The MCP secret scanner never ran.** A hook `matcher` is a regex matched against the *whole* tool
  name, so the bare `"mcp__"` matcher could not match `mcp__context7__resolve-library-id` — or any
  other real tool. It shipped that way in the plugin's first commit and had not fired once since.
  2.0.0 fixed the scanner's payload parsing but left the matcher, so the gate stayed dead; the
  matcher is now `"mcp__.*"`. Caught by calling a real MCP tool with a synthetic AWS key in the
  payload and watching it sail through. The repo contained the evidence all along: the (now
  removed) `idea-usage-tracker` used `"mcp__idea__.*"` and worked.
- `validate.sh` Stage 4 now fails on any `mcp__`-prefixed matcher that does not end in `*`, so this
  class of silent no-op cannot ship again.

## [2.0.0] - 2026-07-29

Two weeks of daily use made the verdict clear: the context layer (docs, `br` memory, priming,
skills) makes the agent genuinely better informed, while the enforcement layer mostly got in the
way. A three-part audit found that of thirteen blocking gates, exactly one defended an irreversible
outcome — and it was dead code. This release strips enforcement down to safety-only. See
[ADR 0005](docs/decisions/0005-enforcement-safety-only.md).

The rules did not change. The walls did. Everything a gate used to block is still written in
`scaffold/CLAUDE.md` and the skills, where an agent reads it and a human can override it.

### Removed

- **Eleven blocking gates, 22 files, ~2,570 lines.** The idea-mcp guard bracket (symbol/glob/bash-
  grep guards, read gate, agent guard, force-activate, usage tracker), the `br` edit/branch/progress
  gates, the review→docs Stop gate, the `git commit -F` gate, the external-AI language guard, and
  the passive hooks that only existed to feed them (`snapshot-baseline.sh`, `br-snapshot.sh`,
  `br-sig.py`, `gated.sh`, `skill-run-tracker.py`, `track-file-touch.sh`).
- **The `Stop` lifecycle event**, which no longer has any consumer. A session can end whenever it
  ends.
- **The escape environment variables** `BR_GATE_OFF`, `REVIEW_GATE_OFF`, `IDEA_GATE_OFF` and
  `TOOL_LANG_OFF`. Nothing reads them; keeping a documented hatch with nothing behind it is the same
  doc/code contradiction this release exists to end. **If you set any of these, remove them** — they
  will be silently ignored.
- **`hooks/core/lib/`**, the cross-group helper directory. With one consumer left per helper, each
  survivor moved into (or was inlined by) the hook that uses it.
- **`pipeline.json` keys** `enabled`, `min_lines_changed`, `review_threshold`, `file_patterns`,
  `review_command`, `test_command`, `docs_command` and `phases`. Only `run_plan` retains a consumer.
  **A tuned `review_threshold` now gets silence, not an error.**

### Changed

- **`hooks.json`: 27 hook commands → 10.** Two of them can block; the rest inject context.
- **`enforce-git-flow-skill.py`: 522 → 296 lines.** Rules 2/3/4/5/6 (commits off gitflow branches,
  manual merges, manual branch creation, one-branch-at-a-time) are gone; they duplicated
  `skills/git-flow/SKILL.md` verbatim. The release/hotfix ASK is unchanged.
- **The open-epic-steps DENY is now scoped to `APOGEE_RUN_PLAN=1`-tagged commands only** — and stays
  fail-closed there. An interactive `git flow feature|bugfix finish` is no longer checked at all.
  This is the one rule that survived the teardown, on a refined criterion: the test is not only
  whether an outcome is irreversible, but whether a human is present to catch it. An unattended loop
  has no such backstop.
- **`permissions.deny` is documented as what it always was** — the primary guard against destructive
  commands (`sudo`, `rm -rf`, `git push --force`, `git reset --hard`, …). It is enforced by Claude
  Code itself, independent of any Apogee hook, and it is untouched by this release.
- **`br` tracking is now stated as a rule** in `scaffold/CLAUDE.md` §1. It was the only discipline
  that existed solely inside a deleted gate and nowhere in prose.
- **`idea-nudge.py` no longer bootstraps anything** — it reminds the agent that `mcp__idea__*` tools
  are cheaper than grep + whole-file reads, and stops after three firings per session.
- **`br-capture-gate.py`'s directive** no longer promises edit/branch gates that don't exist.
- Docs rewritten to match: `HOOKS.md` (96 → 62 lines), `ARCHITECTURE.md`, `README.md`, `INSTALL.md`,
  and the git-flow / git-commit / idea-mcp skills.

### Fixed

- **The MCP secret scanner was dead code and now works.** It inspected `.code_context`,
  `.problem_description` and `.attached_files[]` — the schema of a gemini MCP server that has not
  been configured for months — so every outbound payload passed through unexamined. It now walks the
  whole `tool_input` via `jq -r '..|strings'`, one value per line, capped at 256 KB so a minified
  blob in the payload cannot spike grep.
- **The scanner's false-positive engine is gone.** The heuristic `credentials` group and the loose
  `regex_patterns` matched `password: str`, `client_secret: string` and `API_KEY=os.environ[...]`,
  and a 24-entry line whitelist could not keep up. What remains is vendor-prefixed tokens, PEM
  headers and credential-bearing URLs, plus a placeholder filter applied to the matched token — so
  AWS's own `AKIAIOSFODNN7EXAMPLE` and `postgres://user:password@localhost` stay quiet. Precision
  over recall, deliberately: a scanner that cries wolf gets switched off, and a switched-off scanner
  has zero recall.
- The scanner emits a modern `permissionDecision: deny` instead of the legacy `{"decision":"block"}`
  shape, reports only the first six characters of a match, and no longer writes a log file into the
  versioned plugin cache on every MCP call.

### Testing

- `security-scan.sh --test` — 18 cases (8 must fire, 10 must stay quiet), wired into
  `validate.sh` Stage 5.
- `enforce-git-flow-skill.py --test` rewritten. `_FLOW_FINISH_RE`, the regex behind the release ASK,
  had **zero** coverage before this release.
- `smoke-run-plan.sh` retargeted: 15 assertions against a real `br` + `git flow` sandbox, now
  including the release/hotfix ASK.

## [1.16.1] - 2026-07-24

### Fixed

- `/apogee:run-plan` could not locate `pipeline.json`. The file ships as plugin machinery, so
  `setup.sh` never copies it into a host project, and `${CLAUDE_PLUGIN_ROOT}` is a `hooks.json`
  substitution rather than an environment variable an agent's Bash call can read. Pre-flight now
  resolves it explicitly — repo-relative inside the Apogee source tree, otherwise a
  version-agnostic search of the plugin cache — and falls back to documented defaults.
- `br-progress-gate.sh` read `hooks/br/config/pipeline.json`, a path that never existed. The gate
  had run on hardcoded defaults since it shipped, ignoring `min_lines_changed` and `file_patterns`.
- `effective_repo()` did not treat a newline as a shell command separator, so `cd sub` on one line
  followed by `git commit` on the next was judged against the session's repo instead of the
  submodule.

### Changed

- The set of extensions counting as trackable code is now defined once, in `pipeline.json`'s
  `file_patterns`, instead of five drifting copies. Bash gates resolve it through the new
  `hooks/core/lib/file_patterns.sh`; `gate_common.py` derives `CODE_EXTENSIONS` from the same
  source. PHP and Dart join the list; Kotlin, Java, and the C family are now consistent across
  every gate.

## [1.16.0] - 2026-07-24

### Added

- `/apogee:run-plan`: autonomous epic-by-epic execution for beads+git-flow projects. Opens a
  branch per ready `br` epic, implements/closes its steps, runs the review/docs/test gates,
  finishes into develop, and repeats — with no per-micro-decision confirmation. A stateless
  `APOGEE_RUN_PLAN=1` command-string tag (not a marker file or env var — hooks are separate
  processes per tool call, so nothing session-scoped is crash-safe) lets
  `enforce-git-flow-skill.py` bypass the "another branch open" ASK and apply a fail-closed check
  on a new DENY rule: finishing a branch is blocked while its linked epic still has open steps,
  failing open only for untagged manual finishes (matching the repo-wide convention). `git push`
  and the release/hotfix lifecycle always stay manual. Circuit breaker defaults to 3
  epics/invocation (`pipeline.json`, tunable).

### Fixed

- `br-capture-gate.py` (fires on `ExitPlanMode`) now hands off to `/apogee:run-plan` in git-flow
  repos instead of telling the agent to open the branch and implement by hand — approving a plan
  is now the trigger for autonomous execution, not a separate ask.

### Changed

- ADR 0003 records that Zed has no idea-mcp-parity MCP surface (researched, not built); ADR 0004
  records Serena as the recommended non-JetBrains alternative (researched, not built).
- `/apogee:plan-feature` gained a `deep-research` skill escalation rung for genuinely deep external
  unknowns that ad-hoc WebSearch can't settle.

## [1.15.1] - 2026-07-13

### Fixed

- The commit gate (`enforce-git-flow-skill.py`) now judges the git-flow branch of the repo the
  command actually targets, not the session's working directory. A submodule commit
  (`git -C sub commit`, `cd sub && git commit`) issued while the super-repo sat on `develop`/`main`
  was wrongly denied, forcing a pointless same-named "umbrella" branch in the super-repo just to
  commit submodule code. New `effective_repo()` helper in `gitflow_common.py` resolves the target
  repo (parsing `git -C <dir>` and a leading `cd <dir> &&`); real super-repo commits stay gated.
  This mirrors the already submodule-aware `br-branch-gate.py`.

## [1.15.0] - 2026-07-09

### Added

- `setup.sh` now runs `git flow init -d` automatically alongside `git init`/`br init` when a
  project has no `gitflow.*` config yet (on by default, opts out with the existing
  `--no-tracker-init` flag) — verified to work even on a brand-new, zero-commit repo.
- `scaffold/CLAUDE.md` §6 Coding Standards gained five senior-level rules: type hints on new
  signatures, deliberate (never silent) error handling, function decomposition past one
  responsibility, no duplicated constants/parsing rules, and `set -euo pipefail` as the Bash
  default. A new §9 "Bilingual Documentation" gives host projects an opt-in template for
  maintaining RU+EN docs as separate per-language files. `scripts/validate.sh` gained a Stage 7
  language-policy gate that fails CI on any unallowlisted Cyrillic in shipped code
  (`scripts/lang-check-allowlist.txt` holds the known legitimate exceptions).

### Changed

- `scaffold/CLAUDE.md` §6 gained a comment-register rule: neutral, technical tone for code
  comments — no slang, ALL-CAPS, exclamation marks, or reader-directed asides, English only.

## [1.14.0] - 2026-07-09

### Added

- `setup.sh` now excludes `CLAUDE.md` and `GEMINI.md` (not just `docs/apogee/`) from the host
  project's git via `.git/info/exclude` — all AI-tooling context stays local-only, worked with
  normally (an IDE with "respect gitignore" off still shows it) but never committed. `/apogee:init`
  mirrors this for a submodule's own flat `CLAUDE.md` in that submodule's own exclude file.
- `setup.sh` now runs `git init` automatically when the target isn't a git repo yet, and `br init`
  automatically when it has no `.beads/` yet — both on by default (`--no-git-init` /
  `--no-tracker-init` opt out). `git flow init` stays a printed reminder only, since it's a
  structural branching decision a project should opt into consciously.

### Fixed

- `review-docs-gate.sh` and `br-progress-gate.sh` (Stop hooks) computed `git diff --numstat HEAD`
  to measure changed lines. On a fresh repo with zero commits, `HEAD` doesn't resolve, `git diff`
  exits 128, and `pipefail` combined with `set -e` aborted the script silently mid-run — surfacing
  as a non-blocking Stop hook failure on every stop. Both gates now skip cleanly when `HEAD`
  doesn't exist yet.
- `docs/apogee/**` was only exempt from the br edit/branch gates when the project happened to have
  it git-ignored already — a one-time side effect `setup.sh` writes on install. A project that
  enabled the plugin without running `setup.sh` (or ran `/apogee:init` before it) never got that
  exclude rule, so the first write into `docs/apogee/**` was wrongly denied pending a br step/work
  branch. It's now unconditionally exempt, independent of git-ignore state.

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
