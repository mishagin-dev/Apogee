# The `symfony` binary — commands that are not `console`

Every `local:*` command has a short alias without the prefix (`symfony server:start` ≡
`symfony local:server:start`). Flags below were read from `symfony help <cmd>` on CLI 5.20.0; run the
same to confirm on another version. `symfony list` prints everything.

## Contents

1. Creating a project
2. Local web server
3. TLS and the local proxy (custom domains)
4. Workers and background processes
5. Docker Compose integration and `var:export`
6. PHP version selection
7. Wrappers: `console`, `composer`, `php`, `run`
8. Checks: requirements, security
9. Everything else in `symfony list`

---

## 1. Creating a project

```bash
symfony new my_app --version="8.1.*" --webapp      # full web stack (Twig, Doctrine, Maker, AssetMapper, Messenger, …)
symfony new my_app --version="8.1.*"               # minimal skeleton: add packs as you go
symfony new my_app --version=lts --webapp          # LTS (7.4 in 2026) — for long-lived apps that want 3 years of fixes
symfony new my_app --version="8.1.*" --api         # API pack (API Platform)
symfony new my_app --demo                          # the Symfony Demo app, for exploring
```

Useful flags: `--php=8.4` (pins `.php-version`), `--docker` (adds `compose.yaml`), `--no-git`,
`--dir=path`. `--version` accepts a constraint (`"8.1.*"`) or `lts`, `stable`, `next`, `previous`.

Pick `--webapp` for a classic server-rendered app or when the user is unsure; the bare skeleton for
microservices, CLIs, or when the user names the packs they want; `lts` only when the user asks for
LTS or the project must outlive the 8-month support window of a regular minor.

Network note: `--webapp` ends with the AssetMapper recipe running `importmap:require` for Stimulus/Turbo,
which needs `data.jsdelivr.com`. Behind a proxy that resolves Packagist but not jsdelivr the command
fails at the very end with `Could not resolve host: data.jsdelivr.com` — the project is still created;
only `importmap.php` is incomplete (restore later with `symfony console importmap:require @hotwired/stimulus @hotwired/turbo`,
*unverified*).

`symfony project:init` (CLI 5.x) generates Docker/Upsun templates for an existing project — not
needed for local work; mention it only if the user asks for a Docker scaffold.

## 2. Local web server

```bash
symfony server:start -d                 # background (daemon); HTTPS if the CA is installed, else HTTP
symfony server:start -d --port=8001     # preferred port; the CLI picks the next free one if busy
symfony server:start -d --no-tls        # force plain HTTP
symfony server:start --allow-http       # keep HTTP reachable without redirecting to HTTPS
symfony server:status                   # state + URL. Exit code is 0 EVEN WHEN NOT RUNNING — parse stdout for "Not Running"
symfony server:list                     # all local servers on this machine
symfony server:stop
symfony server:log                      # STREAMS FOREVER — even with --no-follow on CLI 5.20 (verified). Never run it bare in an agent shell
symfony server:log --no-app-logs        # filters: --no-worker-logs, --no-server-logs; -n N lines of history
symfony open:local                      # open the app in the browser (--path=/admin)
symfony open:local:webmail              # Mailpit/MailCatcher UI if a mailer container is up
symfony server:prod                     # switch the LOCAL server to APP_ENV=prod; --off to revert
```

The server reads `.symfony.local.yaml` in the project root:

```yaml
# .symfony.local.yaml
http:
    document_root: public/
    port: 8000          # preferred_port: 8001 is the softer variant
    no_tls: false
    allow_http: false
    daemon: true
proxy:
    domains: [my-app]   # attached domains, see §3
workers:                # see §4
    docker_compose: ~
```

`server:status` exits `0` whether or not the server runs. In scripts capture stdout into a variable
and `case` on `*"Not Running"*`; do not pipe to `grep -q` under `set -o pipefail` (grep closes the
pipe on the first match, `symfony` dies of SIGPIPE, and a *successful* match reports failure).

The URL the server actually got (port may differ from 8000) is in the injected env:

```bash
symfony var:export SYMFONY_DEFAULT_ROUTE_URL
```

**Reading logs without hanging.** `server:log` prints the log file paths on its first lines
(`Following Web Server log file (…/symfony-cli/log/<hash>.log)`), then tails them; `--no-follow`
did not stop the tailing in testing. Two safe options:

```bash
# a) bounded run: give it a few seconds, then kill it
( symfony server:log --no-ansi -n 50 & p=$!; sleep 4; kill $p ) 2>/dev/null
# b) read the files directly (macOS path; Linux: ~/.symfony5/log/)
ls -t "$HOME/Library/Application Support/symfony-cli/log/"*.log | head -1 | xargs tail -n 50
```

Worker output (`[messenger_async] …`, `Restarting command`) goes to the same server log.

## 3. TLS and the local proxy

```bash
symfony server:ca:install               # once per machine: local CA so https://127.0.0.1:8000 is trusted
symfony server:ca:uninstall
symfony proxy:start                     # local proxy on 127.0.0.1:7080; serves http://127.0.0.1:7080/proxy.pac
symfony proxy:domain:attach my-app      # project → https://my-app.wip (TLD from proxy:tld)
symfony proxy:domain:detach my-app
symfony proxy:status
symfony proxy:url                       # the PAC URL to configure in the OS/browser proxy settings
symfony proxy:tld                       # show/change the TLD (default .wip)
symfony proxy:stop
```

The OS or browser must point its automatic proxy configuration at the PAC URL for `.wip` domains to
resolve — the CLI cannot do that step; tell the user. Domains are also readable from
`proxy.domains` in `.symfony.local.yaml`. `server:ca:install` may prompt for the system password
(it touches the OS trust store) — run it in the foreground via the user, not from an agent shell.

## 4. Workers and background processes

Ad hoc, with the injected env and optional restart-on-change:

```bash
symfony run -d --watch=config,src,templates,vendor symfony console messenger:consume async -vv
symfony run -d npm run watch                      # Encore / Vite / Tailwind watcher
symfony run printenv DATABASE_URL                 # any command sees the injected env
```

Declarative, started and stopped together with the web server (`server:start` / `server:stop`;
`--no-workers` skips them):

```yaml
# .symfony.local.yaml
workers:
    docker_compose: ~                               # runs `docker compose up` with the server
    messenger_async:
        cmd: ['symfony', 'console', 'messenger:consume', 'async', '--time-limit=3600']
        watch: ['config', 'src', 'templates', 'vendor']
    assets:
        cmd: ['npm', 'run', 'watch']
```

Worker output lands in the server log (see §2 for reading it without hanging).
`--time-limit` on consumers matters: with `watch` the CLI restarts the process on file changes, and
the time limit lets it pick up new code even without a change. The watcher reacts to **writes**
(`notify.Write`), not to a bare `touch` that only bumps mtime — verified: appending a line restarted
the consumer within a second, `touch` did nothing. `server:status` lists each worker with its
`(watching config/, src/)` suffix, which is the quickest way to confirm the config was picked up.

## 5. Docker Compose integration and `var:export`

When a `compose.yaml`/`docker-compose.yaml` is in the project and its services are **running**, the
CLI maps their published ports to env vars for every `symfony console|composer|php|run` invocation
and for the web server: PostgreSQL/MySQL → `DATABASE_URL` (with the detected `serverVersion`),
Redis → `REDIS_URL`, RabbitMQ → `MESSENGER_TRANSPORT_DSN` / `RABBITMQ_*`, Mailpit/MailCatcher →
`MAILER_DSN` / `MAILER_URL`, plus `*_HOST`/`*_PORT` variants.

```bash
docker compose up -d
symfony var:export --multiline               # one `export K=V` per line — the complete injected env
symfony var:export DATABASE_URL              # a single value
symfony var:export --debug                   # why a service was or was not picked up
symfony var:export --dir="$root"             # from outside the project directory
symfony console doctrine:database:create     # uses the live port; bare php would use .env's placeholder
```

Rules that follow:

- `.env` keeps the recipe placeholder (`…@127.0.0.1:5432/app…`). That is fine — do not "fix" it to
  the current random port; it will be wrong after the next `up`. Pin host ports in
  `compose.override.yaml` (`"5432:5432"`) only if the user wants stable ports for non-CLI tools.
- Injection needs the Docker daemon up and the containers running; `var:export --debug` explains
  misses (compose project name mismatch, service not exposing a known port).
- Injection happens from the host's point of view (`127.0.0.1:<published port>`). Commands that
  must run *inside* the PHP container (`docker compose exec php …`) see the compose network names
  (`database:5432`) and do not need the CLI.

## 6. PHP version selection

```bash
symfony local:php:list          # table of detected PHPs + which rule selected the current one
symfony local:php:refresh       # rescan after installing a PHP
echo 8.4 > .php-version         # pin for this project (per-directory; also honoured for subdirectories)
symfony php -v                  # what the project will run with
```

Selection order (as printed by `local:php:list`): `.php-version` in the current/parent directories,
then the `php.version` setting in `.symfony.local.yaml` (*unverified*), then the default `php` in
`$PATH`. `composer.json`'s `config.platform.php` does **not** switch the interpreter — it only
constrains Composer's dependency resolution.

## 7. Wrappers

| Wrapper | Behaviour | cwd-sensitive? |
|---|---|---|
| `symfony console <args>` | runs `bin/console` of the enclosing project | no — walks up to the root |
| `symfony composer <args>` | Composer with the project PHP, no memory limit | **yes** — `No composer.json in current directory`; use `--working-dir="$root"` |
| `symfony php <bin> <args>` | runs a PHP script/binary with the project PHP | **yes** — script path is relative to cwd; use an absolute path |
| `symfony run [-d] [--watch=…] <cmd>` | any command with the injected env | path of `<cmd>` resolved normally |

`symfony console` boots the kernel, so a fatal config error surfaces here first; `symfony console about`
is the cheapest end-to-end boot check.

## 8. Checks

```bash
symfony check:requirements                 # PHP version/extensions/ini for Symfony; --dir to target another root
symfony check:security                     # known CVEs in composer.lock; --format=json|markdown|junit, --no-dev, --local (offline cache)
```

`check:security` exits non-zero when advisories are found (`--disable-exit-code` to only report).
It downloads the advisory DB — on an air-gapped machine use `--local` after a one-time
`--update-cache`.

## 9. Everything else

`symfony list` also shows `cloud:*` / `upsun:*` (Platform.sh, Upsun — remote infra, explicit user
request only), `book:*` (the Fast Track book project), `lsp:*`, `self:*` (`self:update` upgrades
the CLI; `self:completion` installs shell completion). None of these are part of local
development work.
