#!/usr/bin/env bash

MAISON_LUME_VERSION="0.5.1"
# shellcheck disable=SC2034 # sourced constants are consumed by task scripts
MAISON_LUME_RELEASE="lume-v0.5.1"
# shellcheck disable=SC2034 # sourced constants are consumed by task scripts
MAISON_LUME_ARCHIVE="lume-0.5.1-darwin-arm64.tar.gz"
# shellcheck disable=SC2034 # sourced constants are consumed by task scripts
MAISON_LUME_URL="https://github.com/trycua/cua/releases/download/lume-v0.5.1/lume-0.5.1-darwin-arm64.tar.gz"
# shellcheck disable=SC2034 # sourced constants are consumed by task scripts
MAISON_LUME_SHA256="7f10cfbe66a800f98a5db88129f7dc024600fcdc139e0be124845bc7a3dc1359"

maison_lume_data_root() {
  local data_home="${XDG_DATA_HOME:-${HOME:-}}"
  [ -n "$data_home" ] || die "HOME or XDG_DATA_HOME is required for the Lume installation"
  printf '%s\n' "$data_home/maison/lume/$MAISON_LUME_VERSION"
}

maison_lume_bin() {
  printf '%s/lume\n' "$(maison_lume_data_root)"
}

maison_lume_lock_dir() {
  local state_home="${XDG_STATE_HOME:-${HOME:-}}"
  [ -n "$state_home" ] || die "HOME or XDG_STATE_HOME is required for the Lume installation lock"
  printf '%s/maison/lume/.%s.install.lock\n' "$state_home" "$MAISON_LUME_VERSION"
}
