#!/usr/bin/env bash

load_nix_environment() {
  if command -v nix > /dev/null 2>&1; then
    return 0
  fi
  if [ -f /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh ]; then
    set +u
    # shellcheck disable=SC1091
    . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
    set -u
  fi
  command -v nix > /dev/null 2>&1 || die "Nix or Lix is not available"
}

configure_github_access_token() {
  local token="${MISE_GITHUB_TOKEN:-${GITHUB_API_TOKEN:-${GITHUB_TOKEN:-}}}"
  if [ -z "$token" ] && command -v mise > /dev/null 2>&1; then
    token="$(mise token github --raw 2> /dev/null || true)"
  fi
  if [ -z "$token" ] && command -v gh > /dev/null 2>&1; then
    token="$(gh auth token 2> /dev/null || true)"
  fi
  if [ -n "$token" ]; then
    export GITHUB_TOKEN="$token"
    case "${NIX_CONFIG:-}" in
      *"access-tokens = github.com="*) ;;
      *) export NIX_CONFIG="${NIX_CONFIG:-}${NIX_CONFIG:+
}access-tokens = github.com=$token" ;;
    esac
  fi
}

nix_common_flags() {
  printf '%s\n' --accept-flake-config --extra-experimental-features 'nix-command flakes' --option fallback true
  [ "${NIX_SUPPRESS_DIRTY_WARNING:-false}" = true ] && printf '%s\n' --no-warn-dirty
}

load_nix_overlay_environment() {
  if [ -z "${MAISON_INVENTORY:-}" ]; then
    local maison_root="${MISE_PROJECT_ROOT:-$PWD}"
    if [ -f "$maison_root/.mise/lib/overlay.sh" ]; then
      # shellcheck source=.mise/lib/overlay.sh
      source "$maison_root/.mise/lib/overlay.sh"
      load_maison_overlay_environment "$maison_root"
    fi
  fi
}

nix_overlay_path() {
  local maison_root="${MISE_PROJECT_ROOT:-$PWD}" inventory_path
  if [ -n "${MAISON_OVERLAY_PATH:-}" ]; then
    printf '%s\n' "$MAISON_OVERLAY_PATH"
    return
  fi
  inventory_path="${MAISON_INVENTORY:-}"
  if [ -n "$inventory_path" ] && [ "$inventory_path" != "$maison_root/inventory.toml" ]; then
    (cd "$(dirname "$inventory_path")" && pwd -P)
    return
  fi
  # The public flake's path input must be overridden to the current checkout.
  # Otherwise --no-update-lock-file rejects any source change since the path
  # hash was recorded in flake.lock, which makes clean CI checkouts fail.
  printf '%s\n' "$maison_root"
}

nix_overlay_args() {
  local overlay_path
  overlay_path="$(nix_overlay_path)"
  [ -n "$overlay_path" ] || return 0
  printf '%s\n' --override-input overlay "path:$overlay_path"
}

nix_command() {
  load_nix_overlay_environment
  local flags=() overlay_args=() flag
  while IFS= read -r flag; do flags+=("$flag"); done < <(nix_common_flags)
  while IFS= read -r flag; do overlay_args+=("$flag"); done < <(nix_overlay_args)
  case "${1:-}" in
    build | eval | fmt | run)
      local subcommand="$1"
      shift
      nix "${flags[@]}" "$subcommand" "${overlay_args[@]}" "$@"
      ;;
    *) nix "${flags[@]}" "$@" "${overlay_args[@]}" ;;
  esac
}

ensure_nh() {
  if command -v nh > /dev/null 2>&1; then
    printf '%s\n' "$(command -v nh)"
  else
    printf '%s\n' "nix-run"
  fi
}

run_nh() {
  load_nix_overlay_environment
  local nix_config="${NIX_CONFIG:-}" args=("$@") overlay_path
  nix_config="${nix_config}${nix_config:+
}accept-flake-config = true"
  overlay_path="$(nix_overlay_path)"
  if [ -n "$overlay_path" ]; then
    args+=(-- --override-input overlay "path:$overlay_path")
  fi

  (
    export NIX_CONFIG="$nix_config"
    if command -v nh > /dev/null 2>&1; then
      nh "${args[@]}"
    else
      nix_command run .#nh -- "${args[@]}"
    fi
  )
}

prepare_darwin_activation() {
  if [ ! -f /etc/nix/nix.conf ] && [ -f /etc/nix/nix.conf.before-nix-darwin ]; then
    log_info "Restoring /etc/nix/nix.conf for the nix-darwin adoption preflight"
    sudo cp /etc/nix/nix.conf.before-nix-darwin /etc/nix/nix.conf
    sudo launchctl kickstart -k system/org.nixos.nix-daemon
    sleep 2
  fi
  if [ -f /etc/nix/nix.conf ] && ! grep -qF nix-darwin /etc/nix/nix.conf 2> /dev/null; then
    log_info "Moving unmanaged /etc/nix/nix.conf aside for nix-darwin"
    sudo mv /etc/nix/nix.conf /etc/nix/nix.conf.before-nix-darwin
  fi
  if [ ! -e /run/current-system/darwin-version ] && [ -f /etc/nix/nix.custom.conf ]; then
    log_info "Moving unmanaged /etc/nix/nix.custom.conf aside for nix-darwin"
    sudo mv /etc/nix/nix.custom.conf /etc/nix/nix.custom.conf.before-nix-darwin
  fi
}

system_profile_for_current_os() {
  case "$(uname -s)" in
    Darwin) printf '%s\n' /nix/var/nix/profiles/system ;;
    Linux) printf '%s\n' /nix/var/nix/profiles/system-manager-profiles/system-manager ;;
    *) return 1 ;;
  esac
}
