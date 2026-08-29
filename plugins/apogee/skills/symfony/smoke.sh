#!/usr/bin/env bash
# Symfony project smoke check — proves the CLI wiring an agent depends on.
#
# Run from the project root. Reports, in order: the CLI is installed, this is a
# Symfony project, requirements pass, which env vars the CLI injects from running
# Docker services, and whether the app answers over HTTP.
#
# Exit 0 = the project is drivable. Any FAIL means stop and fix before working.
set -uo pipefail

pass() { printf '  \033[32mOK\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAILED=1; }
info() { printf '  ---  %s\n' "$1"; }
FAILED=0
STARTED_SERVER=0

echo "== toolchain =="
if command -v symfony >/dev/null 2>&1; then
  pass "$(symfony version --no-ansi 2>/dev/null | head -1)"
else
  fail "symfony CLI not installed — https://symfony.com/download"; exit 1
fi

echo "== project =="
if [ -f bin/console ] && [ -f composer.json ]; then
  pass "Symfony project root ($(pwd))"
else
  fail "no bin/console + composer.json here — cd to the project ROOT first"; exit 1
fi

symfony check:requirements >/dev/null 2>&1 \
  && pass "check:requirements" \
  || fail "check:requirements — run 'symfony check:requirements' for detail"

echo "== injected env (from running Docker services) =="
INJECTED=$(symfony var:export --multiline 2>/dev/null | grep -cE '^export (DATABASE|MAILER|REDIS|RABBITMQ)_' || true)
if [ "${INJECTED:-0}" -gt 0 ]; then
  pass "$INJECTED service var(s) injected — bare 'php bin/console' would NOT see these"
  symfony var:export --multiline 2>/dev/null | grep -E '^export (DATABASE|MAILER)_URL=' | sed 's/^/       /'
  # Prove the divergence on THIS project rather than asserting it: the port Docker
  # published is random per 'up', while .env still carries the recipe placeholder.
  LIVE=$(symfony var:export --multiline 2>/dev/null | sed -n 's/^export DATABASE_URL=//p')
  STALE=$(sed -n 's/^DATABASE_URL=//p' .env 2>/dev/null | tr -d '"')
  if [ -n "$LIVE" ] && [ -n "$STALE" ] && [ "$LIVE" != "$STALE" ]; then
    info "DATABASE_URL differs from .env — bare 'php bin/console' would use the stale one:"
    printf '       .env: %s\n' "$STALE"
  fi
else
  info "none — no Docker services up (fine if this project has no compose.yaml)"
fi

echo "== http =="
# NOTE: 'symfony server:status' exits 0 whether or not the server runs — the state
# is only in stdout, so parsing it is mandatory. Capture into a variable rather than
# piping to 'grep -q': under 'set -o pipefail' grep closes the pipe on first match,
# symfony dies of SIGPIPE (141), and the pipeline reports failure on a SUCCESSFUL match.
SERVER_STATUS=$(symfony server:status --no-ansi 2>&1 || true)
case "$SERVER_STATUS" in
  *"Not Running"*)
    if symfony server:start -d >/dev/null 2>&1; then
      STARTED_SERVER=1
    else
      fail "server:start failed — run 'symfony server:start' in the foreground for the reason"
    fi ;;
  *) info "server already running" ;;
esac
URL=$(symfony var:export 2>/dev/null | tr ' ' '\n' | sed -n 's/^SYMFONY_DEFAULT_ROUTE_URL=//p' | tr -d '"')
URL=${URL:-http://127.0.0.1:8000/}
CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$URL" 2>/dev/null)
CODE=${CODE:-000}
case "$CODE" in
  000) fail "no HTTP response from $URL" ;;
  5*)  fail "$URL -> $CODE (app error; run 'symfony server:log')" ;;
  *)   pass "$URL -> $CODE" ;;
esac
[ "$STARTED_SERVER" = 1 ] && { symfony server:stop >/dev/null 2>&1; info "stopped the server this script started"; }

echo
[ "$FAILED" = 0 ] && echo "SMOKE OK" || echo "SMOKE FAILED"
exit "$FAILED"
