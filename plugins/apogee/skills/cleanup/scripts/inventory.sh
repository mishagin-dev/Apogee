#!/usr/bin/env bash
# Worktree inventory: read-only. Lists every linked worktree of a repository and of
# each of its submodules, with a verdict per entry. Deletes nothing.
#
# Usage: inventory.sh [--no-size] [<path inside the repo>]   (either order)
#
# Output, one line per entry, tab-separated:
#   VERDICT  SIZE  PATH  REF  NOTE
# VERDICT:
#   PRUNE    git still records a worktree whose directory is gone
#   REMOVE   clean, and every commit is on a base branch or a remote
#   KEEP     uncommitted changes, unpushed commits, locked, or used in the last 2 hours
#   NESTED   a submodule worktree inside another listed worktree (goes with it)
#   ORPHAN   a directory in the repo whose .git file points at a gitdir that is gone
#   BUILD    a Rust target/ or Xcode DerivedData/ of the main checkout
#            (rebuildable, never removed by the skill unless asked)
#
# Exit 0 on success, 1 when the path is not inside a git repository.
# Runs on bash 3.2 (macOS /bin/bash): no empty-array expansion under set -u.
# No -e: a git call failing on one worktree must not end the scan; such a worktree is
# reported KEEP ("?" commits) instead.
set -uo pipefail

SIZE=1
ACTIVE_MIN=120
START=$PWD
for arg in "$@"; do
  case "$arg" in
    --no-size) SIZE=0 ;;
    *) START=$arg ;;
  esac
done
# Keep 'git status' from rewriting the index, so this scan does not mark a worktree active.
export GIT_OPTIONAL_LOCKS=0

git -C "$START" rev-parse --git-dir >/dev/null 2>&1 || {
  echo "not inside a git repository: $START" >&2; exit 1; }
# Climb to the outermost superproject: from a submodule of a submodule, one step is not enough.
top=$(git -C "$START" rev-parse --show-toplevel)
while up=$(git -C "$top" rev-parse --show-superproject-working-tree 2>/dev/null) && [ -n "$up" ]; do
  top=$up
done
common=$(git -C "$top" rev-parse --path-format=absolute --git-common-dir)
root=$(dirname "$common")

size_of() {
  if [ "$SIZE" = 1 ] && [ -e "$1" ]; then du -sh "$1" 2>/dev/null | cut -f1; else echo "-"; fi
}

# Number of commits reachable from HEAD that no base branch and no remote holds; "?" on error.
unique_commits() {
  local wt=$1 b args="--remotes"
  for b in develop main master; do
    git -C "$wt" show-ref --verify --quiet "refs/heads/$b" && args="$args refs/heads/$b"
  done
  # shellcheck disable=SC2086
  git -C "$wt" rev-list --count HEAD --not $args 2>/dev/null || echo "?"
}

# Reasons a worktree must stay, separated by "; ". Empty means safe to remove.
# $1 = path, $2 = porcelain flags, $3 = label prefix for nested entries.
assess() {
  local path=$1 flags=$2 label=$3 out="" n index
  add() { out="${out:+$out; }$label$1"; }
  n=$(git -C "$path" status --porcelain --ignore-submodules=none 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" != 0 ] && add "$n uncommitted"
  n=$(unique_commits "$path")
  [ "$n" != 0 ] && add "$n commit(s) on no base branch or remote"
  case "$flags" in *locked*) add "locked" ;; esac
  # Another session may be working there: git touches the index on every status or commit.
  index=$(git -C "$path" rev-parse --path-format=absolute --git-path index 2>/dev/null)
  [ -n "$index" ] && [ -n "$(find "$index" -mmin -"$ACTIVE_MIN" 2>/dev/null)" ] \
    && add "active in the last $ACTIVE_MIN min"
  echo "$out"
}

# Every git common dir to inspect: the superproject, then each initialised submodule.
gitdirs=("$common")
while IFS= read -r sub; do
  [ -n "$sub" ] || continue
  gd=$(git -C "$root/$sub" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || continue
  gitdirs+=("$gd")
done < <(git -C "$root" submodule foreach --recursive --quiet 'echo "$displaypath"' 2>/dev/null)

# Linked worktrees, as parallel arrays. The first porcelain block of each gitdir is its
# main checkout and is skipped.
W_GD=() W_PATH=() W_REF=() W_FLAGS=()
for gd in "${gitdirs[@]}"; do
  first=1 path="" head="" ref="" flags=""
  while IFS= read -r line; do
    case "$line" in
      "worktree "*) path=${line#worktree } ;;
      "HEAD "*)     head=${line#HEAD } ;;
      "branch "*)   ref=${line#branch refs/heads/} ;;
      detached)     ref="detached@${head:0:7}" ;;
      prunable*)    flags="$flags prunable" ;;
      locked*)      flags="$flags locked" ;;
      "")
        if [ -n "$path" ] && [ "$first" = 0 ]; then
          W_GD+=("$gd"); W_PATH+=("$path"); W_REF+=("${ref:--}"); W_FLAGS+=("$flags")
        fi
        [ -n "$path" ] && first=0
        path="" head="" ref="" flags="" ;;
    esac
  done < <(git --git-dir="$gd" worktree list --porcelain 2>/dev/null; echo)
done
COUNT=${#W_PATH[@]}

# Index of the existing worktree that contains path $1, or empty.
parent_of() {
  local i other
  for ((i = 0; i < COUNT; i++)); do
    other=${W_PATH[$i]}
    [ "$other" != "$1" ] && [ -d "$other" ] && case "$1" in "$other"/*) echo "$i"; return ;; esac
  done
}

printf 'VERDICT\tSIZE\tPATH\tREF\tNOTE\n'
for ((i = 0; i < COUNT; i++)); do
  path=${W_PATH[$i]} ref=${W_REF[$i]} flags=${W_FLAGS[$i]}
  if [ ! -d "$path" ]; then
    case "$flags" in
      # git worktree prune never removes a locked record: often a volume not mounted.
      *locked*) printf 'KEEP\t-\t%s\t%s\tlocked, directory missing (unmounted?)\n' "$path" "$ref" ;;
      *) printf 'PRUNE\t-\t%s\t%s\tdirectory gone; record in %s\n' "$path" "$ref" "${W_GD[$i]}" ;;
    esac
    continue
  fi
  p=$(parent_of "$path")
  if [ -n "$p" ]; then
    printf 'NESTED\t-\t%s\t%s\tinside %s\n' "$path" "$ref" "${W_PATH[$p]}"; continue
  fi
  note=$(assess "$path" "$flags" "")
  # Submodules checked out inside this worktree: their own gitdirs, or linked worktrees of
  # the main checkout's submodule gitdirs. Either way they go with the directory.
  while IFS= read -r sp; do
    [ -n "$sp" ] || continue
    n=$(unique_commits "$path/$sp")
    [ "$n" != 0 ] && note="${note:+$note; }$sp: $n commit(s) on no base branch or remote"
  done < <(git -C "$path" submodule foreach --recursive --quiet 'echo "$displaypath"' 2>/dev/null)
  for ((j = 0; j < COUNT; j++)); do
    case "${W_PATH[$j]}" in "$path"/*)
      [ -d "${W_PATH[$j]}" ] || continue
      sub=$(assess "${W_PATH[$j]}" "${W_FLAGS[$j]}" "${W_PATH[$j]#"$path"/}: ")
      [ -n "$sub" ] && note="${note:+$note; }$sub" ;;
    esac
  done
  if [ -z "$note" ]; then verdict=REMOVE note="clean, merged or pushed"; else verdict=KEEP; fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$verdict" "$(size_of "$path")" "$path" "$ref" "$note"
done

# Orphans: a .git file inside the repo whose gitdir is gone.
while IFS= read -r gitfile; do
  target=$(sed -n 's/^gitdir: //p' "$gitfile")
  [ -n "$target" ] || continue
  case "$target" in /*) ;; *) target="$(dirname "$gitfile")/$target" ;; esac
  [ -e "$target" ] && continue
  dir=$(dirname "$gitfile")
  printf 'ORPHAN\t%s\t%s\t-\tgitdir %s is gone\n' "$(size_of "$dir")" "$dir" "$target"
done < <(find "$root" -mindepth 2 -maxdepth 3 -name .git -type f \
           -not -path '*/target/*' -not -path '*/node_modules/*' 2>/dev/null)

# Build directories of the main checkout, recognised by their manifest, not by name alone.
while IFS= read -r d; do
  parent=$(dirname "$d")
  case "$(basename "$d")" in
    target) [ -f "$parent/Cargo.toml" ] || continue ;;
  esac
  [ -n "$(parent_of "$d")" ] && continue
  printf 'BUILD\t%s\t%s\t-\trebuildable; main checkout\n' "$(size_of "$d")" "$d"
done < <(find "$root" -maxdepth 4 -type d \( -name target -o -name DerivedData \) \
           -prune 2>/dev/null)
exit 0
