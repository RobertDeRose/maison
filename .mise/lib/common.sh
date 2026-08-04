#!/usr/bin/env bash

repo_root() {
  local start="${1:-${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}}" directory git_root

  if [ -n "${MISE_PROJECT_ROOT:-}" ] &&
    [ -f "$MISE_PROJECT_ROOT/mise.toml" ] &&
    [ -f "$MISE_PROJECT_ROOT/flake.nix" ]; then
    (cd "$MISE_PROJECT_ROOT" && pwd -P)
    return
  fi

  if git_root="$(git -C "$(dirname "$start")" rev-parse --show-toplevel 2> /dev/null)" &&
    [ -f "$git_root/mise.toml" ] &&
    [ -f "$git_root/flake.nix" ]; then
    printf '%s\n' "$git_root"
    return
  fi

  directory="$(cd "$(dirname "$start")" && pwd -P)"
  while [ "$directory" != / ]; do
    if [ -f "$directory/mise.toml" ] && [ -f "$directory/flake.nix" ]; then
      printf '%s\n' "$directory"
      return
    fi
    directory="$(dirname "$directory")"
  done

  die "could not locate Maison repository root from $start"
}

log_info() { printf '==> %s\n' "$*"; }
log_warn() { printf 'warning: %s\n' "$*" >&2; }
log_error() { printf 'error: %s\n' "$*" >&2; }

run_with_startup_spinner_relay() {
  local ready_file="$1" release_file="$2" done_file="$3" line first=true
  while IFS= read -r line || [ -n "$line" ]; do
    if [ "$first" = true ]; then
      : > "$ready_file"
      while [ ! -e "$release_file" ]; do sleep 0.01; done
      first=false
    fi
    printf '%s\n' "$line"
  done
  : > "$done_file"
}

run_with_startup_spinner() {
  [ "$#" -ge 2 ] || {
    log_error "run_with_startup_spinner requires a label and command"
    return 2
  }

  local label="$1"
  shift
  case "${MAISON_SPINNER:-auto}" in
    never)
      "$@"
      return
      ;;
    always) ;;
    *)
      if is_ci || { [ ! -t 2 ] && [ "${MAISON_INTERACTIVE:-false}" != true ]; }; then
        "$@"
        return
      fi
      ;;
  esac

  local output_dir ready_file release_file stdout_done stderr_done pid
  local frame_index=0 frames='|/-' status
  if ! output_dir="$(mktemp -d "${TMPDIR:-/tmp}/maison-spinner.XXXXXX")"; then
    "$@"
    return
  fi
  ready_file="$output_dir/ready"
  release_file="$output_dir/release"
  stdout_done="$output_dir/stdout-done"
  stderr_done="$output_dir/stderr-done"

  # Hold the first line until the spinner is cleared, then stream both output
  # channels without letting carriage-return updates corrupt the terminal.
  "$@" > >(run_with_startup_spinner_relay "$ready_file" "$release_file" "$stdout_done") \
    2> >(run_with_startup_spinner_relay "$ready_file" "$release_file" "$stderr_done" >&2) &
  pid=$!
  while kill -0 "$pid" 2> /dev/null && [ ! -e "$ready_file" ]; do
    printf '\r\033[2K==> %s %s' "$label" "${frames:frame_index:1}" >&2
    frame_index=$(((frame_index + 1) % ${#frames}))
    sleep 0.1
  done
  printf '\r\033[2K' >&2
  : > "$release_file"

  if wait "$pid"; then
    status=0
  else
    status=$?
  fi
  while [ ! -e "$stdout_done" ] || [ ! -e "$stderr_done" ]; do sleep 0.01; done
  rm -rf "$output_dir"
  if [ "$status" -eq 0 ]; then
    printf '==> %s done\n' "$label" >&2
  else
    printf '==> %s failed (exit %s)\n' "$label" "$status" >&2
  fi
  return "$status"
}

die() {
  log_error "$*"
  return 1
}

require_command() {
  command -v "$1" > /dev/null 2>&1 || die "required command not found: $1"
}

is_ci() {
  [ "${CI:-false}" = "true" ] || [ "${CI:-}" = "1" ]
}

confirm() {
  local prompt="${1:-Continue?}" reply
  if is_ci; then
    return 1
  fi
  printf '%s [y/N] ' "$prompt" >&2
  IFS= read -r reply
  case "$reply" in
    y | Y | yes | YES | Yes) return 0 ;;
    *) return 1 ;;
  esac
}

json_escape() {
  printf '%s' "$1" | awk 'BEGIN { ORS="" } { gsub(/\\/, "\\\\"); gsub(/\"/, "\\\""); gsub(/\t/, "\\t"); gsub(/\r/, "\\r"); if (NR > 1) printf "\\n"; printf "%s", $0 }'
}
