#!/usr/bin/env bash
set -euo pipefail

SYSTEM="${1:?usage: build-platform-targets.sh <nix-system>}"
REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

case "$SYSTEM" in
  aarch64-darwin | aarch64-linux | x86_64-linux) ;;
  *)
    printf 'Unsupported system: %s\n' "$SYSTEM" >&2
    exit 1
    ;;
esac

build_target() {
  local target="$1"
  printf '==> Building %s\n' "$target"
  nix build --accept-flake-config --no-link "$target"
}

ensure_linux_user() {
  local username="$1" fullname="$2"
  id -u "$username" > /dev/null 2>&1 && return 0
  sudo useradd --create-home --comment "$fullname" --shell /bin/bash "$username"
}

ensure_darwin_user() {
  local username="$1" fullname="$2" next_uid
  id -u "$username" > /dev/null 2>&1 && return 0
  next_uid="$(dscl . -list /Users UniqueID | awk 'BEGIN { max = 500 } { if ($2 > max) max = $2 } END { print max + 1 }')"
  sudo dscl . -create "/Users/$username"
  sudo dscl . -create "/Users/$username" UserShell /bin/zsh
  sudo dscl . -create "/Users/$username" RealName "$fullname"
  sudo dscl . -create "/Users/$username" UniqueID "$next_uid"
  sudo dscl . -create "/Users/$username" PrimaryGroupID 20
  sudo dscl . -create "/Users/$username" NFSHomeDirectory "/Users/$username"
  sudo createhomedir -c -u "$username" > /dev/null 2>&1 || true
}

ensure_runner_user() {
  local username="$1" fullname="$2"
  case "$SYSTEM" in
    *-darwin) ensure_darwin_user "$username" "$fullname" ;;
    *-linux) ensure_linux_user "$username" "$fullname" ;;
  esac
}

host_rows() {
  python3 "$REPO_ROOT/.mise/lib/inventory.py" \
    --file "$REPO_ROOT/inventory.toml" \
    --repo-root "$REPO_ROOT" \
    host-rows \
    --system "$SYSTEM"
}

attribute_names() {
  nix eval --accept-flake-config --json "$1" --apply builtins.attrNames |
    python3 -c 'import json, sys; print("\n".join(json.load(sys.stdin)))'
}

while IFS= read -r package; do
  [ -n "$package" ] || continue
  build_target ".#packages.\"$SYSTEM\".\"$package\""
done < <(attribute_names ".#packages.\"$SYSTEM\"")

while IFS= read -r check; do
  [ -n "$check" ] || continue
  build_target ".#checks.\"$SYSTEM\".\"$check\""
done < <(attribute_names ".#checks.\"$SYSTEM\"")

found=false
while IFS=$'\t' read -r host username fullname; do
  [ -n "$host" ] || continue
  found=true
  ensure_runner_user "$username" "$fullname"
  case "$SYSTEM" in
    *-darwin)
      build_target ".#darwinConfigurations.\"$host\".system"
      ;;
    *-linux)
      build_target ".#systemConfigs.\"$host\""
      ;;
  esac
done < <(host_rows)

if [ "$found" = false ]; then
  printf '==> No inventory hosts target %s; package outputs were still validated.\n' "$SYSTEM"
fi
