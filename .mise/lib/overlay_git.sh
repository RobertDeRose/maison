#!/usr/bin/env bash

maison_overlay_git_helper() {
  local root="$1"
  printf '%s/scripts/maison_overlay_git.py\n' "$root"
}

maison_overlay_require_active() {
  local root="$1" operation="$2" overlay_path root_real overlay_real
  overlay_path="$(maison_overlay_path "$root")"
  if [ -z "$overlay_path" ]; then
    printf '%s: no active private overlay; configure an overlay before authoring\n' "$operation" >&2
    return 1
  fi
  root_real="$(cd "$root" && pwd -P)"
  overlay_real="$(cd "$overlay_path" && pwd -P)" || {
    printf '%s: active overlay path is unavailable: %s\n' "$operation" "$overlay_path" >&2
    return 1
  }
  if [ "$root_real" = "$overlay_real" ]; then
    printf '%s: public Maison is not a private overlay\n' "$operation" >&2
    return 1
  fi
  if ! git -C "$overlay_real" rev-parse --show-toplevel > /dev/null 2>&1; then
    printf '%s: active overlay is not a Git authoring checkout: %s\n' "$operation" "$overlay_real" >&2
    return 1
  fi
  export MAISON_PRIVATE_OVERLAY_PATH="$overlay_real"
  export MAISON_OVERLAY_PATH="$overlay_real"
}

maison_overlay_refresh() {
  local root="$1" repository="$2" operation="$3" output status
  set +e
  output="$(python3 "$(maison_overlay_git_helper "$root")" refresh --repo "$repository" 2>&1)"
  status=$?
  set -e
  if [ "$status" -ne 0 ]; then
    printf '%s: overlay refresh failed\n%s\n' "$operation" "$output" >&2
    return "$status"
  fi
  [ -z "$output" ] || printf '%s\n' "$output"
}

maison_overlay_require_clean() {
  local root="$1" repository="$2" operation="$3"
  shift 3
  local -a args=(check-clean --repo "$repository")
  local path output status
  for path in "$@"; do
    args+=(--path "$path")
  done
  set +e
  output="$(python3 "$(maison_overlay_git_helper "$root")" "${args[@]}" 2>&1)"
  status=$?
  set -e
  if [ "$status" -ne 0 ]; then
    printf '%s: mutation target is not clean\n%s\n' "$operation" "$output" >&2
    return "$status"
  fi
}

maison_overlay_commit() {
  local root="$1" repository="$2" operation="$3" scope="$4" identifier="$5"
  shift 5
  local -a args=(commit --repo "$repository" --operation "$operation" --scope "$scope" --identifier "$identifier")
  local -a paths=("$@")
  local path output status subject
  for path in "${paths[@]}"; do
    args+=(--path "$path")
  done
  set +e
  output="$(python3 "$(maison_overlay_git_helper "$root")" "${args[@]}" 2>&1)"
  status=$?
  set -e
  if [ "$status" -ne 0 ]; then
    subject="${operation}(${scope}): \`${identifier}\`"
    printf '%s: Git commit failed after the declaration transaction; changes remain in %s\n' \
      "$scope" "$repository" >&2
    printf '%s\n' "$output" >&2
    printf 'Manual recovery: git -C %q add --' "$repository" >&2
    printf ' %q' "${paths[@]}" >&2
    printf ' && git -C %q commit -m %q\n' "$repository" "$subject" >&2
    return "$status"
  fi
  printf '%s\n' "$output"
}
