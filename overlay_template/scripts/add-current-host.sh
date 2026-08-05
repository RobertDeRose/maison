#!/usr/bin/env bash
# Register the generated consumer host through Maison's validated host:add task.
set -euo pipefail

error() {
  printf 'error: consumer setup: %s\n' "$*" >&2
  exit 1
}

maison_home="${MAISON_HOME:-}"
consumer_root="${MAISON_CONSUMER_ROOT:-.}"
host="${MAISON_HOST:-$(hostname -s)}"
username="${USERNAME:-}"

[ -n "$maison_home" ] || error 'MAISON_HOME must point to a Maison checkout; rerun Copier from Maison'
[ -d "$maison_home" ] || error "Maison checkout does not exist: $maison_home"
maison_home="$(cd "$maison_home" && pwd -P)"
consumer_root="$(cd "$consumer_root" && pwd -P)"
[ -n "$username" ] || error 'Copier did not provide the inventory username'
command -v git >/dev/null 2>&1 || error 'git is required to initialize the consumer repository'
command -v mise >/dev/null 2>&1 || error 'mise is required to register the current host'

if [ ! -e "$consumer_root/.git" ]; then
  git -C "$consumer_root" init --quiet
  git -C "$consumer_root" branch -M main 2>/dev/null || true
fi

export MAISON_HOME="$maison_home"
export MAISON_CONSUMER_ROOT="$consumer_root"
temporary_lock=false
cleanup() {
  local status=$?
  if [ "$temporary_lock" = true ]; then
    rm -f "$consumer_root/flake.lock"
  fi
  exit "$status"
}
trap cleanup EXIT
if [ ! -e "$consumer_root/flake.lock" ] && [ ! -L "$consumer_root/flake.lock" ]; then
  cat >"$consumer_root/flake.lock" <<'JSON'
{
  "nodes": {},
  "root": "root",
  "version": 7
}
JSON
  temporary_lock=true
fi
mise -C "$maison_home" run host:add -- "$host" --user "$username"
if [ "$temporary_lock" = true ]; then
  rm -f "$consumer_root/flake.lock"
  temporary_lock=false
fi
trap - EXIT
