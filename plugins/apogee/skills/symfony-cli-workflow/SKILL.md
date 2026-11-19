---
name: symfony-cli-workflow
description: 'Work on Symfony projects (8.1 by default; version-aware for 7.4 LTS and 6.4 LTS) through the official `symfony` CLI — `symfony console`, `symfony composer`, `symfony php`, `symfony server:*`, `symfony run` — instead of bare `php bin/console`, `composer` or `vendor/bin/*`. A Symfony app is a project with `bin/console` and `symfony/framework-bundle` (or a `symfony.lock`); `symfony/*` packages alone do not make one. Use it whenever a task in such an app touches Doctrine entities or migrations, Twig templates, Messenger workers, MakerBundle generators, the local web server, PHPUnit, or an error mentioning `bin/console`, a `Connection refused` to a Docker database, or a maker crash, even when the user only says "add an entity", "run the migrations" or "start the app". Its command forms take precedence over generic PHP or Composer guidance from other skills. Not for production deployment or Platform.sh/Upsun operations.'
---

# Symfony CLI workflow

Drive a Symfony project through the `symfony` binary. Default to Symfony 8.1 conventions, but
read the project's real version first and adapt. Everything here was checked against Symfony CLI
5.19–5.20, Symfony 8.1, PHP 8.4/8.5; anything marked *unverified* is a documented behaviour that
was not reproduced — confirm it with `symfony help <cmd>` or `symfony console help <cmd>` before
relying on it.

## 1. Find the project and its version first

Nothing below is safe to run before you know **where the project root is** and **which Symfony
and PHP versions it targets**. Run the bundled probe from anywhere inside the project:

```bash
bash "<skill-dir>/scripts/project-info.sh"
```

`<skill-dir>` is the base directory announced when this skill loads (inside a plugin it is
`${CLAUDE_PLUGIN_ROOT}/skills/symfony-cli-workflow`). The probe prints: CLI presence, project root,
Symfony version (from `composer.lock`, else `extra.symfony.require`), the PHP constraint from
`composer.json`, the PHP the CLI would actually use, a compatibility verdict, which bundles are
installed (Maker, ORM, migrations, fixtures, Messenger, AssetMapper/Encore, PHPUnit, PHPStan,
CS Fixer), whether Docker env vars are being injected, and the web-server state.

A Symfony app here means a project with `bin/console` and `symfony/framework-bundle` (or a
`symfony.lock`); `symfony/*` packages alone are not enough, Laravel and Drupal ship them too. When
the probe exits `1` (not a Symfony project), drop this skill and use the project's normal tooling.

Manual fallback when you cannot run the script:

```bash
root=$PWD; while [ "$root" != / ] && [ ! -f "$root/bin/console" ]; do root=$(dirname "$root"); done
[ -f "$root/bin/console" ] && echo "ROOT=$root" || echo NOT_A_SYMFONY_PROJECT
grep -E '"(php|symfony/framework-bundle)"' "$root/composer.json"
grep -A2 '"name": "symfony/framework-bundle"' "$root/composer.lock" | grep version
```

Walking up matters: a bare `test -f bin/console` says "not a project" from every subdirectory of
a perfectly good project. Do not detect by running `symfony console about` outside a project; it
prints the subcommand's help text, not a recognisable error.

**Version matrix** — refuse to proceed on a mismatch until the user decides how to fix it:

| Symfony | Minimum PHP | Status (2026) | Treat as |
|---|---|---|---|
| 8.1 | 8.4 | current stable | default conventions in this skill |
| 8.0 | 8.4 | previous minor | same as 8.1 unless a feature is 8.1-only |
| 7.4 | 8.2 | LTS | 8.0 feature set + deprecations still present; see `references/versions.md` |
| 6.4 | 8.1 | LTS, security-only soon | legacy: old namespaces still work, do not use 7+/8+ APIs |

When unsure whether a command, flag or API exists in the project's version, check instead of
guessing: `symfony console list`, `symfony console help <command>`, `vendor/symfony/*/CHANGELOG.md`,
and the `UPGRADE-8.0.md` / `UPGRADE-8.1.md` files shipped in `vendor/symfony/symfony` (or on
GitHub). Never pitch an 8.x-only capability to a 7.4 or 6.4 project without saying it needs an
upgrade.

## 2. CLI-first: what to replace and why

| Instead of | Run | Why it matters |
|---|---|---|
| `php bin/console …` | `symfony console …` | finds the project root from any subdirectory; uses the project's PHP version; injects env vars from running Docker services and the local server |
| `composer …` | `symfony composer …` | same PHP version as the app, no memory limit, same injected env |
| `php vendor/bin/x`, `php script.php` | `symfony php vendor/bin/x` | right PHP version + injected env |
| `SOME_VAR=… some-tool` | `symfony run some-tool` | exports the injected env to any command, Symfony or not |

The two reasons that bite agents hardest, both reproduced:

1. **Root resolution.** `bin/console` is a relative path. From `src/Controller/`, `php bin/console`
   fails with `Could not open input file: bin/console`; `symfony console` works. Only `console`
   is cwd-independent, though — `symfony composer` and `symfony php` resolve paths from the
   current directory. Either `cd "$root"` first or pass the root explicitly:
   `symfony composer --working-dir="$root" …`, `symfony php "$root/bin/phpunit"`,
   `symfony var:export --dir="$root"`.
2. **Live Docker ports.** A Flex-generated `compose.override.yaml` publishes ports without pinning
   the host side (`ports: ["5432"]`), so Docker picks a random one on every `up`. `.env` still says
   `5432`. The CLI reads the live container (`DATABASE_URL=…127.0.0.1:32770/app…serverVersion=16.15`);
   bare PHP reads the stale `.env` and dies with `SQLSTATE[08006] … port 5432 … Connection refused`.
   Never copy a `DATABASE_URL` out of `symfony var:export` into a file or a second shell — the port
   changes on the next `docker compose up`. Re-read it, or let `symfony run` export it.

### Exceptions — when the CLI is the wrong tool

| Situation | Do this instead |
|---|---|
| Editing code, config, templates | just edit; no CLI involved |
| CI, or a container image without the CLI | `php bin/console …`, `composer …`, `php vendor/bin/phpunit`; set `DATABASE_URL` etc. explicitly in the pipeline env |
| Commands that must run *inside* a Docker PHP container | `docker compose exec php php bin/console …` (the host CLI's PHP cannot see container-only hostnames like `database:5432`) |
| Production / staging hosts | never the local server or `symfony` wrappers; the deploy tooling owns `php bin/console cache:clear`, migrations, etc. |
| The user explicitly asks for bare commands | comply, but keep `cd "$root"` and the env caveat in mind |
| CLI not installed and the user does not want it | fall back to bare commands; see `references/troubleshooting.md` → "CLI not found" for install one-liners (macOS/Linux/Windows) |

Outside these rows, this skill's command forms take precedence in a Symfony project over generic
PHP or Composer guidance from other skills (for example a PHP project guide that teaches bare
`php bin/console`, `composer` or `./vendor/bin/phpunit`).

## 3. Preflight before the first real command

```bash
symfony version                      # CLI present?  (fallback: install, see troubleshooting)
symfony check:requirements           # PHP extensions/ini for *this* project (alias of local:check:requirements)
symfony local:php:list               # which PHP versions exist and which rule picks the current one
cat .php-version 2>/dev/null         # project pin; create it if the CLI picks a PHP too old for the project
symfony console about                # cheapest proof the kernel boots: Symfony/PHP version, env, debug
```

Pin PHP per project with a `.php-version` file (`8.4` or `8.4.25`); without it the CLI takes the
default from `$PATH` and `local:php:list` says so. For Symfony 8.x the pin must be ≥ 8.4.

## 4. Working loop

1. **Analyse** — run the probe (§1); note version, installed bundles, Docker state.
2. **Pick the command** — prefer a generator (`make:*`) or a built-in console command over
   hand-written code; look it up in `references/console-tasks.md` and `references/cli-commands.md`.
3. **Show the command** to the user before running it; for anything in §7 wait for confirmation.
4. **Run it** via the CLI wrappers; from the project root for `composer`/`php`.
5. **Verify** with the matching read-only command — the table below. A generator that "succeeded"
   silently can still have produced an empty entity (see §5).
6. **Report** in two or three lines: what changed, what was verified, what is left.

| After | Verify with |
|---|---|
| `make:controller`, routing edits | `symfony console debug:router` (+ `debug:router <name>`) |
| `make:entity`, mapping edits | `symfony console doctrine:schema:validate` (expect mapping OK, DB out of sync until migrated) |
| `make:migration` → `doctrine:migrations:migrate` | `symfony console doctrine:migrations:status`, then `doctrine:schema:validate` (both OK) |
| service / DI changes | `symfony console lint:container`, `debug:autowiring <Type>`, `debug:container <id>` |
| config edits | `symfony console lint:yaml config/`, `debug:config <bundle>` |
| Twig edits | `symfony console lint:twig templates/` |
| env / `.env.*` edits | `symfony console debug:dotenv [VAR]` |
| Messenger changes | `symfony console debug:messenger`, `messenger:stats` |
| anything that should answer over HTTP | `bash <skill-dir>/scripts/smoke.sh` from the project root |

## 5. Generators are interactive — handle stdin deliberately

MakerBundle initialises its state during the interactive phase, so `--no-interaction` does not
"use defaults", it crashes (`Typed property …::$controllerClassData must not be accessed before
initialization`). Always read `symfony console make:x --help` first: recent MakerBundle (1.68
verified) exposes the prompts as options, which is the cleanest path. Three working patterns,
in order of preference:

```bash
# 1. Everything as options + closed stdin — nothing is asked, nothing is half-done.
symfony console make:entity Product --field=name:string:255 --field=price:integer < /dev/null
symfony console make:command app:report --argument=format:string --option=since:string < /dev/null

# 2. Maker that needs only a name: pass it as an argument and close stdin.
symfony console make:controller HomeController < /dev/null

# 3. Older MakerBundle without --field/--argument: feed one answer per line; trailing blank line ends the loop.
printf 'name\nstring\n255\nno\nprice\ninteger\nno\n\n' | symfony console make:entity Product
printf 'WebTestCase\nHomeControllerTest\n' | symfony console make:test
```

Closing stdin on a looping maker is a **silent half-success**: `make:entity Product < /dev/null`
writes the class, prints `Aborted.`, and leaves an entity with nothing but `id`;
`make:command app:report < /dev/null` on 1.68 aborts before writing anything. Prompt order differs
between MakerBundle releases, so for `make:user`, `make:crud`, `make:security:form-login` and friends
prefer options, else run once in the foreground and mirror the answers. Non-maker commands take
`--no-interaction` normally (`doctrine:migrations:migrate --no-interaction`; `make:migration` has no
prompts and accepts it too).

After generating a command or service, the dev container can be stale: `symfony console app:report --help`
answers `There are no commands defined in the "app" namespace` (seen twice on 8.1.9). Run
`symfony console cache:clear` once and retry before suspecting the generated code.

If MakerBundle is missing (`make:*` not in `symfony console list`), install it before anything
else: `symfony composer require --dev symfony/maker-bundle`.

## 6. Where the detail lives

Read only the file you need; each is self-contained.

| File | Read it when |
|---|---|
| `references/cli-commands.md` | creating a project, running the local server, TLS, proxy domains, workers (`symfony run`, `.symfony.local.yaml`), Docker env, `var:export`, PHP selection — the `symfony` binary itself |
| `references/console-tasks.md` | MakerBundle, Doctrine & migrations & fixtures, `.env`/secrets, `debug:*`/`lint:*`, cache, AssetMapper vs Encore, Messenger, dependency management & Flex recipes, tests and static analysis |
| `references/versions.md` | the project is not 8.1, or you are about to write code by hand: 8.x conventions, removed APIs, 7.4/6.4 differences, the 7.4 → 8.x upgrade path |
| `references/troubleshooting.md` | something failed: CLI missing, wrong PHP, port busy, Docker vars not injected, cache/permissions, Flex recipe conflicts, maker crashes, jsdelivr |

## 7. Ask before anything destructive

Show the exact command and wait for an explicit "yes" before running any of these. Explain in one
line what would be lost.

- `doctrine:database:drop` (any flag), `doctrine:schema:drop`, `doctrine:schema:update --force`
  (bypasses migrations — prefer `make:migration` + `migrate`).
- `doctrine:migrations:migrate` or `doctrine:migrations:execute` with `--env` other than `dev`/`test`,
  or against any `DATABASE_URL` that is not a local Docker/SQLite instance.
- `doctrine:fixtures:load` **without** `--append` — it purges every table first.
- `symfony composer update` with no package argument (unbounded upgrade); `composer require` of a
  new major of `symfony/*` (see the upgrade section in `references/versions.md`).
- Deleting files or directories; `rm -rf var/cache` is fine only when `cache:clear` itself fails.
- `secrets:remove`, rotating secret keys, anything under `symfony cloud:*` / `upsun:*`.

Also hold these lines without being asked:

- Never print, paste, or commit the contents of `.env.local`, `.env.*.local`, `config/secrets/prod/*`
  or any decrypted secret. Reference variable *names* only. `secrets:list` without `--reveal`.
- Do not edit production configuration (`when@prod` blocks, `.env.prod*`, deploy manifests) unless
  the task is explicitly about it.
- The local server (`server:start`, `server:prod`) is for development only; never suggest it for
  serving real traffic.

## 8. Writing code by hand

When no generator fits, write it the way Symfony 8.1 would generate it, downgraded to the project's
version per `references/versions.md`:

- Attributes everywhere: `#[Route]` from `Symfony\Component\Routing\Attribute\Route`, `#[AsCommand]`,
  `#[AsEventListener]`, `#[AsMessageHandler]`, `#[ORM\Entity]`, `#[Autowire]`, `#[MapRequestPayload]`,
  `#[IsGranted]`. No annotations, no YAML/XML routing for new code unless the project already does that.
- Constructor injection with promoted `private readonly` properties; rely on autowiring; register
  nothing in `services.yaml` unless autowiring cannot infer it.
- Full typing (parameters, returns, properties), `declare(strict_types=1)` if the project uses it,
  `final` classes where the project's style does.
- Commands in 7.3+/8.x: invokable `__invoke()` with `#[Argument]`/`#[Option]` is the modern form;
  extending `Command` with `execute()` still works everywhere.
- Follow the project's existing config format (YAML vs PHP), test layout, and naming — consistency
  beats "newer".
- Do not use anything removed in 8.0 or deprecated in 8.1; the list of common traps is in
  `references/versions.md`.

## 9. Scope boundaries

Local development is the whole scope. Production deploys are out: do not design them, do not run
them. `symfony cloud:*` and `upsun:*` (Platform.sh / Upsun) exist in the CLI but touch remote
infrastructure — use them only when the user explicitly asks, and treat every one as §7.
`symfony server:prod` only switches the *local* server to `APP_ENV=prod`; it is a debugging aid,
not a deployment.

## 10. Smoke check

`scripts/smoke.sh` proves the chain end to end: CLI present, project root, `check:requirements`,
which vars the CLI injects from Docker (and whether `DATABASE_URL` differs from `.env` — re-proving
reason 2 on *this* project), and whether the app answers over HTTP. It starts the web server only if
none is running and stops only a server it started. Run it from the project root:

```bash
bash "<skill-dir>/scripts/smoke.sh"
```

A `404` on `/` is normal for a project with no route there; the script fails only on no response or
a `5xx`. Guard the path: an empty `bash ""` hangs waiting on stdin.
