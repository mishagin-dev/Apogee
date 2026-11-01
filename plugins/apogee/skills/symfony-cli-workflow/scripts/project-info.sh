#!/usr/bin/env bash
# Symfony project probe — read-only. Run from anywhere inside the project.
#
# Prints what an agent must know before running anything: CLI presence, project
# root, Symfony and PHP versions (required vs. actually used), a compatibility
# verdict, installed bundles/tools, Docker env injection, web-server state.
#
# Exit 0 = found a Symfony project (the verdict may still say MISMATCH).
# Exit 1 = not inside a Symfony project.   Exit 2 = fatal (no PHP at all).
set -uo pipefail

ok()   { printf '  \033[32mOK\033[0m    %s\n' "$1"; }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mBAD\033[0m   %s\n' "$1"; }
info() { printf '  ---   %s\n' "$1"; }

# --- CLI ---------------------------------------------------------------------
echo "== symfony cli =="
HAVE_CLI=0
if command -v symfony >/dev/null 2>&1; then
  HAVE_CLI=1; ok "$(symfony version --no-ansi 2>/dev/null | head -1)"
else
  warn "symfony CLI not installed — fall back to php/composer; see references/troubleshooting.md §1"
fi

# --- root --------------------------------------------------------------------
echo "== project =="
ROOT=$PWD
while [ "$ROOT" != / ] && [ ! -f "$ROOT/bin/console" ]; do ROOT=$(dirname "$ROOT"); done
if [ ! -f "$ROOT/bin/console" ] || [ ! -f "$ROOT/composer.json" ]; then
  bad "no bin/console + composer.json in $PWD or any parent — not a Symfony project"; exit 1
fi
ok "root: $ROOT"
[ "$ROOT" != "$PWD" ] && info "you are in a subdirectory: 'symfony console' works here; cd to the root for 'symfony composer' / 'symfony php'"

# --- symfony version ---------------------------------------------------------
echo "== symfony version =="
SF_LOCK=$(grep -A3 '"name": "symfony/framework-bundle"' "$ROOT/composer.lock" 2>/dev/null \
          | sed -n 's/.*"version": "v\{0,1\}\([^"]*\)".*/\1/p' | head -1)
SF_REQ=$(sed -n 's/.*"symfony\/framework-bundle": *"\([^"]*\)".*/\1/p' "$ROOT/composer.json" | head -1)
SF_FENCE=$(grep -A4 '"symfony": {' "$ROOT/composer.json" 2>/dev/null | sed -n 's/.*"require": *"\([^"]*\)".*/\1/p' | head -1)
[ -n "$SF_LOCK" ]  && ok "installed (composer.lock): $SF_LOCK"
[ -n "$SF_REQ" ]   && info "composer.json requires framework-bundle: $SF_REQ"
[ -n "$SF_FENCE" ] && info "extra.symfony.require (Flex fence): $SF_FENCE"
[ -z "$SF_LOCK$SF_REQ$SF_FENCE" ] && warn "could not read a Symfony version — run 'symfony console about'"
SF_MAJOR=$(printf '%s\n%s\n%s\n' "$SF_LOCK" "$SF_REQ" "$SF_FENCE" | grep -oE '^[0-9]+' | head -1)
SF_MINOR=$(printf '%s\n%s\n%s\n' "$SF_LOCK" "$SF_REQ" "$SF_FENCE" | grep -oE '^[0-9]+\.[0-9]+' | head -1)

# --- php ---------------------------------------------------------------------
echo "== php =="
PHP_REQ=$(sed -n 's/.*"php": *"\([^"]*\)".*/\1/p' "$ROOT/composer.json" | head -1)
[ -n "$PHP_REQ" ] && info "composer.json requires php: $PHP_REQ"
[ -f "$ROOT/.php-version" ] && info ".php-version pins: $(tr -d '[:space:]' < "$ROOT/.php-version")" \
                             || info "no .php-version — the CLI uses the default php in \$PATH"
if [ "$HAVE_CLI" = 1 ]; then
  PHP_USED=$(cd "$ROOT" && symfony php -r 'echo PHP_VERSION;' 2>/dev/null)
elif command -v php >/dev/null 2>&1; then
  PHP_USED=$(php -r 'echo PHP_VERSION;' 2>/dev/null)
fi
if [ -z "${PHP_USED:-}" ]; then bad "no usable PHP interpreter"; exit 2; fi
ok "php actually used: $PHP_USED"

# minimum PHP by Symfony major/minor
MIN_PHP=
case "${SF_MAJOR:-}" in
  8) MIN_PHP=8.4 ;;
  7) MIN_PHP=8.2 ;;
  6) MIN_PHP=8.1 ;;
  5) MIN_PHP=7.2 ;;
esac
if [ -n "$MIN_PHP" ]; then
  if [ "$(printf '%s\n%s\n' "$MIN_PHP" "$PHP_USED" | sort -V | head -1)" = "$MIN_PHP" ]; then
    ok "verdict: Symfony ${SF_MINOR:-$SF_MAJOR} needs PHP >= $MIN_PHP; using $PHP_USED — compatible"
  else
    bad "verdict: Symfony ${SF_MINOR:-$SF_MAJOR} needs PHP >= $MIN_PHP but $PHP_USED is used — MISMATCH; pin with .php-version (see references/troubleshooting.md §2)"
  fi
fi
case "${SF_MAJOR:-}" in
  8) info "conventions: Symfony 8.x (SKILL.md defaults apply)" ;;
  7) info "conventions: Symfony 7.x — see references/versions.md §4 (deprecated paths still present)" ;;
  6) info "conventions: Symfony 6.x — see references/versions.md §5 (no invokable commands, check ORM major)" ;;
esac

# --- bundles / tools ---------------------------------------------------------
echo "== installed packages (composer.lock) =="
has() { grep -q "\"name\": \"$1\"" "$ROOT/composer.lock" 2>/dev/null; }
row() { if has "$2"; then ok "$1"; else info "$1: not installed${3:+ — $3}"; fi; }
row "maker-bundle"          symfony/maker-bundle            "symfony composer require --dev maker"
row "doctrine/orm"          doctrine/orm                    "symfony composer require orm"
row "doctrine-migrations"   doctrine/doctrine-migrations-bundle
row "doctrine-fixtures"     doctrine/doctrine-fixtures-bundle "symfony composer require --dev orm-fixtures"
row "messenger"             symfony/messenger
row "twig-bundle"           symfony/twig-bundle
row "security-bundle"       symfony/security-bundle
row "asset-mapper"          symfony/asset-mapper
row "webpack-encore-bundle" symfony/webpack-encore-bundle
row "phpunit"               phpunit/phpunit                 "symfony composer require --dev test"
row "phpstan"               phpstan/phpstan
row "php-cs-fixer"          friendsofphp/php-cs-fixer
[ -f "$ROOT/bin/phpunit" ] && info "test entry point: bin/phpunit" || info "test entry point: vendor/bin/phpunit (no bin/phpunit)"

# --- docker / env ------------------------------------------------------------
echo "== docker env injection =="
COMPOSE=$(ls "$ROOT"/compose.yaml "$ROOT"/compose.yml "$ROOT"/docker-compose.yaml "$ROOT"/docker-compose.yml 2>/dev/null | head -1)
if [ -z "$COMPOSE" ]; then
  info "no compose file — nothing to inject; .env values are authoritative"
elif [ "$HAVE_CLI" = 1 ]; then
  INJECTED=$(cd "$ROOT" && symfony var:export --multiline 2>/dev/null | grep -cE '^export (DATABASE|MAILER|REDIS|RABBITMQ|MESSENGER|MONGODB)_' || true)
  if [ "${INJECTED:-0}" -gt 0 ]; then
    ok "$INJECTED service var(s) injected from running containers — bare 'php bin/console' would NOT see them"
    # Names only: injected DSNs carry credentials.
    (cd "$ROOT" && symfony var:export --multiline 2>/dev/null | sed -nE 's/^export ((DATABASE|MAILER|REDIS|RABBITMQ|MESSENGER|MONGODB)_[A-Z_]*)=.*/        \1/p')
  else
    warn "compose file present ($(basename "$COMPOSE")) but nothing injected — containers down? 'docker compose ps' / 'symfony var:export --debug'"
  fi
else
  warn "compose file present but no CLI — set DATABASE_URL etc. manually from 'docker compose port'"
fi

# --- server ------------------------------------------------------------------
echo "== local web server =="
if [ "$HAVE_CLI" = 1 ]; then
  STATUS=$(cd "$ROOT" && symfony server:status --no-ansi 2>&1 || true)
  case "$STATUS" in
    *"Not Running"*) info "not running — 'symfony server:start -d'" ;;
    *) ok "$(printf '%s\n' "$STATUS" | grep -m1 -E 'https?://' || echo running)" ;;
  esac
else
  info "no CLI — 'php -S 127.0.0.1:8000 -t public/' is the dev-only fallback"
fi
exit 0
