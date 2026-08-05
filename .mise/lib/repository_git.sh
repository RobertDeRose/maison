#!/usr/bin/env bash

repository_git_helper() {
  local framework_root="$1"
  printf '%s/scripts/maison_repository_git.py\n' "$framework_root"
}

repository_require_authoring() {
  local repository="$1" operation="$2" framework_root="${MAISON_HOME:-${MISE_PROJECT_ROOT:-}}" repository_path
  if [ -n "$framework_root" ] &&
    [ "$(cd "$framework_root" 2> /dev/null && pwd -P)" = "$(cd "$repository" 2> /dev/null && pwd -P)" ]; then
    printf '%s: a separate consumer repository is required; Maison is not an authoring target\n' \
      "$operation" >&2
    return 1
  fi
  [ -d "$repository" ] || {
    printf '%s: consumer repository is unavailable: %s\n' "$operation" "$repository" >&2
    return 1
  }
  git -C "$repository" rev-parse --show-toplevel > /dev/null 2>&1 || {
    printf '%s: consumer repository is not a Git authoring checkout: %s\n' "$operation" "$repository" >&2
    return 1
  }
  repository_path="$(cd "$repository" && pwd -P)"
  export MAISON_PRIVATE_REPOSITORY_PATH="$repository_path"
}

repository_refresh() {
  local framework_root="$1" repository="$2" operation="$3" output status
  set +e
  output="$(python3 "$(repository_git_helper "$framework_root")" refresh --repo "$repository" 2>&1)"
  status=$?
  set -e
  if [ "$status" -ne 0 ]; then
    printf '%s: consumer repository refresh failed\n%s\n' "$operation" "$output" >&2
    return "$status"
  fi
  [ -z "$output" ] || printf '%s\n' "$output"
}

repository_require_clean() {
  local framework_root="$1" repository="$2" operation="$3"
  shift 3
  local -a args=(check-clean --repo "$repository")
  local path output status
  for path in "$@"; do
    args+=(--path "$path")
  done
  set +e
  output="$(python3 "$(repository_git_helper "$framework_root")" "${args[@]}" 2>&1)"
  status=$?
  set -e
  if [ "$status" -ne 0 ]; then
    printf '%s: mutation target is not clean\n%s\n' "$operation" "$output" >&2
    return "$status"
  fi
}

repository_commit() {
  local framework_root="$1" repository="$2" operation="$3" scope="$4" identifier="$5"
  shift 5
  local -a args=(commit --repo "$repository" --operation "$operation" --scope "$scope" --identifier "$identifier")
  local path output status subject
  for path in "$@"; do
    args+=(--path "$path")
  done
  set +e
  output="$(python3 "$(repository_git_helper "$framework_root")" "${args[@]}" 2>&1)"
  status=$?
  set -e
  if [ "$status" -ne 0 ]; then
    subject="${operation}(${scope}): \`${identifier}\`"
    printf '%s: Git commit failed after the declaration transaction; changes remain in %s\n' \
      "$scope" "$repository" >&2
    printf '%s\n' "$output" >&2
    printf 'Manual recovery: git -C %q add --' "$repository" >&2
    printf ' %q' "$@" >&2
    printf ' && git -C %q commit -m %q\n' "$repository" "$subject" >&2
    return "$status"
  fi
  printf '%s\n' "$output"
}
