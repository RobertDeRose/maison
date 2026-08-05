#!/usr/bin/env bash
# Apply mise bootstrap packages and repair a narrowly scoped Docker Desktop
# ownership handoff when an existing Homebrew completion symlink blocks the
# built-in brew-cask installer.
set -euo pipefail

removed_targets=()
removed_links=()
handoff_pending=false

run_packages() {
  local output_file="$1"
  shift

  # Capture mise's structured log without piping stderr. mise only permits
  # passworded sudo when stderr is attached to a terminal; piping through tee
  # made an interactive `maison apply` appear non-interactive precisely when a
  # cask needed to update a root-owned artifact such as /usr/local/bin/docker.
  : > "$output_file"
  set +e
  MISE_LOG_FILE="$output_file" MISE_LOG_FILE_LEVEL=info \
    mise bootstrap packages apply --yes "$@"
  local status=$?
  set -e
  return "$status"
}

canonical_path() {
  local path="$1" link directory base count=0

  # Resolve the final symlink ourselves because macOS does not provide
  # readlink -f. Physical directory traversal still resolves symlinked parent
  # components without requiring Python during first-run package bootstrap.
  while [ -L "$path" ]; do
    count=$((count + 1))
    [ "$count" -le 16 ] || return 1
    link="$(readlink "$path")" || return 1
    case "$link" in
      /*) path="$link" ;;
      *) path="$(dirname "$path")/$link" ;;
    esac
  done

  directory="$(dirname "$path")"
  base="$(basename "$path")"
  [ -d "$directory" ] || return 1
  directory="$(cd -P "$directory" && pwd -P)" || return 1
  printf '%s/%s\n' "$directory" "$base"
}

reconcile_docker_completion_links() {
  local prefix="${MAISON_HOMEBREW_PREFIX:-/opt/homebrew}"
  local docker_app="${MAISON_DOCKER_APP:-/Applications/Docker.app}"
  local removed=false target source expected expected_path mapping raw_link
  local -a mappings=(
    "etc/bash_completion.d/docker|Contents/Resources/etc/docker.bash-completion"
    "etc/bash_completion.d/docker-compose|Contents/Resources/etc/docker-compose.bash-completion"
    "share/fish/vendor_completions.d/docker.fish|Contents/Resources/etc/docker.fish-completion"
    "share/fish/vendor_completions.d/docker-compose.fish|Contents/Resources/etc/docker-compose.fish-completion"
    "share/zsh/site-functions/_docker|Contents/Resources/etc/docker.zsh-completion"
    "share/zsh/site-functions/_docker-compose|Contents/Resources/etc/docker-compose.zsh-completion"
  )

  for mapping in "${mappings[@]}"; do
    target="$prefix/${mapping%%|*}"
    expected_path="$docker_app/${mapping#*|}"
    [ -L "$target" ] || continue
    [ -f "$expected_path" ] || continue
    source="$(canonical_path "$target")" || continue
    expected="$(canonical_path "$expected_path")" || continue
    [ "$source" = "$expected" ] || continue
    raw_link="$(readlink "$target")" || continue
    printf 'maison: removing unmanaged Docker Desktop completion link %s before retry\n' "$target" >&2
    rm -f "$target"
    removed_targets+=("$target")
    removed_links+=("$raw_link")
    removed=true
  done

  [ "$removed" = true ]
}

restore_docker_completion_links() {
  local index target
  for ((index = 0; index < ${#removed_targets[@]}; index++)); do
    target="${removed_targets[$index]}"
    if [ ! -e "$target" ] && [ ! -L "$target" ]; then
      ln -s "${removed_links[$index]}" "$target" || true
    fi
  done
}

configured_packages_without_docker() {
  local destination="$1"
  local config_root="${MAISON_CONSUMER_ROOT:-}" config_dir platform_name architecture
  local -a config_paths
  [ -n "$config_root" ] || {
    printf 'maison: MAISON_CONSUMER_ROOT is required for Docker Desktop fallback\n' >&2
    return 1
  }
  config_dir="$config_root/config/mise"
  [ -f "$config_dir/config.toml" ] || {
    printf 'maison: missing active mise package configuration at %s\n' "$config_dir/config.toml" >&2
    return 1
  }

  platform_name="${MAISON_PLATFORM:-$(uname -s)}"
  architecture="${MAISON_ARCH:-$(uname -m)}"
  config_paths=("$config_dir/config.toml")
  case "$platform_name" in
    Darwin)
      config_paths+=("$config_dir/config.macos.toml")
      case "$architecture" in
        arm64 | aarch64) config_paths+=("$config_dir/config.macos-arm64.toml") ;;
        x86_64 | amd64) config_paths+=("$config_dir/config.macos-x64.toml") ;;
      esac
      ;;
    Linux)
      config_paths+=("$config_dir/config.linux.toml")
      case "$architecture" in
        arm64 | aarch64) config_paths+=("$config_dir/config.linux-arm64.toml") ;;
        x86_64 | amd64) config_paths+=("$config_dir/config.linux-x64.toml") ;;
      esac
      ;;
  esac

  python3 - "${config_paths[@]}" > "$destination" <<'PY'
from pathlib import Path
import sys
import tomllib

packages: set[str] = set()
for path in map(Path, sys.argv[1:]):
    if path.is_file():
        with path.open("rb") as handle:
            packages.update(tomllib.load(handle).get("bootstrap", {}).get("packages", {}))
packages.discard("brew-cask:docker-desktop")
for package in sorted(packages):
    print(package)
PY
}

ensure_docker_kubectl_link() {
  local docker_app="${MAISON_DOCKER_APP:-/Applications/Docker.app}"
  local source="$docker_app/Contents/Resources/bin/kubectl"
  local target="${MAISON_DOCKER_KUBECTL_TARGET:-/usr/local/bin/kubectl}"
  local sudo_bin="${MAISON_SUDO_BIN:-sudo}"

  [ ! -e "$target" ] && [ ! -L "$target" ] || return 0
  [ -f "$source" ] || {
    printf 'maison: Docker Desktop did not provide %s\n' "$source" >&2
    return 1
  }

  if mkdir -p "$(dirname "$target")" 2> /dev/null && ln -s "$source" "$target" 2> /dev/null; then
    return 0
  fi
  [ ! -e "$target" ] && [ ! -L "$target" ] || return 0
  command -v "$sudo_bin" > /dev/null 2>&1 || return 1
  "$sudo_bin" mkdir -p "$(dirname "$target")"
  "$sudo_bin" ln -s "$source" "$target"
}

converge_docker_desktop_with_homebrew() {
  local brew_bin="${MAISON_BREW_BIN:-brew}" outdated
  command -v "$brew_bin" > /dev/null 2>&1 || {
    printf 'maison: Homebrew is required for the Docker Desktop compatibility fallback\n' >&2
    return 1
  }

  if "$brew_bin" list --cask docker-desktop > /dev/null 2>&1; then
    outdated="$("$brew_bin" outdated --cask --greedy --quiet docker-desktop)" || return
    if printf '%s\n' "$outdated" | grep -Fxq docker-desktop; then
      "$brew_bin" upgrade --cask docker-desktop
    fi
  else
    "$brew_bin" install --cask docker-desktop
  fi
  ensure_docker_kubectl_link
}

prepare_docker_privileges() {
  local sudo_bin="${MAISON_SUDO_BIN:-sudo}"

  # Docker Desktop installs command links beneath root-owned /usr/local/bin.
  # Authenticate before mise redraws its cask progress display so a password
  # prompt is visible and the subsequent artifact transaction uses sudo's
  # credential cache instead of appearing to hang behind the progress UI.
  [ -t 2 ] || return 0
  command -v "$sudo_bin" > /dev/null 2>&1 || return 0
  printf 'maison: Docker Desktop needs administrator access for /usr/local/bin links\n' >&2
  "$sudo_bin" -v
}

output_file="$(mktemp "${TMPDIR:-/tmp}/maison-packages.XXXXXX")"
remaining_packages_file="$output_file.remaining"
# Invoked indirectly by the EXIT trap below.
# shellcheck disable=SC2329
cleanup() {
  local status=$?
  trap - EXIT HUP INT TERM
  if [ "$handoff_pending" = true ]; then
    restore_docker_completion_links
  fi
  rm -f "$output_file" "$remaining_packages_file"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

if run_packages "$output_file" "$@"; then
  exit 0
else
  status=$?
fi

if grep -Fq "brew-cask:docker-desktop: unsupported postflight_steps step type symlink" "$output_file"; then
  prepare_docker_privileges || exit "$?"
  converge_docker_desktop_with_homebrew || exit "$?"
  configured_packages_without_docker "$remaining_packages_file" || exit "$?"
  remaining_packages=()
  while IFS= read -r package; do
    [ -z "$package" ] || remaining_packages+=("$package")
  done < "$remaining_packages_file"
  if [ "${#remaining_packages[@]}" -eq 0 ]; then
    exit 0
  fi
  printf 'maison: retrying remaining package convergence after Docker Desktop compatibility fallback\n' >&2
  run_packages "$output_file" "${remaining_packages[@]}"
  exit "$?"
fi

if grep -Fq "not owned by cask 'docker-desktop'" "$output_file" &&
  grep -Fq "completion target '" "$output_file" &&
  reconcile_docker_completion_links; then
  handoff_pending=true
  if prepare_docker_privileges; then
    :
  else
    status=$?
    restore_docker_completion_links
    handoff_pending=false
    exit "$status"
  fi
  printf 'maison: retrying package convergence after Docker Desktop completion handoff\n' >&2
  if run_packages "$output_file" "$@"; then
    handoff_pending=false
    exit 0
  else
    status=$?
    restore_docker_completion_links
    handoff_pending=false
    exit "$status"
  fi
fi

exit "$status"
