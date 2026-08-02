#!/usr/bin/env bash

maison_overlay_python_available() {
  command -v python3 > /dev/null 2>&1 && python3 -c 'import tomllib' > /dev/null 2>&1
}

maison_overlay_path() {
  local root="$1"
  if maison_overlay_python_available; then
    python3 "$root/scripts/maison_overlay.py" path 2> /dev/null || true
  fi
}

maison_inventory_path() {
  local root="$1"
  if maison_overlay_python_available; then
    python3 "$root/scripts/maison_overlay.py" --repo-root "$root" inventory-path 2> /dev/null || true
    return
  fi
  printf '%s/inventory.toml\n' "$root"
}

maison_user_config_root() {
  local root="$1" overlay_path
  overlay_path="$(maison_overlay_path "$root")"
  if [ -n "$overlay_path" ] && [ -f "$overlay_path/config/mise/config.toml" ]; then
    printf '%s\n' "$overlay_path"
  else
    printf '%s\n' "$root"
  fi
}

load_maison_overlay_environment() {
  local root="$1" overlay_path inventory_path config_root
  overlay_path="$(maison_overlay_path "$root")"
  if [ -n "$overlay_path" ]; then
    export MAISON_OVERLAY_PATH="$overlay_path"
  fi
  config_root="$(maison_user_config_root "$root")"
  export MAISON_USER_CONFIG_ROOT="$config_root"
  export MISE_GLOBAL_CONFIG_FILE="$config_root/config/mise/config.toml"
  inventory_path="$(maison_inventory_path "$root")"
  if [ -n "$inventory_path" ]; then
    export MAISON_INVENTORY="$inventory_path"
  fi
}
