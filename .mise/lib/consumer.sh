#!/usr/bin/env bash

# Consumer repositories own inventory, user configuration, host overrides, and
# the Nix flake/lock. Maison supplies the task/runtime code around them.

consumer_inventory_path() {
  printf '%s/inventory.toml\n' "$1"
}

load_maison_consumer_environment() {
  local root="$1" inventory
  export MAISON_CONSUMER_ROOT="$root"
  inventory="$(consumer_inventory_path "$root")"
  export MAISON_INVENTORY="$inventory"
  export MISE_GLOBAL_CONFIG_FILE="$root/config/mise/config.toml"
}

require_consumer_repository() {
  local root="${1:-$(maison_consumer_root)}" maison_root resolved_root
  maison_root="$(maison_install_root "${BASH_SOURCE[0]}")" || return 1
  resolved_root="$(cd "$root" 2> /dev/null && pwd -P)" || {
    printf 'consumer repository is unavailable: %s\n' "$root" >&2
    return 1
  }
  case "$resolved_root/" in
    "$maison_root/"*)
      printf 'consumer repository must be separate from Maison: %s\n' "$resolved_root" >&2
      return 1
      ;;
  esac
  case "$maison_root/" in
    "$resolved_root/"*)
      printf 'consumer repository must contain no Maison checkout: %s\n' "$resolved_root" >&2
      return 1
      ;;
  esac
  [ -d "$root" ] || {
    printf 'consumer repository is unavailable: %s\n' "$root" >&2
    return 1
  }
  [ -f "$root/flake.nix" ] && [ ! -L "$root/flake.nix" ] || {
    printf 'consumer repository requires a regular flake.nix: %s\n' "$root" >&2
    return 1
  }
  [ -f "$root/flake.lock" ] && [ ! -L "$root/flake.lock" ] || {
    printf 'consumer repository requires a regular flake.lock: %s\n' "$root" >&2
    return 1
  }
  [ -f "$root/inventory.toml" ] && [ ! -L "$root/inventory.toml" ] || {
    printf 'consumer repository requires a regular inventory.toml: %s\n' "$root" >&2
    return 1
  }
}
