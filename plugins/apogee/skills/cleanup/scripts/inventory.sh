#!/usr/bin/env bash
# Worktree inventory: read-only. Lists every linked worktree of a repository and of
# each of its submodules, with a verdict per entry. Deletes nothing.
#
# Usage: inventory.sh [--no-size] [<path inside the repo>]
#
# Output, one line per entry, tab-separated:
#   VERDICT  SIZE  PATH  REF  NOTE
# VERDICT:
#   PRUNE    git still records a worktree whose directory is gone
#   REMOVE   clean, and every commit is on a base branch or a remote
#   KEEP     uncommitted changes, unpushed commits, locked, or used in the last 2 hours
#   NESTED   a submodule worktree inside another listed worktree (goes with it)
#   ORPHAN   a directory with a .git file pointing at a gitdir that no longer exists
#   BUILD    a build directory in the main checkout (rebuildable, never removed here)
#
# Exit 0 on success, 1 when the path is not inside a git repository.
# Errors are not fatal per entry: a worktree that cannot be inspected is reported KEEP.
set -uo pipefail

SIZE=1
ACTIVE_MIN=120
# Keep 'git status' from rewriting the index, so this scan does not mark a worktree active.
export GIT_OPTIONAL_LOCKS=0
if [ "${1:-}" = "--no-size" ]; then SIZE=0; shift; fi
START=${1:-$PWD}

common=$(git -C "$START" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || {
  echo "not inside a git repository: $START" >&2; exit 1; }
# The main checkout of the superproject, even when started from a linked worktree
# or from inside a submodule.
super=$(git -C "$START" rev-parse --show-superproject-working-tree 2>/dev/null)
if [ -n "$super" ]; then
  common=$(git -C "$super" rev-parse --path-format=absolute --git-common-dir)
fi
root=$(dirname "$common")

size_of() {
  if [ "$SIZE" = 1 ] && [ -e "$1" ]; then du -sh "$1" 2>/dev/null | cut -f1; else echo "-"; fi
}

# Commits reachable from HEAD of a worktree that no base branch or remote holds.
unique_commits() {
  local wt=$1 refs=() b
  for b in develop main master; do
    git -C "$wt" show-ref --verify --quiet "refs/heads/$b" && refs+=("refs/heads/$b")
  done
  git -C "$wt" rev-list --count HEAD --not "${refs[@]}" --remotes 2>/dev/null || echo "?"
}

# Every git common dir to inspect: the superproject, then each initialised submodule.
gitdirs=("$common")
while IFS= read -r sub; do
  [ -n "$sub" ] || continue
  gd=$(git -C "$root/$sub" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || continue
  gitdirs+=("$gd")
done < <(git -C "$root" submodule foreach --recursive --quiet 'echo "$displaypath"' 2>/dev/null)

# Pass 1: collect linked worktrees as "gitdir<TAB>path<TAB>ref<TAB>flags".
entries=()
for gd in "${gitdirs[@]}"; do
  first=1 path= head= ref= flags=
  while IFS= read -r line; do
    case "$line" in
      "worktree "*) path=${line#worktree } ;;
      "HEAD "*)     head=${line#HEAD } ;;
      "branch "*)   ref=${line#branch refs/heads/} ;;
      detached)     ref=detached ;;
      prunable*)    flags="$flags prunable" ;;
      locked*)      flags="$flags locked" ;;
      "")
        if [ -n "$path" ]; then
          [ "$ref" = detached ] && ref="detached@${head:0:7}"
          [ "$first" = 1 ] || entries+=("$gd	$path	$ref	$flags")
          first=0
        fi
        path= head= ref= flags= ;;
    esac
  done < <(git --git-dir="$gd" worktree list --porcelain 2>/dev/null; echo)
done

# A path that lies inside another listed, existing worktree is NESTED in it.
parent_of() {
  local p=$1 e other
  for e in "${entries[@]}"; do
    other=$(cut -f2 <<<"$e")
    [ "$other" != "$p" ] && [ -d "$other" ] && case "$p" in "$other"/*) echo "$other"; return;; esac
  done
}

printf 'VERDICT\tSIZE\tPATH\tREF\tNOTE\n'
for e in "${entries[@]}"; do
  IFS=$'\t' read -r gd path ref flags <<<"$e"
  if [[ "$flags" == *prunable* ]] || [ ! -d "$path" ]; then
    printf 'PRUNE\t-\t%s\t%s\tdirectory gone; record in %s\n' "$path" "$ref" "$gd"; continue
  fi
  parent=$(parent_of "$path")
  if [ -n "$parent" ]; then
    printf 'NESTED\t-\t%s\t%s\tinside %s\n' "$path" "$ref" "$parent"; continue
  fi
  notes=()
  dirty=$(git -C "$path" status --porcelain --ignore-submodules=none 2>/dev/null | wc -l | tr -d ' ')
  uniq=$(unique_commits "$path")
  [ "$dirty" != 0 ] && notes+=("$dirty uncommitted")
  [ "$uniq" != 0 ] && notes+=("$uniq commit(s) on no base branch or remote")
  [[ "$flags" == *locked* ]] && notes+=("locked")
  # Another session may be working there: git touches the index on every status/commit.
  index=$(git -C "$path" rev-parse --path-format=absolute --git-path index 2>/dev/null)
  [ -n "$index" ] && [ -n "$(find "$index" -mmin -"$ACTIVE_MIN" 2>/dev/null)" ] \
    && notes+=("active in the last $ACTIVE_MIN min")
  # Submodules checked out inside this worktree have their own gitdirs; commits made
  # there and pushed nowhere are lost with the directory.
  while IFS= read -r sp; do
    [ -n "$sp" ] || continue
    su=$(unique_commits "$path/$sp")
    [ "$su" != 0 ] && notes+=("$sp: $su unpushed commit(s)")
  done < <(git -C "$path" submodule foreach --recursive --quiet 'echo "$displaypath"' 2>/dev/null)
  # Submodule worktrees nested in this one count towards its verdict.
  for n in "${entries[@]}"; do
    IFS=$'\t' read -r _ npath _ _ <<<"$n"
    case "$npath" in "$path"/*)
      [ -d "$npath" ] || continue
      nd=$(git -C "$npath" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
      nu=$(unique_commits "$npath")
      [ "$nd" != 0 ] && notes+=("${npath#"$path"/}: $nd uncommitted")
      [ "$nu" != 0 ] && notes+=("${npath#"$path"/}: $nu unpushed commit(s)")
      ;;
    esac
  done
  if [ ${#notes[@]} -eq 0 ]; then verdict=REMOVE; note="clean, merged or pushed"
  else verdict=KEEP; note=$(IFS=";"; echo "${notes[*]}" | sed "s/;/; /g"); fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$verdict" "$(size_of "$path")" "$path" "$ref" "$note"
done

# Orphans: a .git file whose gitdir is gone, near the repo (inside it and next to it).
while IFS= read -r gitfile; do
  target=$(sed -n 's/^gitdir: //p' "$gitfile")
  [ -n "$target" ] || continue
  case "$target" in /*) ;; *) target="$(dirname "$gitfile")/$target" ;; esac
  [ -e "$target" ] && continue
  dir=$(dirname "$gitfile")
  printf 'ORPHAN\t%s\t%s\t-\tgitdir %s is gone\n' "$(size_of "$dir")" "$dir" "$target"
done < <(find "$root" "$(dirname "$root")" -maxdepth 3 -name .git -type f \
           -not -path '*/target/*' -not -path '*/node_modules/*' 2>/dev/null | sort -u)

# Build directories of the main checkout: reported, never removed by this skill.
while IFS= read -r b; do
  printf 'BUILD\t%s\t%s\t-\trebuildable; main checkout\n' "$(size_of "$b")" "$b"
done < <(find "$root" -maxdepth 4 -type d \( -name target -o -name DerivedData -o -name .build \) \
           -prune 2>/dev/null | while IFS= read -r d; do
             skip=0
             for e in "${entries[@]}"; do
               p=$(cut -f2 <<<"$e"); case "$d" in "$p"/*) skip=1;; esac
             done
             [ "$skip" = 0 ] && echo "$d"
           done)
exit 0
