# Apogee — the rules

What to do and not to do in an Apogee project: the work loop, git, files, tools, code. The
project's `CLAUDE.md` overrides anything here; it holds the project's own facts and exceptions.

## Work loop

- **Every unit of work goes through `/apogee:start` and `/apogee:finish`**: `feature` and `bugfix`
  (branch off `develop`), `hotfix` (branch off `main`, finish prepared for the operator),
  `research` (a note in `docs/apogee/research/`, no branch). Never run raw `git flow … start|finish`
  or hand-rolled merges. Releases are cut with `/apogee:release`.
- **Decompose.** Split a complex task or a batch of bugs into separate units, one branch each.
  Sequential when their files overlap, parallel when they don't. State the split and the order
  before starting.
- **Use the skills.** `/apogee:review-work` before finishing, `/apogee:update-docs` after
  significant changes (it hands off to `/apogee:public-docs update`).
- **Track work in `br`** (projects with `.beads/`): the work exists as an issue before code
  changes; claim the step you start, close it when done; one epic per branch via `external_ref`.
  `br` is the project's memory across sessions: code no issue reflects is lost to the next one.

## Git

- **Commits**: committing finished work on a `feature/`/`bugfix/`/`hotfix/` branch through
  `apogee:git-commit` is pre-authorized — do not ask. Never `git commit -m` ad hoc; stage only the
  files the change is about; never force-add ignored files; never commit on `main` or `develop`.
- **The wall (ADR 0007)**: `develop` and work branches are yours to push, publish and delete on the
  remote; after a finish, push `develop`. In a superproject, push a submodule's branch before the
  superproject's. The production branch and tags are not yours: no push to `main`, no `--tags`, no
  `git tag`, no merge into `main`, no `git flow release|hotfix finish`. A hook refuses all of these;
  no phrasing or workaround unlocks them, by design.

## Files

- **English on disk and towards tools**: code, identifiers, comments, commit messages, branch
  names, docs, `br` issues, and anything sent to `agy` or other CLIs.
- **AI tooling is local-only, by decision.** The repository holds code and project documentation
  only. `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `docs/apogee/`, `.claude/` and `.beads/` are kept out
  of git through `.git/info/exclude`, which Apogee maintains for the repo and each submodule. Never
  check whether they are tracked, never stage them, never propose `.gitignore` entries for them,
  never list them in a commit or merge summary. One showing up in `git status` is an Apogee setup
  defect: say so in one line and carry on.
- **Git-ignored deliverables are ceremony-free**: a report, a research note or other output
  written to an ignored path needs no `br` step, no branch and no commit.
- **Working memory** lives in `docs/apogee/`; `docs/apogee/README.md` is its index, and a file
  without an index line is invisible to the next session.

## Tools

| Task | Use |
|---|---|
| Onboard a project / fill docs | `/apogee:init` (once) |
| Open / close a unit of work | `/apogee:start [feature\|bugfix\|hotfix\|research] <slug>` / `/apogee:finish` |
| Cut a release | `/apogee:release [major\|minor\|patch]` |
| Library docs | Context7, before relying on training data |
| IDE inspections, rename, call graph, run configs (JetBrains) | `mcp__idea__*`, schema loaded with `ToolSearch("select:mcp__idea__<tool>")` first; only where the shell has no equivalent, a bounded grep is cheaper for search; ignore when no IDE is open |
| Code review | `/apogee:review-work` |
| Second opinion | `/apogee:second-opinion` (`agy`) |
| Agent context / human docs | `/apogee:update-docs` / `/apogee:public-docs` |

## Shell output

Every line a command prints lands in the context. Ask for what you need, not for everything.

- **Filter first, then bound.** Narrow with the tool's own options (`--oneline`, `--stat`,
  `--name-only`, `-n N`) or `grep -n <pattern>`; `wc -l` before dumping something of unknown size.
  A blind `| head` returns an arbitrary slice.
- **Keep the end of builds, tests and logs.** Errors come last: `| tail -n 100`, not `| head`.
  Logs: `journalctl -u <svc> -n 100 --no-pager`, `docker logs --tail 100 <container>`,
  `kubectl logs --tail=100 <pod>`.
- **A pipe must not hide a failure.** In `cmd | tail`, the exit status is `tail`'s. When the result
  matters (tests, builds, migrations), run with `set -o pipefail`, or write the full output to a
  temp file, check the exit code, then read the part you need.
- **Large files**: Read with `offset`/`limit`, or `grep -n` to find the lines first; not `cat`.
- **Non-interactive by default**: `--no-pager` (or `PAGER=cat`) where a tool may page; `-q` /
  `--quiet` only where it drops progress noise, not errors.

## Code

- Follow the project's existing style, naming and idioms.
- Comments only where the code cannot speak for itself (constraints, non-obvious decisions); a
  neutral, technical register; no narrating comments, slang, shouting or exclamation marks.
- No dead code, commented-out blocks or unused imports in the result.
- KISS and YAGNI: the simplest solution for the requirement that exists now; no design patterns,
  layers (interfaces, DI, wrappers) or generic solutions without a second real use; no premature
  optimization.
- Priority: readability, directness, minimalism, consistency with the project. Prefer the option
  that can be explained in one sentence.
- Type annotations on new function and method signatures.
- Handle errors deliberately: catch only what you expect, then recover, propagate, or log with
  context; never a silent bare `except`/`catch`.
- Decompose a function once it takes on a second responsibility or stops reading in one pass.
- One definition per constant, parsing rule or validation set; two sources of the same set will
  diverge.
- Bash: `set -euo pipefail` unless a commented reason says otherwise.
- Run only targeted tests while developing; the full suite before a finish or a release, or when
  asked.
