#!/usr/bin/env bash
# Provider-neutral fnox orchestration for consumer-owned runtime secrets.

maison_fnox_framework_root() {
  if [ -n "${MAISON_HOME:-}" ]; then
    (cd "$MAISON_HOME" && pwd -P)
    return
  fi
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P
}

maison_fnox_config_path() {
  local root="$1"
  local config="${MAISON_FNOX_CONFIG:-$root/fnox.toml}"
  if [ -f "$config" ]; then
    printf '%s\n' "$config"
    return 0
  fi
  return 1
}

maison_fnox_validator() {
  local framework_root
  framework_root="$(maison_fnox_framework_root)"
  printf '%s\n' "$framework_root/.mise/lib/fnox.py"
}

maison_fnox_validate_config() {
  local root="$1" config
  config="$(maison_fnox_config_path "$root")" || return 0
  python3 "$(maison_fnox_validator)" --file "$config" validate >/dev/null
}

maison_fnox_materialize_config() {
  local config="$1" runtime_dir local_override
  runtime_dir="$(mktemp -d "${TMPDIR:-/tmp}/maison-fnox-runtime.XXXXXX")" || return 1
  chmod 700 "$runtime_dir"
  if ! cp -- "$config" "$runtime_dir/fnox.toml"; then
    rm -rf -- "$runtime_dir"
    return 1
  fi
  chmod 600 "$runtime_dir/fnox.toml"
  local_override="$(dirname "$config")/fnox.local.toml"
  if [ -f "$local_override" ]; then
    if ! cp -- "$local_override" "$runtime_dir/fnox.local.toml"; then
      rm -rf -- "$runtime_dir"
      return 1
    fi
    chmod 600 "$runtime_dir/fnox.local.toml"
  fi
  printf '%s\n' "$runtime_dir"
}

maison_fnox_logical_secrets() {
  local root="$1" config
  config="$(maison_fnox_config_path "$root")" || return 0
  python3 "$(maison_fnox_validator)" --file "$config" list-secrets
}

maison_fnox_preflight() {
  local root="$1" config output status logical_secrets config_dir runtime_config
  [ "${MAISON_FNOX_PREFLIGHT_DONE:-false}" = true ] && return 0
  config="$(maison_fnox_config_path "$root")" || {
    export MAISON_FNOX_PREFLIGHT_DONE=true
    return 0
  }

  if ! output="$(python3 "$(maison_fnox_validator)" --file "$config" validate 2>&1)"; then
    printf 'error: invalid fnox contract at %s\n' "$config" >&2
    printf '%s\n' "$output" >&2
    return 1
  fi

  if ! command -v fnox >/dev/null 2>&1; then
    printf 'error: consumer defines %s but fnox is unavailable\n' "$config" >&2
    printf 'Install fnox through the consumer-selected toolchain before activation.\n' >&2
    return 1
  fi

  local output_file
  output_file="$(mktemp "${TMPDIR:-/tmp}/maison-fnox-check.XXXXXX")"
  config_dir="$(maison_fnox_materialize_config "$config")" || {
    rm -f "$output_file"
    printf 'error: could not materialize fnox configuration owner-only for runtime use\n' >&2
    return 1
  }
  runtime_config="$config_dir/fnox.toml"
  if FNOX_CONFIG_DIR="$config_dir" FNOX_IF_MISSING=error FNOX_SHELL_OUTPUT=none fnox -c "$runtime_config" check >"$output_file" 2>&1; then
    rm -f "$output_file"
    rm -rf -- "$config_dir"
    export MAISON_FNOX_PREFLIGHT_DONE=true
    return 0
  else
    status=$?
  fi
  logical_secrets="$(maison_fnox_logical_secrets "$root" || true)"
  rm -f "$output_file"
  rm -rf -- "$config_dir"
  printf 'error: fnox preflight failed before mutation (exit %s)\n' "$status" >&2
  if [ -n "$logical_secrets" ]; then
    printf 'Required logical secrets: %s\n' "$(printf '%s' "$logical_secrets" | paste -sd ', ' -)" >&2
  fi
  printf 'Resolve the required values with the consumer-selected fnox provider and retry.\n' >&2
  printf 'Secret values were not printed.\n' >&2
  return "$status"
}

maison_fnox_has_secret() {
  local root="$1" name="$2" config
  config="$(maison_fnox_config_path "$root")" || return 1
  python3 "$(maison_fnox_validator)" --file "$config" has-secret "$name" >/dev/null
}

maison_fnox_get() {
  local root="$1" name="$2" config value status config_dir runtime_config
  config="$(maison_fnox_config_path "$root")" || {
    printf 'error: no fnox configuration is available for logical secret %s\n' "$name" >&2
    return 1
  }
  [[ "$name" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
    printf 'error: invalid logical fnox secret name: %s\n' "$name" >&2
    return 1
  }
  config_dir="$(maison_fnox_materialize_config "$config")" || {
    printf 'error: could not materialize fnox configuration owner-only for runtime use\n' >&2
    return 1
  }
  runtime_config="$config_dir/fnox.toml"
  if value="$(FNOX_CONFIG_DIR="$config_dir" FNOX_IF_MISSING=error FNOX_SHELL_OUTPUT=none fnox -c "$runtime_config" get "$name" 2>/dev/null)"; then
    :
  else
    status=$?
    rm -rf -- "$config_dir"
    printf 'error: fnox could not resolve logical secret %s at runtime (exit %s)\n' "$name" "$status" >&2
    return "$status"
  fi
  rm -rf -- "$config_dir"
  [ -n "$value" ] || {
    printf 'error: fnox returned no value for logical secret %s\n' "$name" >&2
    return 1
  }
  printf '%s\n' "$value"
}

maison_fnox_exec() {
  local root="$1" config runtime_dir runtime_config status
  shift
  [ "$#" -gt 0 ] || {
    printf 'error: maison_fnox_exec requires a command\n' >&2
    return 2
  }
  config="$(maison_fnox_config_path "$root")" || {
    "$@"
    return
  }
  runtime_dir="$(maison_fnox_materialize_config "$config")" || {
    printf 'error: could not materialize fnox configuration owner-only for runtime use\n' >&2
    return 1
  }
  runtime_config="$runtime_dir/fnox.toml"
  if FNOX_CONFIG_DIR="$runtime_dir" FNOX_IF_MISSING=error FNOX_SHELL_OUTPUT=none fnox -c "$runtime_config" exec -- "$@"; then
    status=0
  else
    status=$?
  fi
  rm -rf -- "$runtime_dir"
  return "$status"
}
