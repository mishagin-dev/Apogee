# Everyday tasks through `symfony console` and `symfony composer`

All commands assume the project root for `composer`; `console` works from anywhere. Append
`--help` to any console command to see the flags of the *installed* version; this file names only
flags that are stable across 6.4 → 8.1 unless marked.

## Contents

1. Installing packs and bundles (Flex)
2. MakerBundle generators
3. Doctrine: database, migrations, schema, fixtures
4. Configuration, environments, secrets
5. Diagnostics (`debug:*`) and linters (`lint:*`)
6. Cache
7. Assets: AssetMapper (default) vs Webpack Encore
8. Messenger
9. Dependency maintenance and upgrades
10. Tests and static analysis

---

## 1. Installing packs and bundles

Flex aliases save typing and pull the recipe that wires config, `.env` lines and `bundles.php`:

```bash
symfony composer require --dev maker          # symfony/maker-bundle
symfony composer require orm                  # doctrine ORM + migrations (symfony/orm-pack)
symfony composer require --dev orm-fixtures   # doctrine/doctrine-fixtures-bundle
symfony composer require security twig form validator serializer mailer messenger
symfony composer require asset-mapper         # or: encore
symfony composer require --dev test profiler debug   # PHPUnit stack, web profiler, debug toolbar
symfony composer require --dev phpstan/phpstan friendsofphp/php-cs-fixer
```

After a `require`, Flex prints what the recipe changed; check `git status` and
`symfony console debug:config <bundle>`. Recipe mechanics (`recipes`, `recipes:install --force`,
conflicts) are in §9 and in `troubleshooting.md`.

Before using any `make:*`, confirm the bundle: `symfony console list make` — empty output means
install `maker` first.

## 2. MakerBundle generators

Interactivity rules are in SKILL.md §5 (argument + `< /dev/null` for single-prompt makers; piped
answers for loops; never `--no-interaction`). The generators and what to verify afterwards:

| Generator | Produces | Verify |
|---|---|---|
| `make:controller NameController` | controller + Twig template (`templates/name/index.html.twig`) | `debug:router` |
| `make:entity Name --field=name:string:255 --field=price:integer [--relation=author:ManyToOne:User]` (1.68+; older: prompt loop) | entity + repository; re-run on an existing entity to add fields; `?` suffix = nullable | `doctrine:schema:validate` → mapping OK, DB not in sync |
| `make:migration` (no prompts; `-n` fine) | `migrations/VersionYYYY….php` diff against the current DB | read the file, then `doctrine:migrations:migrate -n` |
| `make:form NameType [Entity]` | form type class | `debug:form` (lists types) |
| `make:crud Entity` | controller + form + templates + optional tests | `debug:router`, open the list page |
| `make:user` | `User` entity/repository, `security.yaml` provider, password hasher | `doctrine:schema:validate`, `debug:config security` |
| `make:security:form-login` | login controller, template, `security.yaml` form_login | `debug:router app_login`, `debug:firewall` |
| `make:command app:name --argument=format:string --option=since:string` (1.68+; without the options it prompts in a loop and `< /dev/null` aborts) | invokable command (`__invoke` + `#[Argument]`/`#[Option]`) on 7.3+/8.x; classic `execute()` on 6.4 | `cache:clear` if `--help` says the namespace is unknown, then `symfony console app:name --help` |
| `make:subscriber Name` / `make:listener Name` | event subscriber / `#[AsEventListener]` class | `debug:event-dispatcher <event>` |
| `make:message Name` + `make:messenger-middleware` | message + handler | `debug:messenger` |
| `make:test` (prompts: type, class name) | `TestCase`/`KernelTestCase`/`WebTestCase`/`ApiTestCase`/`PantherTestCase` | `symfony php bin/phpunit tests/…` |
| `make:registration-form`, `make:reset-password`, `make:voter`, `make:validator`, `make:twig-component`, `make:stimulus-controller`, `make:schedule`, `make:webhook` | as named | matching `debug:*` |

Generated code follows the installed MakerBundle's idea of "current" Symfony — on a 6.4 project it
will not emit 7.3+ invokable commands. Always open what it wrote before building on it.

Invokable-command types worth knowing (7.3+/8.x, verified on 8.1): a `#[Argument]` typed as a
backed enum (`enum ReportFormat: string { case Csv = 'csv'; … }`) is validated by Console itself
(`The value "xml" is not valid for the "format" argument. Supported values are "csv", "json"`) and
its cases feed shell completion; a `?\DateTimeImmutable` option is parsed by the built-in date
resolver (`--since='-7 days'` works). Prefer these over hand-written `in_array`/`new DateTime` checks.

Messenger's Doctrine transport ships with `MESSENGER_TRANSPORT_DSN=doctrine://default?auto_setup=0`
in `--webapp` projects, so `messenger_messages` does **not** create itself: the first `make:migration`
on an empty DB includes it (fine — keep it), or run `messenger:setup-transports` once. A consumer
started before the table exists dies with `no such table: messenger_messages` and, under a
`watch` worker, restarts in a loop.

## 3. Doctrine

```bash
symfony console doctrine:database:create --if-not-exists
symfony console doctrine:database:create --if-not-exists --env=test     # test DB (name gets the _test suffix from doctrine.yaml when@test)
symfony console make:migration                                          # diff → migrations/Version*.php; review it
symfony console doctrine:migrations:migrate --no-interaction            # dev; add --env=test for the test DB
symfony console doctrine:migrations:status                              # executed / pending / new
symfony console doctrine:migrations:list
symfony console doctrine:migrations:diff                                # same as make:migration without the Maker wrapper
symfony console doctrine:schema:validate                                # mapping + sync; the canonical "is Doctrine happy" check
symfony console doctrine:schema:update --dump-sql                       # preview only; --force bypasses migrations → ask first (SKILL.md §7)
symfony console doctrine:query:sql 'SELECT count(*) FROM product'
symfony console doctrine:mapping:info
symfony console doctrine:fixtures:load --append                         # keep data; without --append it PURGES all tables → ask first
symfony console doctrine:fixtures:load --group=dev --append
```

Migrations workflow: change entities → `make:migration` → read the generated `up()`/`down()` →
`migrate -n` → `schema:validate`. Never hand-edit the schema in the DB. If `make:migration` says
"No changes detected" but you expect some, check the entity is under a mapped directory
(`debug:config doctrine orm.mappings`) and that the cache is not stale (`cache:clear`).

Fixtures live in `src/DataFixtures/*Fixture.php` (`Fixture` base class, `load(ObjectManager $m)`),
groups via `FixtureGroupInterface`, ordering via `DependentFixtureInterface`. In tests use
`--env=test` and consider a fresh DB per run (`doctrine:database:drop --force --env=test` is
destructive → confirm; the *test* DB is the one case where users usually say yes).

## 4. Configuration, environments, secrets

File precedence (later wins): `.env` (committed defaults) < `.env.local` (machine secrets, git-ignored)
< `.env.$APP_ENV` (committed per-env) < `.env.$APP_ENV.local` (git-ignored). `.env.local` is **not**
loaded when `APP_ENV=test`, so test overrides go to `.env.test` / `.env.test.local`. Values injected
by the Symfony CLI (Docker, server URL) override all files because they are real process env vars.

```bash
symfony console debug:dotenv                 # which files were loaded, which defines each var, final value
symfony console debug:dotenv DATABASE_URL
symfony console debug:container --env-vars   # resolved %env()% usage in the container
```

Secrets (encrypted vault, per environment; dev keys may be committed, prod private key never):

```bash
symfony console secrets:generate-keys                 # dev vault (config/secrets/dev)
symfony console secrets:generate-keys --env=prod      # prod vault; keep config/secrets/prod/*.decrypt.private.php OUT of git
symfony console secrets:set DATABASE_PASSWORD         # prompts for the value (hidden); --random generates one
symfony console secrets:set DATABASE_PASSWORD --env=prod
symfony console secrets:list                          # names only; --reveal shows values → never in logs/chat
symfony console secrets:remove NAME
symfony console secrets:decrypt-to-local / secrets:encrypt-from-local
```

Reference a secret like an env var: `%env(DATABASE_PASSWORD)%`. A real env var with the same name
wins over the vault. Prod secrets need the private key present at runtime (deploy concern — out of
scope here; just say so).

## 5. Diagnostics and linters

```bash
symfony console debug:router [name] [--show-controllers]
symfony console debug:container [id|--tag=…|--parameters|--env-vars|--deprecations]
symfony console debug:autowiring [search]            # what you can type-hint
symfony console debug:config <bundle> [path]         # effective config; config:dump-reference <bundle> for the schema
symfony console debug:event-dispatcher [event]
symfony console debug:twig                           # functions, filters, tests, globals, namespaces
symfony console debug:firewall [name]                # security listeners per firewall
symfony console debug:messenger                      # handlers per message
symfony console debug:validator <Class>
symfony console debug:serializer <Class>
symfony console debug:form [Type]
symfony console debug:translation <locale>
symfony console debug:asset-map                      # AssetMapper paths and mapped assets
symfony console debug:scheduler                      # 6.3+

symfony console lint:container                       # service wiring / type errors without a request
symfony console lint:yaml config/ --parse-tags
symfony console lint:twig templates/
symfony console lint:xliff translations/
symfony console lint:translations                    # 7.2+ (unverified flag set; run --help)
```

Pattern: after any change, run the one linter that covers it (table in SKILL.md §4). `lint:container`
plus `cache:warmup` together catch most "works on my machine, breaks in prod" wiring errors.

## 6. Cache

```bash
symfony console cache:clear                          # dev; --env=prod for the prod cache dir
symfony console cache:warmup
symfony console cache:pool:list
symfony console cache:pool:clear cache.app           # application cache only (cache.system for Symfony's own)
```

`cache:clear` already warms up; `--no-warmup` to skip. Permission errors in `var/cache` →
`troubleshooting.md`. Doctrine metadata/query caches live inside the system cache; a stale mapping
after renaming a field is a `cache:clear` problem, not a Doctrine one.

## 7. Assets

**AssetMapper** is the default in `--webapp` since 6.3/6.4 and the only default in 7.x/8.x: no Node,
importmap + native ES modules, Stimulus/Turbo from jsdelivr.

```bash
symfony console importmap:require bootstrap @hotwired/stimulus   # add packages (downloads to assets/vendor)
symfony console importmap:remove bootstrap
symfony console importmap:update [package]
symfony console importmap:outdated
symfony console importmap:audit                                  # vulnerable JS deps
symfony console importmap:install                                # (re)download assets/vendor after clone
symfony console asset-map:compile                                # prod build → public/assets; dev serves on the fly
symfony console debug:asset-map
```

`assets/vendor/` is git-ignored; a fresh clone needs `importmap:install`. The dev server serves
assets dynamically — never commit `public/assets/`.

**Webpack Encore** (`symfony composer require encore`, then `npm install`) is the right call when the
project already uses it, needs a bundler (TypeScript, Sass with heavy tooling, React/Vue SFCs, legacy
browser targets), or the team insists on npm. Run its watcher as a worker (`cli-commands.md` §4):
`symfony run -d npm run watch`; build with `npm run build`. Do not mix both systems in one project
without a reason.

## 8. Messenger

```bash
symfony console messenger:consume async -vv --time-limit=3600 --memory-limit=256M
symfony console messenger:stats                     # queued per transport
symfony console messenger:failed:show [id]
symfony console messenger:failed:retry [id] --force
symfony console messenger:failed:remove <id>
symfony console messenger:setup-transports          # create tables/queues (idempotent)
symfony console debug:messenger
```

Transports come from `MESSENGER_TRANSPORT_DSN` — injected by the CLI when a RabbitMQ/Redis
container runs, otherwise the Doctrine transport in `.env`. Long-running consumers belong in a
`.symfony.local.yaml` worker so they restart with the code (`cli-commands.md` §4).

## 9. Dependency maintenance and upgrades

```bash
symfony composer outdated "symfony/*"               # what is behind
symfony composer update "symfony/*" --with-all-dependencies    # within extra.symfony.require — safe minor/patch bumps
symfony composer recipes                            # recipe status per package
symfony composer recipes:update                     # apply upstream recipe changes (interactive diff, Flex ≥ 1.18)
symfony composer recipes:install <pkg> --force -v   # reset a recipe to upstream (overwrites your edits → ask first)
symfony check:security                              # CVE scan of composer.lock
```

`extra.symfony.require` in `composer.json` (e.g. `"8.1.*"`) is the version fence; Flex refuses to
install `symfony/*` outside it. Do not widen it casually.

**Major upgrade (e.g. 7.4 → 8.x)** only on explicit request. The path is fixed by how Symfony is
versioned (8.0 = 7.4 with every deprecated path removed):

1. Be on 7.4 with the latest patch: `symfony composer update "symfony/*"`.
2. Drive deprecations to zero — `symfony console debug:container --deprecations`, the profiler's
   Logs → Deprecations panel, PHPUnit's deprecation report
   (`SYMFONY_DEPRECATIONS_HELPER=max[self]=0 symfony php bin/phpunit`).
3. Check PHP ≥ 8.4 (`symfony local:php:list`, `.php-version`), bump `require.php`.
4. Read `UPGRADE-8.0.md` (and `UPGRADE-8.1.md`) from `vendor/symfony/symfony` or GitHub for the
   removed APIs; third-party bundles must have 8.x-compatible releases (`symfony composer why-not symfony/framework-bundle 8.1`).
5. Set `extra.symfony.require` to `"8.1.*"`, `symfony composer update "symfony/*" --with-all-dependencies`,
   then `symfony composer recipes:update`, `lint:container`, `cache:warmup`, full test suite.

Details and the removed-API list: `versions.md`.

## 10. Tests and static analysis

```bash
symfony console doctrine:database:create --if-not-exists --env=test
symfony console doctrine:migrations:migrate -n --env=test        # or doctrine:schema:create --env=test for a throwaway DB
symfony php bin/phpunit                                          # phpunit-bridge entry point; use vendor/bin/phpunit if bin/phpunit is absent
symfony php bin/phpunit tests/Controller --filter=HomeController
symfony php bin/phpunit --testdox
symfony php vendor/bin/phpstan analyse                           # config in phpstan.neon / phpstan.dist.neon
symfony php vendor/bin/php-cs-fixer fix --dry-run --diff         # drop --dry-run to apply
```

Why `symfony php` and not `php`: tests read `DATABASE_URL` too, and the injected value points at the
live Docker port. The `_test` suffix comes from `config/packages/doctrine.yaml`
(`when@test: dbname_suffix: '_test%env(default::TEST_TOKEN)%'`), so the test DB is created from the
same URL automatically. `.env.test` sets `APP_ENV=test`; `KERNEL_CLASS` lives there too.

Static analysis is not installed by default — offer it, do not assume it. Prefer the project's
existing config (`phpstan.neon`, `.php-cs-fixer.dist.php`) over inventing new rule sets.
