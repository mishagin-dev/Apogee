#!/usr/bin/env bash
#
# validate.sh — repo health check for Apogee.
#
# Checks:
#   1. Python syntax  — py_compile every *.py under plugins/
#   2. Shell syntax   — bash -n every *.sh in the repo (excluding .git)
#   3. JSON validity  — jq empty every *.json in the repo (excluding .git)
#   4. Hook paths     — every ${CLAUDE_PLUGIN_ROOT}/<path> in hooks.json must
#                       resolve to an existing file under plugins/apogee/
#   5. Self-tests     — hook --test modes (enforce-git-flow-skill)
#   6. Version lockstep — plugin.json version == marketplace.json plugins[0].version
#                       == CHANGELOG.md's top-most ## [x.y.z] header
#   7. Language policy — no unallowlisted Cyrillic in plugins/apogee/**, scripts/**,
#                       setup.sh, sync.sh, install.sh, root CLAUDE.md (see
#                       scripts/lang-check-allowlist.txt for known exceptions)
#   8. Plugin validator — `claude plugin validate --strict` (skipped without the CLI)
#   9. Backstop smoke  — tests/smoke-run-plan.sh against real br + git-flow sandboxes
#                       (skipped without the binaries)
#
# Exits 0 if all stages pass, 1 on any failure.
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_JSON="${REPO_ROOT}/plugins/apogee/hooks/hooks.json"
PLUGIN_ROOT="${REPO_ROOT}/plugins/apogee"
PLUGIN_JSON="${REPO_ROOT}/plugins/apogee/.claude-plugin/plugin.json"
MARKETPLACE_JSON="${REPO_ROOT}/.claude-plugin/marketplace.json"
CHANGELOG="${REPO_ROOT}/CHANGELOG.md"

fail=0

# ---------------------------------------------------------------------------
# Stage 1: Python syntax
# ---------------------------------------------------------------------------
echo "=== Stage 1: Python syntax ==="
while IFS= read -r -d '' f; do
    if ! python3 -m py_compile "$f" 2>/dev/null; then
        echo "FAIL py $f"
        fail=1
    fi
done < <(find "${REPO_ROOT}/plugins" -name "*.py" -print0)
echo "Stage 1 done."

# ---------------------------------------------------------------------------
# Stage 2: Shell syntax
# ---------------------------------------------------------------------------
echo "=== Stage 2: Shell syntax ==="
while IFS= read -r -d '' f; do
    if ! bash -n "$f" 2>/dev/null; then
        echo "FAIL sh $f"
        fail=1
    fi
done < <(find "${REPO_ROOT}" -path "${REPO_ROOT}/.git" -prune -o -name "*.sh" -print0)
echo "Stage 2 done."

# ---------------------------------------------------------------------------
# Stage 3: JSON validity
# ---------------------------------------------------------------------------
echo "=== Stage 3: JSON validity ==="
while IFS= read -r -d '' f; do
    if ! jq empty "$f" 2>/dev/null; then
        echo "FAIL json $f"
        fail=1
    fi
done < <(find "${REPO_ROOT}" -path "${REPO_ROOT}/.git" -prune -o -name "*.json" -print0)
echo "Stage 3 done."

# ---------------------------------------------------------------------------
# Stage 4: Hook path resolution
# ---------------------------------------------------------------------------
echo "=== Stage 4: Hook path resolution ==="
stage4_out="$(python3 - "${HOOKS_JSON}" "${PLUGIN_ROOT}" <<'PYEOF'
import re, sys, os, json

hooks_json = sys.argv[1]
plugin_root = sys.argv[2]

with open(hooks_json) as f:
    data = json.load(f)

def walk_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk_strings(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_strings(item)
    elif isinstance(obj, str):
        yield obj

paths = set()
for s in walk_strings(data):
    for rel in re.findall(r'\$\{CLAUDE_PLUGIN_ROOT\}/([^\s"]+)', s):
        paths.add(rel)

missing = []
for rel in paths:
    full = os.path.join(plugin_root, rel)
    if not os.path.isfile(full):
        missing.append(rel)

# A hook matcher is a regex matched against the WHOLE tool name, so a bare prefix silently matches
# nothing. `"mcp__"` shipped from the first plugin commit and never once fired -- it cannot equal
# `mcp__context7__resolve-library-id`. The working form is `mcp__.*`. Only an `mcp__` matcher can
# hit this (native tool names like `Bash` ARE the whole name), so the rule is scoped to those.
bad_matchers = []
for event, groups in data.get("hooks", {}).items():
    for group in groups:
        m = group.get("matcher")
        if not m:
            continue
        # A matcher may be an alternation (`mcp__.*|WebFetch`); judge each `mcp__` branch on its own.
        for alt in m.split("|"):
            if alt.startswith("mcp__") and not alt.endswith("*"):
                bad_matchers.append(f"{event}: {alt!r} in {m!r} matches nothing -- did you mean {alt + '.*'!r}?")

for problem in bad_matchers:
    print(f"FAIL matcher {problem}")
for p in sorted(missing):
    print(f"FAIL path {p}")
if missing or bad_matchers:
    sys.exit(1)
print(f"All {len(paths)} hook paths resolved OK; matchers OK.")
PYEOF
)"
stage4_rc=$?
echo "${stage4_out}"
if [ "${stage4_rc}" -ne 0 ]; then
    fail=1
fi
echo "Stage 4 done."

# ---------------------------------------------------------------------------
# Stage 5: self-tests (lib __main__ assertions + hook --test modes)
# ---------------------------------------------------------------------------
echo "=== Stage 5: self-tests ==="
# The two surviving blocking hooks both expose a --test mode (their __main__ otherwise runs the
# live hook on stdin). Entries are "<interpreter> <path>".
# NOTE: no bare-`python3 <lib>` self-test array here. There used to be one for the shared libs, but
# both were deleted with the gates they served (ADR 0005). Do not reintroduce an EMPTY array and
# loop over it: this script runs `set -uo pipefail` and macOS ships Bash 3.2, where "${EMPTY[@]}"
# aborts on an unbound variable -- CI (Bash 5) would pass while every local run failed.
HOOK_SELFTESTS=(
    "python3 ${REPO_ROOT}/plugins/apogee/hooks/git/enforce-git-flow-skill.py"
    "bash ${REPO_ROOT}/plugins/apogee/hooks/core/security-scan.sh"
    "python3 ${REPO_ROOT}/plugins/apogee/hooks/core/apogee-session-start.py"
)
for entry in "${HOOK_SELFTESTS[@]}"; do
    if ${entry} --test > /dev/null 2>&1; then
        echo "ok  ${entry##* } --test"
    else
        echo "FAIL selftest ${entry##* } --test"
        fail=1
    fi
done
echo "Stage 5 done."

# ---------------------------------------------------------------------------
# Stage 6: version lockstep (plugin.json <-> marketplace.json <-> CHANGELOG.md)
# ---------------------------------------------------------------------------
echo "=== Stage 6: version lockstep ==="
# Every marketplace entry must agree with its plugin.json; the `apogee` entry must also match the
# CHANGELOG's top header.
plugin_version="$(jq -r '.version' "${PLUGIN_JSON}" 2>/dev/null)"
marketplace_version="$(jq -r '.plugins[] | select(.name == "apogee") | .version' "${MARKETPLACE_JSON}" 2>/dev/null)"
changelog_version="$(grep -m1 -oE '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' "${CHANGELOG}" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"

if [ -z "${plugin_version}" ] || [ "${plugin_version}" = "null" ]; then
    echo "FAIL version: could not read .version from ${PLUGIN_JSON}"
    fail=1
elif [ -z "${marketplace_version}" ] || [ "${marketplace_version}" = "null" ]; then
    echo "FAIL version: could not read the apogee entry's version from ${MARKETPLACE_JSON}"
    fail=1
elif [ -z "${changelog_version}" ]; then
    echo "FAIL version: could not find a '## [x.y.z]' header in ${CHANGELOG}"
    fail=1
elif [ "${plugin_version}" != "${marketplace_version}" ]; then
    echo "FAIL version: plugin.json (${plugin_version}) != marketplace.json (${marketplace_version})"
    fail=1
elif [ "${plugin_version}" != "${changelog_version}" ]; then
    echo "FAIL version: plugin.json (${plugin_version}) != CHANGELOG.md top entry (${changelog_version})"
    fail=1
else
    echo "ok  apogee: plugin.json, marketplace.json and CHANGELOG at ${plugin_version}"
fi
while IFS=$'\t' read -r name source entry_version; do
    [ "${name}" = "apogee" ] && continue
    pj="${REPO_ROOT}/${source#./}/.claude-plugin/plugin.json"
    pv="$(jq -r '.version' "${pj}" 2>/dev/null)"
    if [ "${pv}" != "${entry_version}" ]; then
        echo "FAIL version: ${name}: plugin.json (${pv}) != marketplace.json (${entry_version})"
        fail=1
    else
        echo "ok  ${name}: plugin.json and marketplace.json at ${pv}"
    fi
done < <(jq -r '.plugins[] | [.name, .source, .version] | @tsv' "${MARKETPLACE_JSON}" 2>/dev/null)
echo "Stage 6 done."

# ---------------------------------------------------------------------------
# Stage 7: language policy (English-only in code/config; docs/apogee/ is never
#          scanned since it's not in the scan list). Implemented in Python on
#          purpose: a `grep -E '[а-я]'` is locale-dependent -- with LANG unset,
#          BSD grep treats the range bytewise and matched every em-dash (614
#          false FAILs on a clean tree), while CI's C.UTF-8 passed.
# ---------------------------------------------------------------------------
echo "=== Stage 7: language policy ==="
LANG_ALLOWLIST="${REPO_ROOT}/scripts/lang-check-allowlist.txt"
stage7_out="$(python3 - "${REPO_ROOT}" "${LANG_ALLOWLIST}" <<'PYEOF'
import os, re, sys

root, allowlist_path = sys.argv[1], sys.argv[2]
scan = ["plugins", "scripts", "setup.sh", "sync.sh", "install.sh", "CLAUDE.md"]
cyrillic = re.compile("[а-яА-ЯёЁ]")

allow = set()
if os.path.isfile(allowlist_path):
    with open(allowlist_path, encoding="utf-8") as f:
        allow = {line.rstrip("\n") for line in f if line.strip() and not line.startswith("#")}

def candidates():
    for entry in scan:
        path = os.path.join(root, entry)
        if os.path.isfile(path):
            yield path
            continue
        for d, _, names in os.walk(path):
            for n in names:
                yield os.path.join(d, n)

hits = 0
for path in candidates():
    if os.path.abspath(path) == os.path.abspath(allowlist_path):
        continue
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, OSError):
        continue  # binary or unreadable: not a text file we police
    rel = os.path.relpath(path, root)
    for n, line in enumerate(lines, 1):
        if cyrillic.search(line):
            # Allowlist entries are `path:exact line text` -- no line number, so an unrelated
            # edit above the line doesn't invalidate the entry.
            key = f"{rel}:{line.rstrip(chr(10))}"
            if key in allow:
                continue
            print(f"FAIL lang {rel}:{n}:{line.rstrip(chr(10))}")
            hits += 1
sys.exit(1 if hits else 0)
PYEOF
)"
stage7_rc=$?
[ -n "${stage7_out}" ] && echo "${stage7_out}"
if [ "${stage7_rc}" -ne 0 ]; then
    fail=1
else
    echo "ok  no unallowlisted Cyrillic found"
fi
echo "Stage 7 done."

# ---------------------------------------------------------------------------
# Stage 8: official plugin validator (manifest, frontmatter, hook schema).
#          Skipped where the claude CLI is absent (CI), so it never blocks there.
# ---------------------------------------------------------------------------
echo "=== Stage 8: claude plugin validate --strict ==="
if command -v claude >/dev/null 2>&1; then
    for plugin_dir in "${REPO_ROOT}"/plugins/*/; do
        if claude plugin validate --strict "${plugin_dir}" >/dev/null 2>&1; then
            echo "ok  claude plugin validate --strict ${plugin_dir#"${REPO_ROOT}"/}"
        else
            echo "FAIL claude plugin validate --strict ${plugin_dir#"${REPO_ROOT}"/} (run it directly for details)"
            fail=1
        fi
    done
else
    echo "skip  claude CLI not installed"
fi
echo "Stage 8 done."

# ---------------------------------------------------------------------------
# Stage 9: hook integration smoke against real br + git-flow sandboxes.
#          Skipped when either binary is missing (CI).
# ---------------------------------------------------------------------------
echo "=== Stage 9: run-plan backstop smoke ==="
if command -v br >/dev/null 2>&1 && command -v git-flow >/dev/null 2>&1; then
    if bash "${REPO_ROOT}/tests/smoke-run-plan.sh" >/dev/null 2>&1; then
        echo "ok  tests/smoke-run-plan.sh"
    else
        echo "FAIL tests/smoke-run-plan.sh (run it directly for details)"
        fail=1
    fi
else
    echo "skip  br or git-flow not installed"
fi
echo "Stage 9 done."

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
if [ "${fail}" -ne 0 ]; then
    echo "VALIDATION FAILED"
    exit 1
else
    echo "OK"
    exit 0
fi
