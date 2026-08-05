#!/usr/bin/env bash
# Link generated global lockfiles outside mise dotfile processing.
set -euo pipefail

consumer_root="${MAISON_CONSUMER_ROOT:-}"
[ -n "$consumer_root" ] || {
  printf 'MAISON_CONSUMER_ROOT is required to link consumer lockfiles\n' >&2
  exit 1
}
consumer_root="$(cd "$consumer_root" 2> /dev/null && pwd -P)" || {
  printf 'consumer repository is unavailable: %s\n' "$consumer_root" >&2
  exit 1
}
dry_run=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=true ;;
    *)
      printf 'usage: %s [--dry-run]\n' "${0##*/}" >&2
      exit 2
      ;;
  esac
  shift
done

locks=(mise.lock config.macos.lock)
for name in "${locks[@]}"; do
  source="$consumer_root/config/mise/$name"
  target="$HOME/.config/mise/$name"
  [ -f "$source" ] || {
    printf 'missing generated lockfile: %s\n' "$source" >&2
    exit 1
  }
  if [ "$dry_run" = true ]; then
    printf 'ln -sfn %q %q\n' "$source" "$target"
  else
    mkdir -p "$(dirname "$target")"
    ln -sfn "$source" "$target"
  fi
done
