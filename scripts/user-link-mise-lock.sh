#!/usr/bin/env bash
# Link generated global lockfiles outside mise dotfile processing.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
config_root="${MAISON_USER_CONFIG_ROOT:-$root}"
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
  source="$config_root/config/mise/$name"
  target="$HOME/.config/mise/$name"
  [ -f "$source" ] || source="$root/config/mise/$name"
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
