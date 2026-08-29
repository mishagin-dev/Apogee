---
name: symfony
description: 'Drive a Symfony project through the official `symfony` CLI instead of bare `php bin/console` / `composer` / `vendor/bin/*`. Use when running or starting a Symfony app, its local web server, console commands, Doctrine migrations, MakerBundle generators (make:entity, make:controller, make:test), PHPUnit, or a security audit — and whenever a Symfony command failed with "Could not open input file", "Connection refused", or a MakerBundle crash. Applies only inside a Symfony project.'
---

# Symfony Skill

## Precondition

This skill applies only to a Symfony project. Locate the project root before running
anything — this both gates the skill and gives you the directory `symfony composer` and
`symfony php` require (see Reason 1):

```bash
root=$PWD; while [ "$root" != / ] && [ ! -f "$root/bin/console" ]; do root=$(dirname "$root"); done
[ -f "$root/bin/console" ] && echo "SYMFONY_ROOT=$root" || echo NOT_A_SYMFONY_PROJECT
```

Walking up matters: a bare `test -f bin/console` answers `NOT_A_SYMFONY_PROJECT` from every
subdirectory of a perfectly good project. Do not try to tell the two cases apart by running
`symfony console about` outside a project — it prints the subcommand's help text
(`Runs the Symfony Console (bin/console) for current project`), not a recognisable error.

## The rule

**Drive every operation through the `symfony` binary.** Never call `php bin/console`,
bare `composer`, or `vendor/bin/*` directly. This is not a style preference — the two
sections below are the measured reasons, both reproduced on Symfony 8.1.5 / PHP 8.5.9 /
Symfony CLI 5.19.0.

## Reason 1 — the CLI resolves the project root; bare PHP does not

`bin/console` is a *relative path*. From any subdirectory it does not exist:

```bash
cd src/Controller && php bin/console about
# Could not open input file: bin/console
```

`symfony console` walks up to the project root itself, so the same call from the same
directory works. That removes a whole class of agent error — no bookkeeping about where
the shell currently is.

**The fix is narrower than it looks.** Only `console` is cwd-independent:

| Command | Works from a subdirectory? | Observed failure |
|---|---|---|
| `symfony console <cmd>` | **yes** — finds the project root | — |
| `symfony composer <cmd>` | **no** | `No composer.json in current directory` |
| `symfony php <script>` | **no** — the script path is relative to cwd | `Could not open input file: bin/phpunit` |

So: `symfony console` from anywhere; **`cd` to the project root** before `symfony composer`
or `symfony php`.

## Reason 2 — the CLI injects env vars from running Docker services

A Flex-generated `compose.override.yaml` publishes ports **without pinning the host side**
(`ports: - "5432"`), so Docker assigns a random one on every `up`. `.env` still carries the
placeholder `5432`. The CLI reads the live Docker state; PHP reads the stale `.env`:

```bash
docker compose up -d
symfony var:export --multiline | grep DATABASE_URL
# export DATABASE_URL=postgres://app:!ChangeMe!@127.0.0.1:32770/app?sslmode=disable&charset=utf8&serverVersion=16.15
grep '^DATABASE_URL' .env
# DATABASE_URL="postgresql://app:!ChangeMe!@127.0.0.1:5432/app?serverVersion=16&charset=utf8"
```

Both sides of the consequence, run back to back against the same container:

```bash
php bin/console doctrine:database:create
# An exception occurred in the driver: SQLSTATE[08006] [7] connection to server at
# "127.0.0.1", port 5432 failed: Connection refused

symfony console doctrine:database:create
# An exception occurred while executing a query: SQLSTATE[42P04]: Duplicate database:
# 7 ERROR:  database "app" already exists
```

The CLI also substitutes the *detected* server version (`serverVersion=16.15`) for the
hardcoded `16`, which is what Doctrine uses to pick platform-specific SQL.

`symfony run <cmd>` exports the same variables to any command, not just Symfony's:

```bash
symfony run printenv DATABASE_URL
```

## Verified command map

Every command below was executed in this project layout.

| Task | Command |
|---|---|
| New project | `symfony new --webapp <dir>` |
| Environment sanity | `symfony check:requirements` |
| Known CVEs in dependencies | `symfony check:security` |
| PHP versions + how one is selected | `symfony local:php:list` |
| Any console command | `symfony console <cmd>` |
| Composer (root only) | `symfony composer <cmd>` |
| A PHP script with injected env (root only) | `symfony php vendor/bin/phpunit` |
| Any command with injected env | `symfony run <cmd>` |
| Start / stop the web server | `symfony server:start -d` · `symfony server:stop` |
| Server state | `symfony server:status` |
| Show injected env | `symfony var:export --multiline` |

Pin the PHP version per project with a `.php-version` file; without it the CLI takes the
default from `$PATH` (`symfony local:php:list` prints which rule applied).

## MakerBundle is interactive, and `--no-interaction` breaks it

MakerBundle initializes its state inside the interactive phase, so suppressing that phase
crashes the generator instead of using defaults:

```bash
symfony console make:controller HomeController --no-interaction
# [WARNING] "make:controller" is not meant to be run in non-interactive mode.
# Typed property Symfony\Bundle\MakerBundle\Maker\MakeController::$controllerClassData
#   must not be accessed before initialization
```

**Pass the name as an argument and close stdin instead** — `interact()` runs, sees the
argument is already supplied, and asks nothing:

```bash
symfony console make:controller HomeController < /dev/null
# created: src/Controller/HomeController.php
# created: templates/home/index.html.twig
```

For a generator that keeps prompting in a loop (`make:entity` asks for field after field),
closing stdin is a **silent half-success**: the files are written, the loop reports
`Aborted.`, and the entity ends up with nothing but `id`. Feed the answers instead — one
line per prompt, a trailing empty line to end the loop:

```bash
printf 'name\nstring\n255\nno\nprice\ninteger\nno\n\n' | symfony console make:entity Product
#   #[ORM\Column(length: 255)] private ?string $name = null;
#   #[ORM\Column]              private ?int $price = null;

printf 'WebTestCase\nHomeControllerTest\n' | symfony console make:test
```

Non-maker commands take `--no-interaction` normally:
`symfony console doctrine:migrations:migrate --no-interaction`.

## Smoke check

`smoke.sh` proves the whole chain — CLI present, project root, requirements, which vars the
CLI injects from Docker, and whether the app answers over HTTP. It starts the web server only
if one is not already running, and stops only a server it started itself.

Resolve it from the installed plugin (the path is version-pinned — never hardcode it), then
run it **from the project root**:

```bash
SMOKE=$(find ~/.claude/plugins/cache/apogee -path '*/skills/symfony/smoke.sh' 2>/dev/null | sort -V | tail -1)
[ -n "$SMOKE" ] && bash "$SMOKE" || echo "smoke.sh not found in the plugin cache"
```

The guard matters: an unguarded `bash "$SMOKE"` on an empty match runs `bash` with no
arguments and hangs waiting on stdin. If the match is empty, the installed plugin version
predates this skill — cross-check
`~/.claude/plugins/installed_plugins.json` → `.plugins["apogee@apogee"][0].installPath`
and append `/skills/symfony/smoke.sh`.

Output on a healthy project with Docker services up:

```
== toolchain ==
  OK   Symfony CLI version 5.19.0 ...
== project ==
  OK   Symfony project root (/tmp/apogee-sf-probe/demo)
  OK   check:requirements
== injected env (from running Docker services) ==
  OK   26 service var(s) injected — bare 'php bin/console' would NOT see these
       export DATABASE_URL=postgres://app:!ChangeMe!@127.0.0.1:32771/app?...
       export MAILER_URL=smtp://127.0.0.1:32772
  ---  DATABASE_URL differs from .env — bare 'php bin/console' would use the stale one:
       .env: postgresql://app:!ChangeMe!@127.0.0.1:5432/app?serverVersion=16&charset=utf8
== http ==
  OK   http://127.0.0.1:8000/ -> 404
  ---  stopped the server this script started

SMOKE OK
```

The `DATABASE_URL differs` line is the point: it re-proves Reason 2 on *your* project
instead of asking you to trust the numbers above.

A `404` on `/` is normal for a project with no route mapped there — the smoke check reports
the status code rather than judging it, and only fails on no response at all or a `5xx`.

## Gotchas

- **`symfony server:log` never returns.** It streams until interrupted. Running it in the
  foreground hangs the session (killed at 143 on timeout). Only run it detached, or read the
  log files it names on its first two lines.
- **`symfony server:status` exits `0` whether or not the server runs.** The state is in
  stdout only, so `if symfony server:status; then …` is always true. Parse the output for
  `Not Running` — and capture it into a variable rather than piping to `grep -q`, because
  under `set -o pipefail` grep closes the pipe on a match, `symfony` dies of `SIGPIPE`, and
  the pipeline reports failure on a *successful* match. `smoke.sh` does it the safe way.
- **The Docker port changes on every `docker compose up`.** Observed directly: the same
  project came up on `32770`, then on `32771` after a `down -v` / `up` cycle. Never copy a
  `DATABASE_URL` out of `var:export` into a file or a second shell — re-read it each time,
  or use `symfony run`.
- **`symfony new --webapp` needs `data.jsdelivr.com`,** not just Packagist: the AssetMapper
  recipe runs `importmap:require` for Stimulus/Turbo as a post-install step. On a network
  that resolves Packagist but not jsdelivr it fails at the very end with
  `Could not resolve host: data.jsdelivr.com`. The project is still created and usable —
  only `importmap.php` is left with just the `app` entry.
- **`symfony console` boots the app**, so a fatal error in config surfaces here rather than
  in the CLI. `symfony console about` is the cheapest end-to-end check that the kernel boots.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Could not open input file: bin/console` | ran bare `php` from a subdirectory | `symfony console <cmd>` |
| `Could not open input file: bin/phpunit` | `symfony php` does not rewrite script paths | `cd` to the project root |
| `No composer.json in current directory` | `symfony composer` from a subdirectory | `cd` to the project root |
| `SQLSTATE[08006] … port 5432 … Connection refused` | bare `php` used the `.env` placeholder port | `symfony console …` |
| `Typed property …$controllerClassData must not be accessed before initialization` | `--no-interaction` on a maker command | argument + `< /dev/null` |
| `make:entity` printed `Aborted.` and the entity has only `id` | stdin closed during the field loop | pipe answers with `printf` |
| `Could not resolve host: data.jsdelivr.com` | AssetMapper recipe needs jsdelivr | the project is created and usable; only the importmap is incomplete — restore it on a network that reaches jsdelivr (not verified here) |
