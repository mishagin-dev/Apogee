#!/usr/bin/env bash
# Open and close a zone worktree: a linked worktree of the superproject in which only the
# submodules one unit of work needs are populated, each as a linked worktree of the main
# checkout's own submodule repository (shared objects, branches and git-flow config; nothing is
# cloned). Parallel sessions then each own a HEAD and an index instead of sharing one.
#
# Usage:
#   zone-worktree.sh open <type>/<slug> <path>... [--read <path>...]   # from the main checkout
#   zone-worktree.sh close                                              # inside the zone worktree
#
# A <path> is a first-level submodule, or a directory holding several (`platform` = every
# submodule under platform/).
#
# open creates <root>/worktrees/<slug> on <type>/<slug> off the superproject's develop, and the
# same branch in each <path> off that submodule's develop; --read paths are checked out detached
# at their pins (build dependencies the work does not change). In that worktree every other
# submodule is made inactive and the populated ones get update=none: a bare
# `git submodule update` (`make sync`, say) there would otherwise clone the rest and repoint the
# shared submodule repositories at the worktree, which breaks them in the main checkout.
#
# close merges each <path> branch into its develop with git flow from the main checkout (a
# branch without commits is just deleted), pins the superproject branch to those develops and
# removes the worktrees. It prints the superproject finish, which the caller runs.
#
# Stops at the first failing step (-e) and leaves the state for the caller to read.
set -euo pipefail
export GIT_OPTIONAL_LOCKS=0 GIT_MERGE_AUTOEDIT=no

die() { echo "zone-worktree: $*" >&2; exit 1; }

common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || die "not in a git repository"
[ "$(basename "$common")" = ".git" ] || die "run it from the superproject, not from inside a submodule"
root=$(dirname "$common")
[ -f "$root/.gitmodules" ] || die "$root has no submodules"
develop_of() { git -C "$1" config --get gitflow.branch.develop 2>/dev/null || echo develop; }

# All first-level submodules as "name<TAB>path" lines.
submodules=$(git config --file "$root/.gitmodules" --get-regexp '^submodule\..*\.path$' |
  sed -E 's/^submodule\.(.*)\.path (.*)$/\1	\2/')

# expand <path>...: the submodule paths each argument names (itself, or every one under it).
expand() {
  local arg found p
  for arg in "$@"; do
    arg=${arg%/}
    found=0
    while IFS='	' read -r _ p; do
      case "$p" in "$arg"|"$arg"/*) echo "$p"; found=1 ;; esac
    done <<< "$submodules"
    [ "$found" -eq 1 ] || die "$arg is not a submodule and holds none"
  done
}

open_zone() {
  [ "$(git rev-parse --path-format=absolute --git-dir)" = "$common" ] || die "run open from the main checkout"
  local branch=$1; shift
  case "$branch" in */*) ;; *) die "branch must be <type>/<slug>" ;; esac
  local slug=${branch#*/} write=() read=() mode=write a p
  for a in "$@"; do
    if [ "$a" = "--read" ]; then mode=read; continue; fi
    if [ "$mode" = write ]; then write+=("$a"); else read+=("$a"); fi
  done
  [ "${#write[@]}" -gt 0 ] || die "name at least one path to work in"
  local wpaths rpaths=""
  wpaths=$(expand "${write[@]}" | sort -u)
  [ "${#read[@]}" -gt 0 ] && rpaths=$(expand "${read[@]}" | sort -u | grep -vxF -f <(printf '%s\n' "$wpaths") || true)

  for p in $wpaths $rpaths; do
    [ -e "$root/$p/.git" ] || die "$p is not initialised in the main checkout"
  done
  for p in $wpaths; do
    git -C "$root/$p" config --get gitflow.branch.develop >/dev/null ||
      die "$p has no git-flow; initialise it there first"
  done

  local wt="$root/worktrees/$slug"
  [ -e "$wt" ] && die "$wt already exists"
  local exclude
  exclude=$(git -C "$root" rev-parse --git-path info/exclude)
  grep -qxF '/worktrees/' "$exclude" 2>/dev/null || echo '/worktrees/' >> "$exclude"

  if git -C "$root" rev-parse --verify -q "refs/heads/$branch" >/dev/null; then
    git -C "$root" worktree add -q "$wt" "$branch"
  else
    git -C "$root" worktree add -q -b "$branch" "$wt" "$(develop_of "$root")"
  fi
  git -C "$root" config extensions.worktreeConfig true
  local name
  while IFS='	' read -r name p; do
    if printf '%s\n' $wpaths $rpaths | grep -qxF "$p"; then
      git -C "$wt" config --worktree "submodule.$name.update" none
    else
      git -C "$wt" config --worktree "submodule.$name.active" false
    fi
  done <<< "$submodules"
  git -C "$wt" config --worktree apogee.zone "$(echo $wpaths)"
  git -C "$wt" config --worktree apogee.zoneRead "$(echo $rpaths)"

  for p in $wpaths; do
    rmdir "$wt/$p"
    if git -C "$root/$p" rev-parse --verify -q "refs/heads/$branch" >/dev/null; then
      git -C "$root/$p" worktree add -q "$wt/$p" "$branch"
    else
      git -C "$root/$p" worktree add -q -b "$branch" "$wt/$p" "$(develop_of "$root/$p")"
    fi
  done
  for p in $rpaths; do
    rmdir "$wt/$p"
    git -C "$root/$p" worktree add -q --detach "$wt/$p" "$(git -C "$wt" rev-parse "HEAD:$p")"
  done
  echo "$wt"
}

close_zone() {
  local wt
  wt=$(git rev-parse --show-toplevel)
  [ "$(git rev-parse --path-format=absolute --git-dir)" != "$common" ] || die "run close inside the zone worktree"
  local wpaths rpaths branch type slug p
  wpaths=$(git -C "$wt" config --worktree --get apogee.zone) || die "$wt is not a zone worktree"
  rpaths=$(git -C "$wt" config --worktree --get apogee.zoneRead || true)
  branch=$(git -C "$wt" branch --show-current)
  type=${branch%%/*}; slug=${branch#*/}

  [ -z "$(git -C "$wt" status --porcelain --ignore-submodules=all)" ] || die "uncommitted changes in the superproject worktree"
  for p in $wpaths $rpaths; do
    [ -z "$(git -C "$wt/$p" status --porcelain)" ] || die "uncommitted changes in $p"
  done
  [ "$(git -C "$root" branch --show-current)" = "$(develop_of "$root")" ] ||
    die "the main checkout is not on $(develop_of "$root")"
  for p in $wpaths; do
    local dev
    dev=$(develop_of "$root/$p")
    [ "$(git -C "$root/$p" branch --show-current)" = "$dev" ] || die "$p in the main checkout is not on $dev"
    [ -z "$(git -C "$root/$p" status --porcelain)" ] || die "$p in the main checkout has uncommitted changes"
  done

  for p in $wpaths; do
    local dev ahead
    dev=$(develop_of "$root/$p")
    git -C "$wt/$p" checkout -q --detach
    # A branch already gone was merged by an earlier, interrupted close.
    if ! git -C "$root/$p" rev-parse --verify -q "refs/heads/$branch" >/dev/null; then
      ahead=-1
    else
      ahead=$(git -C "$root/$p" rev-list --count "$dev..$branch")
    fi
    if [ "$ahead" -lt 0 ]; then
      :
    elif [ "$ahead" -gt 0 ]; then
      (cd "$root/$p" && git flow "$type" finish "$slug")
    else
      git -C "$root/$p" branch -q -d "$branch"
    fi
    git -C "$wt/$p" checkout -q --detach "$dev"
    git -C "$wt" add "$p"
  done
  if ! git -C "$wt" diff --cached --quiet; then
    git -C "$wt" commit -q -m "chore: Pin the submodules of $slug to develop"
  fi
  for p in $wpaths $rpaths; do
    git -C "$root/$p" worktree remove "$wt/$p"
    mkdir "$wt/$p"
  done
  git -C "$root" worktree remove "$wt"
  echo "next, from $root: git flow $type finish $slug"
}

case "${1:-}" in
  open) shift; open_zone "$@" ;;
  close) close_zone ;;
  *) die "usage: zone-worktree.sh open <type>/<slug> <path>... [--read <path>...] | close" ;;
esac
