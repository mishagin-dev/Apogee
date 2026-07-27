# file_patterns.sh — shared code-file-pattern resolution for the review/br Bash gates.
#
# Single source of truth for "which files count as trackable code" on the shell side:
# plugins/apogee/hooks/core/config/pipeline.json's `file_patterns` array. Sourced by
# review-docs-gate.sh, br-progress-gate.sh, and snapshot-baseline.sh so there is exactly ONE
# hardcoded fallback list on the shell side (used only when pipeline.json itself is missing or
# unreadable) instead of three independently-maintained copies that can -- and did -- drift out
# of sync with each other and with gate_common.py's CODE_EXTENSIONS (the Python-side mirror of
# this same list, also derived from pipeline.json -- see that file's `_load_code_extensions`).
# Bash 3.2 compatible (macOS ships 3.2 by default): no mapfile/readarray.
#
# Usage (from a script that has already set $SCRIPT_DIR):
#   source "$SCRIPT_DIR/<relative-path-to>/core/lib/file_patterns.sh"
#   PATS=()
#   while IFS= read -r p; do PATS+=("$p"); done < <(resolve_file_patterns "$CONFIG")

_FILE_PATTERNS_FALLBACK=(
    "*.py" "*.ts" "*.tsx" "*.js" "*.swift" "*.go" "*.rs" "*.kt" "*.kts"
    "*.c" "*.cpp" "*.h" "*.java" "*.php" "*.dart"
)

# resolve_file_patterns <config_path> -- prints one glob pattern per line on stdout: pipeline.json's
# `file_patterns` array if the file exists and the key is non-empty, else the fallback above.
resolve_file_patterns() {
    local config="$1" pat found=0
    if [[ -f "$config" ]]; then
        while IFS= read -r pat; do
            [[ -n "$pat" ]] && { printf '%s\n' "$pat"; found=1; }
        done < <(jq -r '(.file_patterns // [])|.[]' "$config" 2>/dev/null)
    fi
    if [[ "$found" -eq 0 ]]; then
        printf '%s\n' "${_FILE_PATTERNS_FALLBACK[@]}"
    fi
}
