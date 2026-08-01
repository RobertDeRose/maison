#!/usr/bin/env bash

git_is_dirty() {
  local root="$1"
  [ -n "$(git -C "$root" status --porcelain)" ]
}

git_show_diff() {
  local root="$1"
  git -C "$root" diff -- "$@"
}

git_commit_paths() {
  local root="$1" message="$2"
  shift 2
  git -C "$root" add -- "$@"
  git -C "$root" commit -m "$message" -- "$@"
}
