#!/usr/bin/env bash
# Validate a candidate commit message against the Conventional Commits rules
# enforced by this skill. Reads the message from a file argument or stdin.
#
# Usage:
#   printf '%s' "$msg" | bash scripts/check-message.sh
#   bash scripts/check-message.sh path/to/message.txt
#
# Exit code 0 and prints "OK" when the message is valid; non-zero with a list
# of specific violations otherwise. Warnings (subject > 50) do not fail.
set -uo pipefail

# Read the whole message.
if [ "$#" -ge 1 ] && [ -f "$1" ]; then
  msg=$(cat "$1")
else
  msg=$(cat)
fi

errors=0
err()  { echo "FAIL: $1"; errors=$((errors + 1)); }
warn() { echo "WARN: $1"; }

# Split into lines (preserve blank lines).
mapfile -t lines <<< "$msg"
subject="${lines[0]:-}"

allowed='feat|fix|docs|style|refactor|perf|test|chore|ci'

# --- Subject checks ---
if [ -z "$subject" ]; then
  err "subject line is empty"
else
  if ! printf '%s' "$subject" | grep -qE "^($allowed)(\([a-z0-9._/-]+\))?: .+"; then
    err "subject must match '<type>(<scope>): <Summary>' with type in: $allowed"
  else
    # Summary = text after the first ": "
    summary="${subject#*: }"
    first="${summary:0:1}"
    if [[ ! "$first" =~ [A-Z] ]]; then
      err "summary must start with a capital letter (got: '$first')"
    fi
    last="${subject: -1}"
    case "$last" in
      '.'|'!'|'?') err "subject must not end with punctuation (got: '$last')" ;;
    esac
  fi

  len=${#subject}
  if [ "$len" -gt 72 ]; then
    err "subject is $len chars; hard cap is 72"
  elif [ "$len" -gt 50 ]; then
    warn "subject is $len chars; target is <= 50 (max 72)"
  fi
fi

# --- Body checks ---
if [ "${#lines[@]}" -ge 2 ]; then
  if [ -n "${lines[1]}" ]; then
    err "line 2 must be blank (separate subject from body)"
  fi
  for i in "${!lines[@]}"; do
    [ "$i" -lt 2 ] && continue
    bl=${#lines[$i]}
    if [ "$bl" -gt 72 ]; then
      err "body line $((i + 1)) is $bl chars; wrap at 72"
    fi
  done
fi

# --- English-only: no non-ASCII bytes anywhere ---
# Portable across BSD/GNU grep: match any byte outside printable ASCII
# (space..tilde), allowing tab. In the C locale a multibyte UTF-8 char
# (e.g. Cyrillic) has high bytes that fall outside this range.
nonascii=$(printf '%s' "$msg" | LC_ALL=C grep -n "[^$(printf ' -~\t')]" || true)
if [ -n "$nonascii" ]; then
  err "message contains non-ASCII characters; commit messages must be English"
  printf '%s\n' "$nonascii" | sed 's/^/      offending line /'
fi

if [ "$errors" -eq 0 ]; then
  echo "OK"
  exit 0
fi
echo "---"
echo "$errors error(s) found."
exit 1
