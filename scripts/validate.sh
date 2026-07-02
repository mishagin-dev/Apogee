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
#   5. Self-tests     — idea_symbols.py + idea-usage-tracker.py --test
#
# Exits 0 if all stages pass, 1 on any failure.
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_JSON="${REPO_ROOT}/plugins/apogee/hooks/hooks.json"
PLUGIN_ROOT="${REPO_ROOT}/plugins/apogee"

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

if missing:
    for p in sorted(missing):
        print(f"FAIL path {p}")
    sys.exit(1)
else:
    print(f"All {len(paths)} hook paths resolved OK.")
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
SELFTESTS=(
    "${REPO_ROOT}/plugins/apogee/hooks/idea/lib/idea_symbols.py"
)
# Hook-entry scripts expose a --test mode (their __main__ otherwise runs the live hook on stdin).
HOOK_SELFTESTS=(
    "${REPO_ROOT}/plugins/apogee/hooks/idea/idea-usage-tracker.py"
)
for f in "${SELFTESTS[@]}"; do
    if python3 "$f" > /dev/null 2>&1; then
        echo "ok  $f"
    else
        echo "FAIL selftest $f"
        fail=1
    fi
done
for f in "${HOOK_SELFTESTS[@]}"; do
    if python3 "$f" --test > /dev/null 2>&1; then
        echo "ok  $f --test"
    else
        echo "FAIL selftest $f --test"
        fail=1
    fi
done
echo "Stage 5 done."

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
