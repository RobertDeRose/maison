#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
mkdir -p "$HOME/.local/bin" "$HOME/.local/state/maison/backups/pi"

# Pi mutates settings.json. Merge checked-in defaults while preserving any
# additional package selections made interactively.
settings="$HOME/.pi/agent/settings.json"
defaults="$root/dotfiles/pi/settings.defaults.json"
old_extension="$HOME/.pi/agent/extensions/interface-overlays.ts"
if [ -e "$old_extension" ]; then
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$old_extension" "$HOME/.local/state/maison/backups/pi/interface-overlays.ts.$timestamp"
fi
mkdir -p "$(dirname "$settings")"
[ -s "$settings" ] || printf '{}\n' > "$settings"
if command -v jq > /dev/null 2>&1 && [ -f "$defaults" ]; then
  tmp="$(mktemp)"
  if jq --slurpfile defaults "$defaults" '
    . * $defaults[0]
    | .packages = (((.packages // []) + ($defaults[0].packages // [])) | unique)
  ' "$settings" > "$tmp"; then
    mv "$tmp" "$settings"
    chmod 600 "$settings"
  else
    rm -f "$tmp"
    printf 'warning: could not merge Pi settings at %s\n' "$settings" >&2
  fi
fi

# Keep the repository CLI and its Usage runtime location-independent.
ln -sfn "$root/bin/maison" "$HOME/.local/bin/maison"
usage_bin="$(mise -C "$root" which usage 2> /dev/null || true)"
if [ -x "$usage_bin" ]; then
  ln -sfn "$usage_bin" "$HOME/.local/bin/usage"
fi
