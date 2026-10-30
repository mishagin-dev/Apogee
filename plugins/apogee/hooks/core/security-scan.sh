#!/bin/bash
# security-scan.sh — PreToolUse hook: refuse to send a live credential to an external service.
#
# Wired on three surfaces (hooks.json): every `mcp__*` tool, WebFetch/WebSearch, and Bash -- where
# it only looks at `agy` invocations, because that is the one shell command this toolkit uses to
# hand code to an external model (the second-opinion skill puts diffs inside the prompt). Any
# other Bash command is skipped untouched.
#
# This is the one gate ADR 0005 kept on irreversibility grounds: a secret that reaches a third-party
# service cannot be unsent, and no amount of `git reset` fixes it. Everything else the enforcement
# layer used to block was recoverable and is now prose.
#
# How it decides:
#   * The WHOLE tool_input is scanned, not enumerated per-server fields. Field enumeration is what
#     rotted the previous version -- it looked for `.code_context` / `.problem_description` /
#     `.attached_files[]`, the schema of a gemini MCP server that has not been configured for
#     months, so it had been passing everything through unexamined. `jq -r '..|strings'` walks any
#     shape, current or future.
#   * Value-per-line, byte-capped. A minified bundle pasted into a payload is one enormous line;
#     grep on that spikes CPU. jq emits each string value separately and MAX_BYTES truncates the
#     total, so both the line length and the total work stay bounded.
#   * High-confidence patterns ONLY (see config/sensitive-patterns.json) plus a placeholder filter
#     applied to the matched token. Precision over recall, deliberately.
#   * DENY, not ask: with a vendor-prefixed match a false positive is unlikely and redact-and-retry
#     is cheap.
#
# Fail-open on every error (no jq, unreadable config, malformed stdin): a broken scanner must not
# wedge the session.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATTERNS_FILE="${SCRIPT_DIR}/config/sensitive-patterns.json"
MAX_BYTES=262144  # 256 KB of string values is far more than any legitimate MCP prompt

# Scan `$1` (newline-separated string values). Echoes "<redacted-token>" and returns 0 on a hit,
# returns 1 otherwise. Used by both main() and --test.
scan_values() {
    local values="$1"
    local combined suppress match

    combined=$(jq -r '[.patterns[] | "(" + . + ")"] | join("|")' "$PATTERNS_FILE" 2>/dev/null) || return 1
    [[ -z "${combined}" || "${combined}" == "null" ]] && return 1
    suppress=$(jq -r '.placeholder_suppression // empty' "$PATTERNS_FILE" 2>/dev/null)

    while IFS= read -r match; do
        [[ -z "${match}" ]] && continue
        # A match that is documentation boilerplate (AKIAIOSFODNN7EXAMPLE, :password@, <token>)
        # is not a leak. Checked per match, so a real secret elsewhere in the same payload still
        # trips the gate.
        if [[ -n "${suppress}" ]] && printf '%s' "${match}" | grep -qE "${suppress}"; then
            continue
        fi
        # Report the first 6 characters only -- enough to identify which credential, not enough to
        # reprint it into the transcript.
        printf '%s...' "${match:0:6}"
        return 0
    done < <(printf '%s' "${values}" | grep -oE "${combined}" 2>/dev/null)

    return 1
}

# True if a Bash command string invokes `agy` as a command (at the start or after a shell chain
# operator, optionally preceded by VAR=value assignments). `echo agy` or a path containing "agy"
# does not count.
is_agy_command() {
    printf '%s' "$1" | grep -qE '(^|&&|\|\||;|\|)[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*agy([[:space:]]|$)'
}

main() {
    command -v jq >/dev/null 2>&1 || exit 0

    local input values hit tool_name command
    input=$(cat)
    tool_name=$(printf '%s' "${input}" | jq -r '.tool_name // ""' 2>/dev/null)
    if [[ "${tool_name}" == "Bash" ]]; then
        command=$(printf '%s' "${input}" | jq -r '.tool_input.command // ""' 2>/dev/null)
        is_agy_command "${command}" || exit 0
    fi

    values=$(printf '%s' "${input}" | jq -r '.tool_input | .. | strings' 2>/dev/null | head -c "${MAX_BYTES}")
    [[ -z "${values}" ]] && exit 0

    if hit=$(scan_values "${values}"); then
        jq -n --arg h "${hit}" '{
            hookSpecificOutput: {
                hookEventName: "PreToolUse",
                permissionDecision: "deny",
                permissionDecisionReason: ("Refusing to send this to an external service (MCP server, agy, web fetch): the payload contains what looks like a live credential (\($h)). Replace it with a placeholder (YOUR_API_KEY, <token>, ${SECRET}) and retry. If this is a false positive, the pattern list is in hooks/core/config/sensitive-patterns.json.")
            }
        }'
    fi
    exit 0
}

run_self_test() {
    local ok=0

    check() {  # check <label> <values> <want: HIT|QUIET>
        local label="$1" values="$2" want="$3" got
        if got=$(scan_values "$values"); then got="HIT"; else got="QUIET"; fi
        if [[ "$got" == "$want" ]]; then
            printf '  ok    %-46s %s\n' "$label" "$got"
        else
            printf '  FAIL  %-46s %s (want %s)\n' "$label" "$got" "$want"
            ok=1
        fi
    }

    echo "Must FIRE (real credentials):"
    check "anthropic key"        "sk-ant-api03-$(printf 'a%.0s' {1..95})" HIT
    check "aws access key id"    "AKIA1234567890ABCDEF"                   HIT
    check "github classic pat"   "ghp_$(printf 'b%.0s' {1..36})"          HIT
    check "google api key"       "AIza$(printf 'c%.0s' {1..35})"          HIT
    check "stripe live key"      "sk_live_$(printf 'd%.0s' {1..24})"      HIT
    check "PEM private key"      "-----BEGIN RSA PRIVATE KEY-----"        HIT
    check "postgres with creds"  "postgres://svc:Tr0ub4dor@db.prod:5432"  HIT
    check "secret among noise"   "$(printf 'harmless line\nAKIA1234567890ABCDEF\nmore text')" HIT

    echo
    echo "Must stay QUIET (the false positives that killed the old scanner):"
    check "python type hint"     "password: str"                                     QUIET
    check "env lookup"           'API_KEY=os.environ["API_KEY"]'                     QUIET
    check "ts interface field"   "client_secret: string;"                            QUIET
    check "dotenv example"       "DATABASE_URL=<your_database_url>"                  QUIET
    check "plain base64 blob"    "aGVsbG8gd29ybGQgdGhpcyBpcyBub3QgYSBjcmVkZW50aWFs" QUIET
    check "aws doc example key"  "AKIAIOSFODNN7EXAMPLE"                              QUIET
    check "docs conn string"     "postgres://user:password@localhost:5432/mydb"      QUIET
    check "placeholder token"    "Authorization: Bearer <token>"                     QUIET
    check "shell var conn"       'redis://admin:${REDIS_PASSWORD}@cache:6379'        QUIET
    check "empty input"          ""                                                  QUIET

    echo
    echo "Bash surface: only agy invocations are inspected"
    agy_check() {  # agy_check <label> <command> <want: AGY|SKIP>
        local label="$1" cmd="$2" want="$3" got
        if is_agy_command "$cmd"; then got="AGY"; else got="SKIP"; fi
        if [[ "$got" == "$want" ]]; then
            printf '  ok    %-46s %s\n' "$label" "$got"
        else
            printf '  FAIL  %-46s %s (want %s)\n' "$label" "$got" "$want"
            ok=1
        fi
    }
    agy_check "bare agy"             "agy -p 'review this'"                     AGY
    agy_check "agy after cd &&"      "cd sub && agy --model x -p 'q'"           AGY
    agy_check "env prefix then agy"  "FOO=1 agy -p 'q'"                         AGY
    agy_check "agy as last of pipe"  "cat diff.txt | agy -p 'q'"                AGY
    agy_check "git commit"           "git commit -F /tmp/msg"                   SKIP
    agy_check "echo mentioning agy"  "echo agy is great"                        SKIP
    agy_check "path containing agy"  "cat docs/agy-notes.md"                    SKIP
    agy_check "empty command"        ""                                         SKIP

    echo
    if [[ $ok -eq 0 ]]; then echo "All tests passed."; else echo "SOME TESTS FAILED."; fi
    exit $ok
}

if [[ "${1:-}" == "--test" ]]; then
    run_self_test
else
    main
fi
