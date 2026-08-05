#!/usr/bin/env bash

# shellcheck source=.mise/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
# shellcheck source=.mise/lib/consumer.sh
source "$(dirname "${BASH_SOURCE[0]}")/consumer.sh"

inventory_path() {
  local root="$1"
  printf '%s\n' "$(consumer_inventory_path "$root")"
}

inventory_repo_root() {
  dirname "$(inventory_path "$1")"
}

inventory_cli() {
  local root="$1" inventory framework_root
  shift
  load_maison_consumer_environment "$root"
  inventory="$(inventory_path "$root")"
  framework_root="$(maison_install_root "${BASH_SOURCE[0]}")"
  if command -v python3 > /dev/null 2>&1 && python3 -c 'import tomllib' > /dev/null 2>&1; then
    python3 "$framework_root/.mise/lib/inventory.py" --file "$inventory" --repo-root "$root" "$@"
    return
  fi
  if command -v nix > /dev/null 2>&1; then
    nix run --accept-flake-config "$framework_root#maison-inventory" -- \
      --file "$inventory" --repo-root "$root" "$@"
    return
  fi
  printf 'inventory validation requires Python 3.11+ or Nix/Lix\n' >&2
  return 1
}

require_inventory_file() {
  local root="$1" file
  file="$(inventory_path "$root")"
  if [ ! -f "$file" ]; then
    printf 'inventory.toml is missing at %s\n' "$file" >&2
    return 1
  fi
}

validate_hostname() {
  printf '%s' "$1" | grep -Eq '^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$'
}

validate_username() {
  [ "$1" != root ] && printf '%s' "$1" | grep -Eq '^[a-z_][a-z0-9_-]*$'
}

validate_github_username() {
  printf '%s' "$1" | grep -Eq '^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?$'
}

inventory_hosts() { inventory_cli "$1" list-hosts; }
inventory_host_rows() { inventory_cli "$1" host-table; }
inventory_users() { inventory_cli "$1" list-users; }
inventory_has_host() { inventory_cli "$1" has-host "$2" > /dev/null 2>&1; }
inventory_has_user() { inventory_cli "$1" has-user "$2" > /dev/null 2>&1; }
inventory_host_system() { inventory_cli "$1" host-field "$2" system; }
inventory_host_user() { inventory_cli "$1" host-field "$2" user; }
inventory_host_profiles() { inventory_cli "$1" host-field "$2" profiles; }
inventory_host_username() { inventory_cli "$1" host-field "$2" username; }
inventory_user_field() { inventory_cli "$1" user-field "$2" "$3"; }
inventory_host_feature() { inventory_cli "$1" host-field "$2" "feature.$3"; }
inventory_host_deploy_field() { inventory_cli "$1" host-field "$2" "deploy.$3"; }
inventory_deploy_hostname() { inventory_host_deploy_field "$1" "$2" hostname; }
inventory_deploy_ssh_user() { inventory_host_deploy_field "$1" "$2" ssh_user; }
inventory_deploy_user_ssh_user() { inventory_host_deploy_field "$1" "$2" user_ssh_user; }
inventory_deploy_repo_path() { inventory_host_deploy_field "$1" "$2" repo_path; }

host_platform_class() { inventory_cli "$1" host-field "$2" platform; }

inventory_user_allowed_for_system() {
  local root="$1" user="$2" system="$3" username allow_nonportable
  inventory_has_user "$root" "$user" || return 1
  username="$(inventory_user_field "$root" "$user" username)"
  if validate_username "$username"; then
    return 0
  fi
  allow_nonportable="$(inventory_user_field "$root" "$user" allow_nonportable)"
  [ "$allow_nonportable" = true ] || return 1
  case "$system" in
    *-darwin) return 0 ;;
    *) return 1 ;;
  esac
}

print_available_hosts() {
  local root="$1"
  printf 'Available hosts:\n' >&2
  inventory_hosts "$root" | sed 's/^/  /' >&2
}

require_inventory_host() {
  local root="$1" host="$2"
  if ! inventory_has_host "$root" "$host"; then
    printf 'Host "%s" is not defined in inventory.toml.\n\n' "$host" >&2
    print_available_hosts "$root"
    return 1
  fi
}

validate_host_platform() {
  local root="$1" host="$2" actual="$3" expected
  expected="$(inventory_host_system "$root" "$host")" || return 1
  if [ "$expected" != "$actual" ]; then
    printf 'Host "%s" is configured as %s, but this machine is %s.\n\n' "$host" "$expected" "$actual" >&2
    printf 'Use --host to select another configuration or correct inventory.toml.\n' >&2
    return 1
  fi
}

require_inventory_user_for_host() {
  local root="$1" host="$2" user system username
  user="$(inventory_host_user "$root" "$host")" || return 1
  system="$(inventory_host_system "$root" "$host")" || return 1
  inventory_has_user "$root" "$user" || return 1
  username="$(inventory_host_username "$root" "$host")" || return 1
  inventory_user_allowed_for_system "$root" "$user" "$system" || return 1
  printf '%s\n' "$username"
}
