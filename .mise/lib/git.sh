#!/usr/bin/env bash

# Git operations shared by consumer authoring tasks. These functions never
# fetch, pull, or push: Git history remains the consumer operator's boundary.

git_is_dirty() {
  local root="$1"
  [ -n "$(git -C "$root" status --porcelain)" ]
}

git_show_diff() {
  local root="$1"
  git -C "$root" diff -- "$@"
}

git_require_authoring() {
  local repository="$1" operation="$2" framework_root="${MAISON_HOME:-${MISE_PROJECT_ROOT:-}}"
  local repository_path framework_path

  [ -d "$repository" ] || {
    printf '%s: consumer repository is unavailable: %s\n' "$operation" "$repository" >&2
    return 1
  }
  repository_path="$(cd "$repository" 2> /dev/null && pwd -P)" || {
    printf '%s: consumer repository is unavailable: %s\n' "$operation" "$repository" >&2
    return 1
  }
  if [ -n "$framework_root" ] && framework_path="$(cd "$framework_root" 2> /dev/null && pwd -P)" &&
    [ "$framework_path" = "$repository_path" ]; then
    printf '%s: a separate consumer repository is required; Maison is not an authoring target\n' \
      "$operation" >&2
    return 1
  fi
  git -C "$repository_path" rev-parse --show-toplevel > /dev/null 2>&1 || {
    printf '%s: consumer repository is not a Git authoring checkout: %s\n' \
      "$operation" "$repository_path" >&2
    return 1
  }
  export MAISON_CONSUMER_REPOSITORY_PATH="$repository_path"
}

git_relative_path() {
  local repository="$1" path="$2" repository_path candidate parent base
  repository_path="$(cd "$repository" && pwd -P)" || return 1
  case "$path" in
    /*) candidate="$path" ;;
    *) candidate="$repository_path/$path" ;;
  esac
  parent="$(cd "$(dirname "$candidate")" 2> /dev/null && pwd -P)" || {
    printf 'path parent is unavailable: %s\n' "$path" >&2
    return 1
  }
  base="$(basename "$candidate")"
  candidate="$parent/$base"
  case "$candidate" in
    "$repository_path"/*) printf '%s\n' "${candidate#"$repository_path"/}" ;;
    *)
      printf 'path is outside consumer repository: %s\n' "$path" >&2
      return 1
      ;;
  esac
}

git_require_clean_paths() {
  local repository="$1" operation="$2" path relative changed
  shift 2
  [ "$#" -gt 0 ] || {
    printf '%s: at least one mutation target is required\n' "$operation" >&2
    return 1
  }
  for path in "$@"; do
    relative="$(git_relative_path "$repository" "$path")" || return 1
    changed="$(git -C "$repository" status --porcelain=v1 --untracked-files=all -- "$relative")"
    if [ -n "$changed" ]; then
      printf '%s: mutation target is not clean\n%s\n' "$operation" "$changed" >&2
      return 1
    fi
  done
}

git_commit_paths() {
  local repository="$1" operation="$2" scope="$3" identifier="$4" path relative
  local index changed sha subject status
  shift 4
  case "$operation" in
    added | removed) ;;
    *)
      printf 'focused commit operation must be added or removed\n' >&2
      return 1
      ;;
  esac
  case "$scope:$identifier" in
    *$'\n'* | *$'\r'*)
      printf 'focused commit scope and identifier cannot contain newlines\n' >&2
      return 1
      ;;
  esac
  [ "$#" -gt 0 ] || {
    printf 'focused commit requires at least one path\n' >&2
    return 1
  }

  local -a relative_paths=()
  for path in "$@"; do
    relative="$(git_relative_path "$repository" "$path")" || return 1
    relative_paths+=("$relative")
  done
  subject="$operation($scope): \`$identifier\`"
  index="$(mktemp "${TMPDIR:-/tmp}/maison-consumer-index.XXXXXX")"
  rm -f "$index"
  status=0
  (
    export GIT_INDEX_FILE="$index"
    git -C "$repository" rev-parse --verify HEAD > /dev/null || exit 1
    git -C "$repository" read-tree HEAD || exit
    git -C "$repository" add --all -- "${relative_paths[@]}" || exit
    changed="$(git -C "$repository" diff --cached --name-only)"
    [ -n "$changed" ] || {
      printf 'focused commit has no changes in its requested paths\n' >&2
      exit 1
    }
    git -C "$repository" commit --message "$subject"
  ) || status=$?
  rm -f "$index"
  if [ "$status" -ne 0 ]; then
    printf '%s: Git commit failed after the declaration transaction; changes remain in %s\n' \
      "$scope" "$repository" >&2
    printf 'Manual recovery: git -C %q add --' "$repository" >&2
    printf ' %q' "${relative_paths[@]}" >&2
    printf ' && git -C %q commit -m %q\n' "$repository" "$subject" >&2
    return "$status"
  fi

  # Keep only the committed paths aligned in the real index; unrelated staged
  # work belongs to the consumer operator and must remain untouched.
  git -C "$repository" add --all -- "${relative_paths[@]}" || return
  sha="$(git -C "$repository" rev-parse HEAD)"
  printf 'Created %s (%s).\n' "$subject" "$sha"
}
