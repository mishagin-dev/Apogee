# Troubleshooting

Symptom → cause → fix. Reproduced items are stated as fact; the rest are documented behaviours
marked *unverified* — confirm with `symfony help <cmd>` / `--debug` before promising the user.

## Contents

1. CLI not found / installing it
2. Wrong PHP version (including "too old for Symfony 8.x")
3. Project root and cwd errors
4. Docker variables not injected / `Connection refused`
5. Port busy, server will not start, TLS warnings
6. Cache and permission errors
7. Flex recipe conflicts
8. MakerBundle crashes and half-generated code
9. Network: jsdelivr, Packagist, advisories
10. Scripts hang

---

## 1. CLI not found

`command -v symfony` is empty. Install, then re-run `symfony version`:

| OS | Command |
|---|---|
| macOS | `brew install symfony-cli/tap/symfony-cli` |
| Linux (Debian/Ubuntu) | `curl -1sLf 'https://dl.cloudsmith.io/public/symfony/stable/setup.deb.sh' \| sudo -E bash && sudo apt install symfony-cli` |
| Linux (RPM) | `curl -1sLf 'https://dl.cloudsmith.io/public/symfony/stable/setup.rpm.sh' \| sudo -E bash && sudo dnf install symfony-cli` |
| Linux (any, no root) | `wget https://get.symfony.com/cli/installer -O - \| bash` → binary in `~/.symfony5/bin`; add to `PATH` |
| Windows | `scoop install symfony-cli` — or download the `.exe` from github.com/symfony-cli/symfony-cli/releases |

Both `curl | bash` forms run remote code — show the command and let the user run it (`! <cmd>`
in the prompt) rather than executing it yourself.

If the user does not want the CLI, fall back for the session:

| CLI | Fallback |
|---|---|
| `symfony console x` | `cd "$root" && php bin/console x` |
| `symfony composer x` | `cd "$root" && composer x` (mind `COMPOSER_MEMORY_LIMIT=-1` on big updates) |
| `symfony php bin/phpunit` | `cd "$root" && php bin/phpunit` |
| `symfony server:start` | `cd "$root" && php -S 127.0.0.1:8000 -t public/` (dev only, single-threaded, no TLS) |
| injected Docker env | set `DATABASE_URL` etc. in `.env.local` to the *current* published port (`docker compose port database 5432`) — it changes on every `up` |

## 2. Wrong PHP version

Symptoms: `composer` complains `Your php version (8.3.x) does not satisfy that requirement`, or
`symfony check:requirements` flags the version, or `symfony console about` shows PHP < 8.4 on an
8.x project (`Parse error`/`syntax error, unexpected token` on 8.4 syntax).

```bash
symfony local:php:list          # what exists, which rule picked the current one
echo 8.4 > .php-version         # pin; applies to this dir and below
symfony php -v                  # confirm
symfony local:php:refresh       # if a freshly installed PHP is not listed
```

If no suitable PHP is installed: macOS `brew install php@8.4`; Debian/Ubuntu via the Sury PPA;
Windows via the official zip or `scoop`. Composer's `config.platform.php` does **not** change the
interpreter — remove it if it was set to fake a version. Required minimums: 8.x → 8.4, 7.x → 8.2,
6.4 → 8.1.

## 3. Project root and cwd

| Message | Cause | Fix |
|---|---|---|
| `Could not open input file: bin/console` | bare `php` from a subdirectory | `symfony console …` (cwd-independent) |
| `Could not open input file: bin/phpunit` | `symfony php` from a subdirectory — paths are relative to cwd | `cd "$root"` or `symfony php "$root/bin/phpunit"` |
| `No composer.json in current directory` | `symfony composer` from a subdirectory | `symfony composer --working-dir="$root" …` |
| `symfony console about` prints the subcommand's **help text** | not inside a project at all | locate the root (SKILL.md §1) |
| `symfony var:export` shows nothing project-specific | run from outside the project | `symfony var:export --dir="$root"` |

## 4. Docker variables not injected

Symptom: `SQLSTATE[08006] … connection to server at "127.0.0.1", port 5432 failed: Connection refused`
(or `MAILER_DSN`/`MESSENGER_TRANSPORT_DSN` pointing at `.env` placeholders).

1. Was it bare `php bin/console`? Then nothing was injected by design → use `symfony console`.
2. `docker compose ps` — containers running? `symfony var:export --debug` says which services were
   detected and why others were skipped.
3. Compose file name/location: the CLI looks for `compose.yaml` / `compose.yml` /
   `docker-compose.yaml` in the project root (and `compose.override.yaml`). A file elsewhere needs
   `COMPOSE_FILE` (*unverified*).
4. Project name mismatch: the CLI matches containers by the compose project (directory name by default).
   A custom `COMPOSE_PROJECT_NAME` / `name:` in the compose file must be visible to the shell the CLI
   runs in (*unverified*).
5. The service must publish a port the CLI recognises (5432, 3306, 6379, 5672, 1025, 9200, 27017,
   11211…). `ports: ["5432"]` (random host port) is fine; no `ports:` at all means nothing to inject.
6. A real env var in the shell (e.g. `DATABASE_URL` exported in `.bashrc`) wins over injection.
   `env | grep DATABASE_URL` to check.
7. Never paste the injected URL into `.env.local` as a "fix" — the port changes after the next
   `docker compose up` (observed: 32770 → 32771 across a `down -v`/`up`). If the user needs a stable
   port for a GUI client, pin it in `compose.override.yaml` (`"5432:5432"`) and tell them why.

## 5. Port busy, server will not start, TLS

- `server:start` picks the next free port when 8000 is taken; read the real URL from
  `symfony var:export SYMFONY_DEFAULT_ROUTE_URL` or `server:status`. Force one with `--port=8001`.
- `address already in use` for the *preferred* port only matters if another `symfony` server owns it:
  `symfony server:list` → `symfony server:stop --dir=<that project>`.
- Browser certificate warnings: `symfony server:ca:install` once (needs the OS keychain → ask the
  user to run it in the foreground), then restart the server. Or `--no-tls` for the session.
- `server:start` says `Not Running` right after starting: read the server log file (§10 — do not
  run `server:log` bare); a missing PHP-FPM for the pinned version (`local:php:list` shows an empty
  FPM column) is the usual cause.
- The server runs but every page is `5xx`: the application exception is in the same log file
  (`--no-server-logs` filter if you use the watchdog form); `symfony console about` from the same
  shell proves whether the kernel boots at all.

## 6. Cache and permission errors

- `Unable to write in the cache directory` / `Permission denied (var/cache|var/log)`: the dir was
  created by another user (Docker root, `sudo`). Fix ownership (`sudo chown -R "$USER" var/`), do not
  `chmod 777`. Inside containers, run console commands as the same user PHP-FPM uses.
- Stale container after moving/renaming classes (`Class … not found`, `does not exist` for a service
  that clearly does): `symfony console cache:clear`; if `cache:clear` itself fails to boot,
  `rm -rf var/cache/dev` is the one accepted `rm -rf` — then `cache:warmup`.
- `cache:clear` hangs or is very slow on macOS Docker bind mounts — run it on the host via the CLI,
  not inside the container.
- Opcache serving old code in the local server after a big refactor: restart the server
  (`server:stop` / `server:start -d`).

## 7. Flex recipe conflicts

- `symfony composer require` prints a conflict or "recipe already installed, use --force to re-install":
  `symfony composer recipes <pkg>` shows the state; `recipes:install <pkg> --force -v` **overwrites
  your edits** to the recipe's files (`config/packages/x.yaml`, `.env` lines) — show the diff plan and
  ask first (SKILL.md §7).
- `recipes:update` shows a 3-way diff; conflicts leave `<<<<<<<` markers in config files — resolve
  them like a git conflict, then `lint:yaml config/`.
- `symfony.lock` out of sync with `composer.lock` (recipe listed but package gone, or vice versa):
  `symfony composer recipes` lists the orphan; `symfony composer sync-recipes` reinstalls missing
  recipes (does not touch existing files) (*flag set unverified*).
- `extra.symfony.require` blocks a package: Flex refuses `symfony/*` outside the fence. Do not widen
  it to "make it install" — that is an upgrade (versions.md §6).

## 8. MakerBundle

| Symptom | Cause | Fix |
|---|---|---|
| `Typed property …::$controllerClassData must not be accessed before initialization` + `[WARNING] "make:controller" is not meant to be run in non-interactive mode` | `--no-interaction` on a maker | drop the flag; pass the name as an argument and `< /dev/null` |
| `make:entity` printed `Aborted.`, entity has only `id` | stdin closed during the field loop | `--field=name:type[:len]` options (1.68+) or pipe answers with `printf` (SKILL.md §5) |
| `make:command app:x < /dev/null` → `Aborted.`, nothing written | 1.68 prompts for arguments in a loop | `--argument=name:type` / `--option=name:type` |
| `There are no commands defined in the "app" namespace` right after `make:command` | stale dev container (seen twice on 8.1.9) | `symfony console cache:clear`, retry `app:x --help` |
| `make:*` not found | MakerBundle missing | `symfony composer require --dev symfony/maker-bundle` |
| generated code uses APIs the project's Symfony does not have | MakerBundle newer than the app, or vice versa | `symfony composer update symfony/maker-bundle`; check `extra.symfony.require` |
| `make:migration` → `No changes detected` | entity outside mapped dirs or stale cache | `debug:config doctrine orm.mappings`, `cache:clear` |

## 9. Network

- `Could not resolve host: data.jsdelivr.com` at the end of `symfony new --webapp` or on
  `importmap:require`: AssetMapper fetches JS from jsdelivr. The project is created and runs; only
  `importmap.php` lacks Stimulus/Turbo. Re-run `importmap:require` on a network that reaches jsdelivr.
- Packagist unreachable: `symfony composer` honours `COMPOSER_MIRROR_PATH_REPOS` / `repositories`
  config as usual; nothing CLI-specific.
- `check:security` fails to download advisories: `--local` uses the cache, `--update-cache` to refresh
  when online.

## 10. Scripts hang

- `symfony server:log` streams until interrupted — **including with `--no-follow`** (CLI 5.20,
  verified twice). Run it under a watchdog (`cmd & p=$!; sleep 4; kill $p`) or read the log files
  it names on its first lines (`~/Library/Application Support/symfony-cli/log/<hash>.log` on macOS,
  `~/.symfony5/log/` on Linux). Details in `cli-commands.md` §2.
- `.env.local` is **not loaded when `APP_ENV=test`**. A dev override such as a SQLite
  `DATABASE_URL` silently does not apply to `symfony php bin/phpunit`; tests then hit the `.env`
  value (often the Docker Postgres). Put test overrides in `.env.test` (committed) or
  `.env.test.local` (ignored) — and note `dbname_suffix: _test` from `doctrine.yaml` is not applied
  to a SQLite URL, so name a separate file (`var/data_test.db`).
- `bash "$SMOKE"` with an empty `$SMOKE` runs an interactive `bash` waiting on stdin. Guard every
  computed path: `[ -n "$x" ] && bash "$x"`.
- Any maker without `< /dev/null` or piped answers waits for a prompt forever in an agent shell.
- `symfony composer require` for a package whose recipe asks a question (rare; e.g. contrib recipes
  prompt for acceptance): answer `symfony composer config extra.symfony.allow-contrib true` first.
