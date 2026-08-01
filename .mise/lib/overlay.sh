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

load_maison_overlay_environment() {
  local root="$1" overlay_path inventory_path
  overlay_path="$(maison_overlay_path "$root")"
  if [ -n "$overlay_path" ]; then
    export MAISON_OVERLAY_PATH="$overlay_path"
  fi
  inventory_path="$(maison_inventory_path "$root")"
  if [ -n "$inventory_path" ]; then
    export MAISON_INVENTORY="$inventory_path"
  fi
}
