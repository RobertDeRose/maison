#!/usr/bin/env bash
# Install Maison and hand machine setup to a consumer repository.
#
# Usage:
#   ./bootstrap.sh [--host HOST] [--consumer PATH] [--repo OWNER/REPO|URL|PATH] [--ref REF]
#   Run from the consumer checkout or pass MAISON_CONSUMER_ROOT explicitly.
#   Download this file from a reviewed release, verify it against the published checksum, then run:
#     bash bootstrap.sh --consumer "$HOME/src/terroir" --repo RobertDeRose/maison --ref v0.1.1

set -euo pipefail

show_help() {
  cat << 'HELP'
Install Maison and hand machine setup to a consumer repository.

Usage:
  bootstrap.sh [--host HOST] [--consumer PATH] [--repo OWNER/REPO|URL|PATH] [--ref REF]
  bootstrap.sh [HOST]

Options:
  --host HOST       Consumer inventory host; defaults to the short local hostname.
  --consumer PATH   Consumer Git repository with flake.nix, flake.lock, and inventory.toml.
  --repo REPO       GitHub owner/repository, Git URL, or local Maison repository path.
  --ref REF         Maison branch, tag, or immutable commit; defaults to main.
  -h, --help        Show this help text.

Environment:
  MAISON_CONSUMER_ROOT  Consumer repository path; equivalent to --consumer.
  MAISON_REQUIRE_CONSUMER  Fail instead of deferring when no consumer is selected.
HELP
}

log() { printf '==> %s\n' "$*"; }
bootstrap_die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

host="$(hostname -s)"
repo="${REPO:-RobertDeRose/maison}"
ref="${REF:-${BRANCH:-main}}"
profiles="${PROFILES:-}"
consumer="${MAISON_CONSUMER_ROOT:-${MAISON_REPOSITORY:-${MAISON_REPO:-}}}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      [ "$#" -ge 2 ] || bootstrap_die "--host requires a value"
      host="$2"
      shift 2
      ;;
    --consumer | --repository)
      [ "$#" -ge 2 ] || bootstrap_die "--consumer requires a value"
      consumer="$2"
      shift 2
      ;;
    --repo)
      [ "$#" -ge 2 ] || bootstrap_die "--repo requires a value"
      repo="$2"
      shift 2
      ;;
    --ref)
      [ "$#" -ge 2 ] || bootstrap_die "--ref requires a value"
      ref="$2"
      shift 2
      ;;
    --profiles)
      [ "$#" -ge 2 ] || bootstrap_die "--profiles requires a value"
      profiles="$2"
      shift 2
      ;;
    -h | --help)
      show_help
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*) bootstrap_die "unknown option: $1" ;;
    *)
      # Preserve the original positional hostname interface.
      host="$1"
      shift
      ;;
  esac
done
[ "$#" -eq 0 ] || bootstrap_die "unexpected argument: $1"

run_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    command -v sudo > /dev/null 2>&1 || bootstrap_die "sudo is required to install platform prerequisites"
    sudo "$@"
  fi
}

install_linux_prerequisites() {
  command -v git > /dev/null 2>&1 && command -v curl > /dev/null 2>&1 && return 0
  log "Installing git and curl"
  if command -v apt-get > /dev/null 2>&1; then
    run_root apt-get update -qq
    run_root apt-get install -y -qq git curl ca-certificates
  elif command -v dnf > /dev/null 2>&1; then
    run_root dnf install -y git curl ca-certificates
  elif command -v yum > /dev/null 2>&1; then
    run_root yum install -y git curl ca-certificates
  elif command -v pacman > /dev/null 2>&1; then
    run_root pacman -Sy --needed --noconfirm git curl ca-certificates
  elif command -v zypper > /dev/null 2>&1; then
    run_root zypper --non-interactive install git curl ca-certificates
  else
    bootstrap_die "install git and curl, then rerun bootstrap.sh"
  fi
}

install_macos_prerequisites() {
  command -v xcode-select > /dev/null 2>&1 || bootstrap_die "xcode-select is unavailable"
  if xcode-select -p > /dev/null 2>&1; then
    return 0
  fi
  log "Installing Xcode Command Line Tools"
  marker=/tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress
  touch "$marker"
  product="$(softwareupdate -l 2> /dev/null | awk '/\*.*Command Line/ { sub(/^[^C]*/, ""); value=$0 } END { print value }')"
  rm -f "$marker"
  [ -n "$product" ] || bootstrap_die "no Command Line Tools update was found; run 'xcode-select --install'"
  run_root softwareupdate -i "$product" --verbose
}

is_maison_checkout() {
  local path="$1"
  [ -f "$path/mise.toml" ] && [ -f "$path/flake.nix" ] && [ -d "$path/.mise/tasks" ]
}

is_consumer_checkout() {
  local path="$1"
  [ -d "$path" ] && [ -f "$path/flake.nix" ] && [ -f "$path/flake.lock" ] && [ -f "$path/inventory.toml" ]
}

print_consumer_setup_help() {
  log "Maison CLI installed at $HOME/.local/bin/maison"
  printf '%s\n' "No consumer repository was selected, so Nix and user activation were skipped."
  printf '%s\n' "Set MAISON_CONSUMER_ROOT or rerun bootstrap with --consumer /path/to/consumer."
  printf '%s\n' "The consumer must own flake.nix, flake.lock, inventory.toml, hosts, and user configuration."
  printf '%s\n' "Read: $repo_root/docs/src/reference/consumer.md"
}

case "$(uname -s)" in
  Darwin)
    case "$(uname -m)" in
      arm64 | aarch64) ;;
      *) bootstrap_die "Maison supports Apple Silicon macOS only" ;;
    esac
    install_macos_prerequisites
    ;;
  Linux)
    unset LC_ALL
    export LANG=C.UTF-8
    export LC_CTYPE=C.UTF-8
    install_linux_prerequisites
    ;;
  *) bootstrap_die "unsupported operating system: $(uname -s)" ;;
esac
command -v git > /dev/null 2>&1 || bootstrap_die "git is unavailable"
command -v curl > /dev/null 2>&1 || bootstrap_die "curl is unavailable"

case "$repo" in
  *://* | git@* | /* | ./* | ../*) repo_url="$repo" ;;
  *) repo_url="https://github.com/${repo%.git}.git" ;;
esac
repo_root=""
if git_root="$(git rev-parse --show-toplevel 2> /dev/null)" && is_maison_checkout "$git_root"; then
  repo_root="$git_root"
  if [ -z "$consumer" ] && [ "$git_root" != "$(pwd -P)" ] && is_consumer_checkout "$(pwd -P)"; then
    consumer="$(pwd -P)"
  fi
elif [ -n "${MAISON_HOME:-}" ]; then
  repo_root="$MAISON_HOME"
elif [ -n "${NIX_CONFIG_DIR:-}" ]; then
  # Compatibility with installations created before the Maison rename.
  repo_root="$NIX_CONFIG_DIR"
else
  repo_root="$HOME/.maison"
fi

if [ ! -d "$repo_root/.git" ]; then
  [ ! -e "$repo_root" ] || bootstrap_die "$repo_root exists but is not a Git repository"
  log "Cloning $repo_url at $ref into $repo_root"
  if [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then
    git clone --no-checkout "$repo_url" "$repo_root"
    git -C "$repo_root" checkout --detach "$ref"
  else
    git clone --branch "$ref" --single-branch "$repo_url" "$repo_root"
  fi
elif ! is_maison_checkout "$repo_root"; then
  bootstrap_die "$repo_root does not look like Maison"
else
  log "Using Maison repository at $repo_root"
fi

if [ -z "$consumer" ] &&
  git_root="$(git -C "$PWD" rev-parse --show-toplevel 2> /dev/null)" &&
  [ "$git_root" != "$repo_root" ] &&
  is_consumer_checkout "$git_root"; then
  consumer="$git_root"
fi
if [ -n "$consumer" ]; then
  consumer="$(cd "$consumer" 2> /dev/null && pwd -P)" || bootstrap_die "consumer repository is unavailable: $consumer"
  is_consumer_checkout "$consumer" ||
    bootstrap_die "consumer repository must contain flake.nix, flake.lock, and inventory.toml: $consumer"
fi

cd "$repo_root"
export MAISON_HOME="$repo_root"
export MISE_TRUSTED_CONFIG_PATHS="$repo_root${MISE_TRUSTED_CONFIG_PATHS:+:$MISE_TRUSTED_CONFIG_PATHS}"

# Bootstrap only the executors required by the two ownership layers: mise and Nix/Lix.
# shellcheck source=.mise/lib/common.sh
source "$repo_root/.mise/lib/common.sh"
# shellcheck source=.mise/lib/platform.sh
source "$repo_root/.mise/lib/platform.sh"
# shellcheck source=.mise/lib/bootstrap.sh
source "$repo_root/.mise/lib/bootstrap.sh"
install_mise_if_missing
command -v mise > /dev/null 2>&1 || bootstrap_die "mise installation did not place the executable on PATH"

log "Installing Maison command"
mkdir -p "$HOME/.local/bin"
ln -sfn "$repo_root/bin/maison" "$HOME/.local/bin/maison"

log "Trusting Maison project configuration"
mise trust "$repo_root/mise.toml" > /dev/null

if [ -z "$consumer" ]; then
  if [ "${MAISON_REQUIRE_CONSUMER:-false}" = true ] || [ ! -t 0 ]; then
    bootstrap_die "a consumer repository is required; pass --consumer or set MAISON_CONSUMER_ROOT"
  fi
  print_consumer_setup_help
  exit 0
fi

export MAISON_CONSUMER_ROOT="$consumer"
install_nix_or_lix_if_missing

log "Handing off to Maison for consumer host $host"
bootstrap_args=(--host "$host" --consumer "$consumer")
if [ -n "$profiles" ]; then
  log "Ignoring legacy --profiles=$profiles; profiles select only Nix system modules in the consumer inventory"
fi
exec mise exec --locked python -- mise run --skip-tools bootstrap -- "${bootstrap_args[@]}"
