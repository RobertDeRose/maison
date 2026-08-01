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

nix_command() {
  if [ -z "${MAISON_INVENTORY:-}" ]; then
    local maison_root="${MISE_PROJECT_ROOT:-$PWD}"
    if [ -f "$maison_root/.mise/lib/overlay.sh" ]; then
      # shellcheck source=.mise/lib/overlay.sh
      source "$maison_root/.mise/lib/overlay.sh"
      load_maison_overlay_environment "$maison_root"
    fi
  fi
  local flags=() flag impure=()
  while IFS= read -r flag; do flags+=("$flag"); done < <(nix_common_flags)
  if [ -n "${MAISON_INVENTORY:-}" ] && [ "${MAISON_INVENTORY}" != "${MISE_PROJECT_ROOT:-$PWD}/inventory.toml" ]; then
    impure=(--impure)
  fi
  case "${1:-}" in
    build | eval | fmt | run)
      local subcommand="$1"
      shift
      nix "${flags[@]}" "$subcommand" "${impure[@]}" "$@"
      ;;
    *) nix "${flags[@]}" "$@" ;;
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
  local nix_config="${NIX_CONFIG:-}"
  nix_config="${nix_config}${nix_config:+
}accept-flake-config = true"

  (
    export NIX_CONFIG="$nix_config"
    if command -v nh > /dev/null 2>&1; then
      nh "$@"
    else
      nix_command run .#nh -- "$@"
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
