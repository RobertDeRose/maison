#!/usr/bin/env bash

wait_for_nix_daemon() {
  for _i in $(seq 1 30); do
    [ -S /nix/var/nix/daemon-socket/socket ] && return 0
    sleep 1
  done
  return 1
}

bootstrap_manifest_path() {
  printf '%s/bootstrap/artifacts.toml\n' "${MISE_PROJECT_ROOT:-$(repo_root "${BASH_SOURCE[0]}")}"
}

manifest_value() {
  local manifest="$1" artifact="$2" key="$3" system="${4:-}" section
  section="artifacts.$artifact"
  [ -z "$system" ] || section="artifacts.$artifact.platforms.$system"
  awk -v section="$section" -v key="$key" '
    $0 ~ "^\\[" section "\\]$" { active = 1; next }
    $0 ~ /^\[/ { active = 0 }
    active && $1 == key { sub(/^[^=]*= */, ""); gsub(/^\"|\"$/, ""); print; exit }
  ' "$manifest"
}

verify_sha256_file() {
  local path="$1" expected="${2#sha256:}" actual=""
  if command -v sha256sum > /dev/null 2>&1; then
    actual="$(sha256sum "$path" | awk '{print $1}')"
  elif command -v shasum > /dev/null 2>&1; then
    actual="$(shasum -a 256 "$path" | awk '{print $1}')"
  else
    die "sha256 verification requires sha256sum or shasum"
    return 1
  fi
  [ "$actual" = "$expected" ] || die "checksum mismatch for $path: expected sha256:$expected, got sha256:$actual"
}

fetch_verified_bootstrap_artifact() {
  local artifact="$1" destination="$2" manifest system url sha
  manifest="$(bootstrap_manifest_path)"
  system="$(current_system)"
  url="$(manifest_value "$manifest" "$artifact" url "$system")"
  sha="$(manifest_value "$manifest" "$artifact" sha256 "$system")"
  [ -n "$url" ] || die "missing bootstrap artifact URL for $artifact on $system"
  [ -n "$sha" ] || die "missing bootstrap artifact checksum for $artifact on $system"
  curl -fsSL "$url" -o "$destination"
  verify_sha256_file "$destination" "$sha"
}

install_mise_if_missing() {
  local temp_dir artifact
  if command -v mise > /dev/null 2>&1; then
    return 0
  fi
  if [ -x "$HOME/.local/bin/mise" ]; then
    export PATH="$HOME/.local/bin:$PATH"
    command -v mise > /dev/null 2>&1 && return 0
  fi
  log_info "Installing verified mise"
  temp_dir="$(mktemp -d)"
  artifact="$temp_dir/mise"
  fetch_verified_bootstrap_artifact mise "$artifact"
  chmod 0755 "$artifact"
  mkdir -p "$HOME/.local/bin"
  cp "$artifact" "$HOME/.local/bin/mise"
  rm -rf "$temp_dir"
  export PATH="$HOME/.local/bin:$PATH"
}

verify_nix() {
  if ! command -v nix > /dev/null 2>&1 && [ -f /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh ]; then
    set +u
    # shellcheck disable=SC1091
    . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
    set -u
  fi
  command -v nix > /dev/null 2>&1 && nix --version > /dev/null
}

install_nix_or_lix_if_missing() {
  local os arch installer_rc=0 extra_conf
  if verify_nix; then
    log_info "Nix is already installed"
    return 0
  fi

  os="$(current_os)"
  arch="$(current_arch)"
  export NIX_INSTALLER_NO_CONFIRM=true
  export NIX_INSTALLER_ENABLE_FLAKES=true
  extra_conf="trusted-users = root $(id -un)
fallback = true
extra-substituters = https://cache.nixos.org https://nix-community.cachix.org https://cache.numtide.com
extra-trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs= niks3.numtide.com-1:DTx8wZduET09hRmMtKdQDxNNthLQETkc/yaX7M4qK0g="
  if [ -n "${NIX_CONFIG_EXTRA_SUBSTITUTERS:-}" ]; then
    extra_conf="$extra_conf
extra-substituters = ${NIX_CONFIG_EXTRA_SUBSTITUTERS}"
  fi
  if [ "${NIX_INSTALLER_NO_SANDBOX:-false}" = true ]; then
    extra_conf="$extra_conf
sandbox = false"
  fi
  export NIX_INSTALLER_EXTRA_CONF="$extra_conf"

  if [ "$os" = darwin ]; then
    export NIX_INSTALLER_SSL_CERT_FILE=/etc/ssl/cert.pem
  fi

  if [ "$os" = darwin ] && [ "$arch" != aarch64 ]; then
    die "Maison supports Apple Silicon macOS only"
    return 1
  fi

  log_info "Installing verified Lix"
  local temp_dir installer
  temp_dir="$(mktemp -d)"
  installer="$temp_dir/lix-installer"
  fetch_verified_bootstrap_artifact lix "$installer"
  chmod 0755 "$installer"
  "$installer" install || installer_rc=$?
  rm -rf "$temp_dir"
  if [ "$installer_rc" -ne 0 ]; then
    log_warn "Lix installer exited with status $installer_rc; verifying daemon readiness"
  fi

  wait_for_nix_daemon || log_warn "Nix daemon socket did not appear within the initial wait window"
  verify_nix || die "Nix/Lix installation completed but the nix command is not functional"
}

ensure_github_auth() {
  local token=""
  token="$(mise token github --raw 2> /dev/null || true)"
  if [ -z "$token" ] && command -v gh > /dev/null 2>&1; then
    token="$(gh auth token 2> /dev/null || true)"
  fi
  [ -z "$token" ] || return 0
  if is_ci; then
    die "GitHub authentication is unavailable in CI; provide GITHUB_TOKEN"
  fi
  log_info "Configuring GitHub authentication"
  mise run --skip-tools github:auth
}
