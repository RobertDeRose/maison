#!/usr/bin/env bash
# Install Maison and hand machine setup to its mise-backed bootstrap task.
#
# Usage:
#   ./bootstrap.sh [--host HOST] [--overlay GIT-URL-OR-PATH] [--repo OWNER/REPO|URL|PATH] [--ref REF]
#   Set MAISON_OVERLAY instead of passing --overlay to select an existing private repository.
#   Download this file from a reviewed release, verify it against the published checksum, then run:
#     bash bootstrap.sh --host HOST --overlay GIT-URL-OR-PATH --repo RobertDeRose/maison --ref v0.1.1

set -euo pipefail

show_help() {
  cat << 'HELP'
Install Maison and hand machine setup to its mise-backed bootstrap task.

Usage:
  bootstrap.sh [--host HOST] [--overlay GIT-URL-OR-PATH] [--repo OWNER/REPO|URL|PATH] [--ref REF]
  bootstrap.sh [HOST]

Options:
  --host HOST       Inventory host; defaults to the short local hostname.
  --overlay SOURCE  Existing private overlay Git URL or local repository path.
  --repo REPO       GitHub owner/repository, Git URL, or local repository path.
  --ref REF         Branch, tag, or immutable commit to clone; defaults to main.
  -h, --help        Show this help text.

Environment:
  MAISON_OVERLAY          Existing private overlay Git URL or local repository path.
  MAISON_OVERLAY_HOME     Copier destination; defaults to ${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay.
  MAISON_REQUIRE_OVERLAY  Fail instead of deferring when no overlay is available.
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
overlay="${MAISON_OVERLAY:-${MAISON_OVERLAY_SOURCE:-}}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      [ "$#" -ge 2 ] || bootstrap_die "--host requires a value"
      host="$2"
      shift 2
      ;;
    --overlay)
      [ "$#" -ge 2 ] || bootstrap_die "--overlay requires a value"
      overlay="$2"
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

print_overlay_setup_help() {
  log "Maison CLI installed at $HOME/.local/bin/maison"
  printf '%s\n' "No private overlay was selected, so Nix and user activation were skipped."
  printf '%s\n' "Create an overlay with the Copier template, then rerun bootstrap with --overlay or MAISON_OVERLAY."
  printf '%s\n' "Read: $repo_root/README.md#private-overlay"
  printf '%s\n' "Template: $repo_root/overlay_template"
}

setup_overlay_with_copier() {
  local destination="${MAISON_OVERLAY_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay}" copier_user
  copier_user="$(id -un)"
  [ -e "$destination" ] && [ ! -d "$destination" ] && bootstrap_die "overlay destination is not a directory: $destination"
  mkdir -p "$destination"
  destination="$(cd "$destination" && pwd -P)"
  log "Installing the pinned Copier runner"
  mise install uv
  log "Creating private overlay at $destination"
  copier_env="$(mktemp -d)"
  (
    trap 'rm -rf "$copier_env"' EXIT
    mise exec --locked python -- python -m venv "$copier_env"
    mise exec --locked uv pip install \
      --python "$copier_env/bin/python" \
      --require-hashes \
      --no-cache \
      -r "$repo_root/bootstrap/copier-requirements.txt"
    MAISON_HOME="$repo_root" MAISON_OVERLAY_PATH="$destination" MAISON_HOST="$host" \
      "$copier_env/bin/copier" copy --trust --data "username=$copier_user" \
        "$repo_root/overlay_template" "$destination"
  )
  [ -d "$destination/.git" ] || bootstrap_die "Copier did not initialize the overlay Git repository: $destination"
  overlay="$destination"
}

select_overlay_or_defer() {
  local saved reply
  if [ -n "$overlay" ]; then
    return 0
  fi
  if [ -f "$repo_root/scripts/maison_overlay.py" ]; then
    saved="$(mise exec --locked python -- python "$repo_root/scripts/maison_overlay.py" resolve 2> /dev/null || true)"
    if [ -n "$saved" ]; then
      overlay="$saved"
      return 0
    fi
  fi
  if [ "${MAISON_REQUIRE_OVERLAY:-false}" = true ] && [ ! -t 0 ]; then
    bootstrap_die "overlay source is required in non-interactive mode; pass --overlay or set MAISON_OVERLAY"
  fi
  if [ ! -t 0 ]; then
    print_overlay_setup_help
    return 1
  fi
  printf 'No private overlay selected. Set one up now with Copier? [Y/n] ' >&2
  IFS= read -r reply || reply=n
  case "$reply" in
    "" | y | Y | yes | YES | Yes)
      setup_overlay_with_copier
      return 0
      ;;
    n | N | no | NO | No)
      if [ "${MAISON_REQUIRE_OVERLAY:-false}" = true ]; then
        bootstrap_die "overlay source is required; pass --overlay or set MAISON_OVERLAY"
      fi
      print_overlay_setup_help
      return 1
      ;;
    *)
      bootstrap_die "answer yes or no when choosing whether to create a private overlay"
      ;;
  esac
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
if git_root="$(git rev-parse --show-toplevel 2> /dev/null)" &&
  [ -f "$git_root/mise.toml" ] &&
  [ -f "$git_root/flake.nix" ]; then
  repo_root="$git_root"
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
elif [ ! -f "$repo_root/mise.toml" ] || [ ! -f "$repo_root/flake.nix" ]; then
  bootstrap_die "$repo_root does not look like Maison"
else
  log "Using repository at $repo_root"
fi

cd "$repo_root"
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

log "Trusting repository configuration"
mise trust "$repo_root/mise.toml" > /dev/null

if ! select_overlay_or_defer; then
  exit 0
fi

install_nix_or_lix_if_missing

log "Handing off to Maison for host $host"
bootstrap_args=(--host "$host")
if [ -n "$overlay" ]; then
  bootstrap_args+=(--overlay "$overlay")
fi
if [ -n "$profiles" ]; then
  log "Ignoring legacy --profiles=$profiles; profiles now select only Nix system modules in inventory.toml"
fi
exec mise exec --locked python -- mise run --skip-tools bootstrap -- "${bootstrap_args[@]}"
