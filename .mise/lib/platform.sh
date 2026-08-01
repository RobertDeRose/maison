#!/usr/bin/env bash

current_os() {
  case "$(uname -s)" in
    Darwin) printf '%s\n' darwin ;;
    Linux) printf '%s\n' linux ;;
    *) return 1 ;;
  esac
}

current_arch() {
  case "$(uname -m)" in
    arm64 | aarch64) printf '%s\n' aarch64 ;;
    x86_64 | amd64) printf '%s\n' x86_64 ;;
    *) return 1 ;;
  esac
}

current_system() {
  printf '%s-%s\n' "$(current_arch)" "$(current_os)"
}

current_hostname() {
  hostname -s
}

current_user() {
  id -un
}

home_directory_for_user() {
  local username="$1" home=""
  if command -v getent > /dev/null 2>&1; then
    home="$(getent passwd "$username" 2> /dev/null | awk -F: 'NR == 1 { print $6 }')"
  elif [ "$(uname -s)" = "Darwin" ] && command -v dscl > /dev/null 2>&1; then
    home="$(dscl . -read "/Users/$username" NFSHomeDirectory 2> /dev/null | awk '{ print $2 }')"
  fi
  [ -n "$home" ] || home="${HOME:-/home/$username}"
  printf '%s\n' "$home"
}

is_supported_system() {
  case "$1" in
    aarch64-darwin | aarch64-linux | x86_64-linux) return 0 ;;
    *) return 1 ;;
  esac
}
