---
name: git-commit
description: This skill should be used whenever creating a git commit or writing a commit message — when the user asks to "commit", "create a commit", "git commit", "write a commit message", "commit my changes", or "conventional commit". Generates a Conventional Commits message from the staged diff (falling back to all changes), validates it against strict rules, and creates the commit. Commit messages are always written in English. Applies only inside a git repository.
---

# git-commit

## Precondition — git repository required

This skill operates only inside a git repository. Before anything else, check:

!`git rev-parse --is-inside-work-tree 2>/dev/null && echo GIT_OK || echo NOT_A_GIT_REPO`

If the line above reads `NOT_A_GIT_REPO`, **stop immediately** and tell the
user this directory is not a git repository; do not run the scripts below.

Write a Conventional Commits message from the current diff, validate it,
and create the commit. **Commit messages are always English** (ASCII only).

This skill is the single path for committing: whenever a commit is needed,
follow the workflow below rather than calling `git commit` ad hoc. It is
driven by two scripts:

- `scripts/gather-context.sh` — collects the diff + history to summarize.
- `scripts/check-message.sh` — validates a candidate message against every
  rule and exits non-zero with specific violations (the runnable harness).

> Paths below are relative to this skill directory. Run them from the target
> git repository (the scripts operate on the repo of the current directory).

## Workflow (the agent path)

1. **Gather context.** From inside the target repo:

   ```bash
   bash scripts/gather-context.sh
   ```

   It prints the scope in use (STAGED, or a fallback notice for ALL changes),
   `git status --short`, the recent `git log --oneline -10` (match its style),
   the diffstat, and the full diff. If nothing is staged it falls back to all
   modified tracked files; if only untracked files exist it tells you which
   `git add` to run, then exits non-zero.

2. **Compose the message** following the Rules below. If the diff contains
   multiple unrelated changes, focus on the single most significant one.

3. **Validate** before committing:

   ```bash
   printf '%s' "$msg" | bash scripts/check-message.sh
   ```

   It prints `OK` (exit 0) when valid, or `FAIL: …` lines (exit 1) for each
   violation. Fix every failure and re-validate. `WARN` (subject 51–72 chars)
   does not block but prefer ≤ 50.

4. **Create the commit** using a message file with `-F` (not `-m`, which
   mangles the multi-line body):

   ```bash
   f=$(mktemp); printf '%s\n' "$msg" > "$f"
   git commit -F "$f"
   rm -f "$f"
   ```

## Rules

**Subject line** — `<type>(<scope>): <Summary>`

- Target ≤ 50 characters; **hard cap 72** including the `type(scope):` prefix.
- Capitalize the summary (first letter after `: `).
- No trailing punctuation (`.` `!` `?`).
- Imperative mood — "Add feature", not "Added feature".
- Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
  `chore`, `ci`.
- Scope is optional — omit it when it adds no useful context.
- **English only** (ASCII letters; no Cyrillic, no em-dashes).

**Body** (optional)

- Separate from the subject with one blank line.
- Wrap every line at 72 characters.
- Use it only for context not obvious from the subject (why the change was
  made, important side effects, limitations).
- Do not repeat the subject. Keep it short.

## Example

```
feat(auth): Add OAuth2 login via Google

Handles token refresh automatically on expiry.
Falls back to session auth if provider is unavailable.
```

## Gotchas

- **Use `git commit -F <file>`, not `-m`.** `-m` collapses the multi-line
  body and breaks 72-column wrapping. The temp-file + `-F` path preserves the
  message exactly (verified: `git log -1 --format=%B` returns it intact).
- **`gather-context.sh` won't see untracked files.** `git diff` ignores them,
  so the fallback covers only *modified tracked* files. New files must be
  `git add`-ed first; the script prints the exact `git add` lines for them.
- **Non-ASCII is rejected.** The validator flags any byte outside printable
  ASCII — Cyrillic, smart quotes, em-dashes (`—`) all fail. Use plain ASCII
  punctuation (`-`, `"`, `'`).
- **The validator needs the real `git`/`grep`.** Run the scripts with `bash`
  in the target repo; `check-message.sh` uses POSIX `grep` features only, so
  it works with both BSD (macOS) and GNU (Linux) grep.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ERROR: not inside a git work tree` | `cd` into the repo before running the scripts. |
| `gather-context.sh` exits 2, "only untracked files exist" | `git add` the listed files, then re-run. |
| `FAIL: subject must match …` | Add a valid `type` prefix from the allowed list. |
| `FAIL: subject is N chars; hard cap is 72` | Shorten the subject; move detail to the body. |
| `FAIL: message contains non-ASCII characters` | Replace the flagged characters (em-dash, Cyrillic, smart quotes) with ASCII. |
| Body merged into one line after commit | You used `-m`; recommit with the `-F` temp-file pattern. |

## Enforcement hook (active)

A PreToolUse hook is wired via `hooks.json`:

```
plugins/apogee/hooks/git/enforce-git-commit-skill.py
```

It intercepts every `Bash` call and, when it detects a `git commit` invocation,
checks whether the commit goes through the `-F <file>` temp-file pattern used
by this skill's Workflow (step 4). Commits via `-m`, `--message`, `-am`, or a
bare `git commit` are denied with a reminder to use this skill. The hook is
fail-open: any parse error is silently ignored so unrelated Bash calls are
never blocked.
