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
- **Review and docs are part of the finish.** `/apogee:finish` runs the review loop
  (`/apogee:review-work`: tests of the change, review, fixes, tests again) and `/apogee:update-docs`;
  don't run them separately unless the user asks.
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
- **Secrets by shape, never by value.** Inspect env and config files by key names
  (`cut -d= -f1`, or `.env.example`); never print a value. Secrets live in git-ignored local files
  the user fills in (`.env.local`, `*.local.xcconfig`); never write one into a tracked file.
  Anything sent to an external model or service (`agy`, MCP, web) carries placeholders for hosts,
  keys, tokens and subscription URLs.
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
| Code review | inside `/apogee:finish`; `/apogee:review-work` on request |
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

## Commands

Every command is a reviewable action. Keep each one obvious about what it touches.

- **Scratch inside the project.** Probes, helper scripts and temporary files go in `.scratch/` at
  the project root, which Apogee keeps out of git, created with the Write tool. Not `/tmp` or
  `mktemp` (outside the project, every write there is reviewed), not `.claude/` (a protected path,
  same). Delete what you made, by name, when done.
- **Edit files with Edit and Write**, not `python3 -` heredocs, `sed -i` or `perl -pi`: the change
  stays a reviewable diff, and edits inside the project need no extra approval.
- **One state-changing action per command.** Writes, deletions, branch switches and pushes run as
  their own commands, not chained after reads. Delete by named path, never by wildcard, glob or
  `find -delete`.
- **A denied action stays denied.** Don't retry it in another form or chain other commands onto
  it. Tell the user what was blocked and why it was needed; they run it or approve it.
- **Wait with Monitor, not sleep.** Poll a background job or a CI run with `run_in_background` and
  Monitor; a foreground `sleep N; cat <output>` is blocked.

## Encoded data

- **No encoded blobs in commands.** Never put a long base64, hex or other opaque encoded string
  into a Bash command: not in a heredoc, an `echo`/`printf`, or a variable. Nobody can review what
  such a command does, and safety classifiers read it as obfuscation and block it.
- **Decode from disk.** Data already in a file (an export, a dump, a captured payload) is decoded
  by a short script that reads the file and writes the result: write the script to `.scratch/`
  with the Write tool, run `python3 <script> <input> <output>`, and delete the script when done.
  The blob never passes through the command line or the context.
- **Hand files over as files.** To give the user a file, write it to disk and name its path; never
  encode it inline in a message or a command.

## Security-sensitive work

For projects that run network infrastructure (VPN, proxy, DNS, server fleets) or touch security
topics, where safety checks look hardest.

- **Describe the work as it is.** A task, research brief or subagent prompt states the real
  context: whose service it is, that the hosts are the operator's own, and the goal (keep users
  connected, harden, diagnose, migrate). Scope it to the documented behaviour of the software in
  use (upstream docs, issues, source) at design level. "Weaponise" or "exploit" does not describe
  maintaining one's own service; don't use them for it. This is accuracy, not rewording: never
  reshape a request to get past a safety check, and work aimed at third parties is out of scope.
- **A refusal is a result.** A declined request, a model-switch notice, or a subagent that returns
  empty after a refusal is reported as blocked, with what was asked; never merged as "nothing
  found". The user decides what next: rewind, another approach, or the documented fallback model.

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
- **Test your own work.** On a feature, bugfix or hotfix, run the tests that cover what you
  changed, while developing and before `/apogee:finish`; add tests for new behaviour. The full
  suite runs only in the release preparation, or when the user asks; CI runs it again.
