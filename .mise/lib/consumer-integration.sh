#!/usr/bin/env bash

consumer_integration_maison_ref() {
  local root="$1"

  python3 - "$root/flake.lock" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    locked = json.load(handle)

try:
    node = locked["nodes"]["maison"]["locked"]
except (KeyError, TypeError) as error:
    raise SystemExit("consumer flake.lock is missing nodes.maison.locked") from error
if not isinstance(node, dict):
    raise SystemExit("consumer flake.lock nodes.maison.locked must be an object")

expected = {"type": "github", "owner": "RobertDeRose", "repo": "maison"}
for key, value in expected.items():
    if node.get(key) != value:
        raise SystemExit(f"the locked Maison input must use {key}={value!r}")
revision = node.get("rev", "")
if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
    raise SystemExit("the locked Maison input must use a full immutable revision")
print(revision)
PY
}

consumer_integration_maison_root() {
  local root="$1" ref
  ref="$(consumer_integration_maison_ref "$root")"

  nix eval --impure --raw \
    --expr "(builtins.getFlake \"github:RobertDeRose/maison/$ref\").outPath"
}

consumer_integration_resolve_github_ref() {
  local ref="$1" token="${2:-}" metadata api_url
  if [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then
    printf '%s\n' "$ref"
    return 0
  fi
  [ -n "$token" ] || {
    printf 'error: resolving a Maison branch requires GitHub authentication\n' >&2
    return 1
  }
  case "$ref" in
    '' | *[!A-Za-z0-9._/-]* | */ | */.* | *..* | *'@{'*)
      printf 'error: invalid Maison branch reference: %s\n' "$ref" >&2
      return 1
      ;;
  esac
  api_url="https://api.github.com/repos/RobertDeRose/maison/git/ref/heads/$ref"
  metadata="$(consumer_integration_curl_with_token "$token" \
    --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --header 'Accept: application/vnd.github+json' --url "$api_url")" || return 1
  printf '%s\n' "$metadata" |
    jq -er '.object.sha | select(type == "string" and test("^[0-9a-f]{40}$"))'
}

consumer_integration_require_commands() {
  local command
  for command in container curl git jq mise nix python3 ssh ssh-keygen tar; do
    command -v "$command" >/dev/null 2>&1 || {
      printf 'error: Linux integration tests require %s\n' "$command" >&2
      return 1
    }
  done
}

consumer_integration_require_github_token() {
  local token="${GITHUB_TOKEN:-}"
  if [ -z "$token" ] && command -v gh >/dev/null 2>&1; then
    token="$(gh auth token 2>/dev/null || true)"
  fi
  [ -n "$token" ] || {
    cat >&2 <<'EOF'
error: consumer integration tests require GitHub authentication.

Set GITHUB_TOKEN in the environment or authenticate the GitHub CLI:

  gh auth login

The token is passed through owner-controlled environment or an owner-only
temporary file and is never written to the repository or test logs.
EOF
    return 1
  }
  case "$token" in
    *$'\n'* | *$'\r'* | *'"'*)
      printf 'error: GitHub token contains unsupported control or quote characters\n' >&2
      return 1
      ;;
  esac
  case "$token" in
    *\\*)
      printf 'error: GitHub token contains an unsupported backslash character\n' >&2
      return 1
      ;;
  esac
  printf '%s\n' "$token"
}

consumer_integration_curl_with_token() {
  local token="$1"
  shift
  curl --config - "$@" <<CURL_CONFIG
header = "Authorization: Bearer $token"
CURL_CONFIG
}

consumer_integration_sha256() {
  local path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  else
    printf 'error: checksum verification requires sha256sum or shasum\n' >&2
    return 1
  fi
}

consumer_integration_fetch_verified_url() {
  local url="$1" expected="$2" destination="$3" actual
  [[ "$expected" =~ ^sha256:[0-9a-f]{64}$ ]] || {
    printf 'error: invalid SHA-256 contract for downloaded artifact\n' >&2
    return 1
  }
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 --output "$destination" "$url"
  actual="$(consumer_integration_sha256 "$destination")"
  [ "$actual" = "${expected#sha256:}" ] || {
    printf 'error: checksum mismatch for downloaded artifact (expected %s, got sha256:%s)\n' "$expected" "$actual" >&2
    return 1
  }
}

consumer_integration_fetch_framework_artifact() {
  local framework_root="$1" artifact="$2" system="$3" destination="$4"
  local manifest="$framework_root/bootstrap/artifacts.toml" url expected
  read -r url expected < <(python3 - "$manifest" "$artifact" "$system" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    manifest = tomllib.load(handle)
try:
    artifact = manifest["artifacts"][sys.argv[2]]["platforms"][sys.argv[3]]
    print(artifact["url"], artifact["sha256"])
except (KeyError, TypeError) as error:
    raise SystemExit("missing pinned framework artifact") from error
PY
  )
  [ -n "$url" ] && [ -n "$expected" ] || {
    printf 'error: missing pinned %s artifact for %s\n' "$artifact" "$system" >&2
    return 1
  }
  consumer_integration_fetch_verified_url "$url" "$expected" "$destination"
}

consumer_integration_fetch_bootstrap() {
  local ref="$1" token="$2" destination="$3" metadata blob_sha actual
  case "$ref" in
    '' | *[!A-Za-z0-9._/-]*)
      printf 'error: invalid Maison bootstrap reference: %s\n' "$ref" >&2
      return 1
      ;;
  esac
  local api_url="https://api.github.com/repos/RobertDeRose/maison/contents/bootstrap.sh?ref=$ref"
  local raw_url="https://raw.githubusercontent.com/RobertDeRose/maison/$ref/bootstrap.sh"

  metadata="$(consumer_integration_curl_with_token "$token" \
    --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --header 'Accept: application/vnd.github+json' --url "$api_url")" || return 1
  blob_sha="$(printf '%s' "$metadata" | jq -er '.sha | select(type == "string" and test("^[0-9a-f]{40}$"))')" || {
    printf 'error: GitHub did not return a valid bootstrap.sh blob identity at the locked revision\n' >&2
    return 1
  }
  consumer_integration_curl_with_token "$token" \
    --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --output "$destination" --url "$raw_url"
  actual="$(git hash-object "$destination")"
  [ "$actual" = "$blob_sha" ] || {
    printf 'error: bootstrap.sh blob mismatch: expected %s, got %s\n' "$blob_sha" "$actual" >&2
    return 1
  }
}

consumer_integration_build_image() {
  local maison_root="$1" image="${MAISON_TEST_IMAGE:-local/maison-test-linux:24.04}"

  if container image inspect "$image" >/dev/null 2>&1; then
    printf "==> Reusing Apple Container image '%s'\n" "$image"
    return 0
  fi

  printf "==> Building Apple Container image '%s'\n" "$image"
  container build \
    --file "$maison_root/test/Containerfile" \
    --tag "$image" \
    "$maison_root"
}

consumer_integration_stage() {
  local root="$1" stage="$2" host="$3" profiles="$4" deploy_ip="${5:-}"
  local stage_parent stage_name stage_candidate

  [[ "$host" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$ ]] || {
    printf 'error: invalid temporary inventory host: %s\n' "$host" >&2
    return 1
  }
  if [ -n "$deploy_ip" ]; then
    python3 - "$deploy_ip" <<'PY'
import ipaddress
import sys

try:
    ipaddress.IPv4Address(sys.argv[1])
except ValueError as error:
    raise SystemExit(f"invalid temporary deployment address: {sys.argv[1]}") from error
PY
  fi
  case "$profiles" in
    '["base", "linux"]' | '["base", "dev", "linux"]') ;;
    *)
      printf 'error: unsupported temporary Linux profile set: %s\n' "$profiles" >&2
      return 1
      ;;
  esac

  git -C "$root" rev-parse --verify HEAD >/dev/null 2>&1 || {
    printf 'error: consumer integration requires a Git checkout with a committed HEAD\n' >&2
    return 1
  }
  [ -z "$(git -C "$root" status --porcelain --untracked-files=all)" ] || {
    printf 'error: consumer integration requires a clean consumer checkout: %s\n' "$root" >&2
    return 1
  }
  [ -f "$root/inventory.toml" ] || {
    printf 'error: consumer inventory is missing: %s/inventory.toml\n' "$root" >&2
    return 1
  }
  grep -Fq "[users.tester]" "$root/inventory.toml" && {
    printf 'error: temporary inventory user already exists in the consumer: tester\n' >&2
    return 1
  }
  grep -Fq "[hosts.$host]" "$root/inventory.toml" && {
    printf 'error: temporary inventory host already exists in the consumer: %s\n' "$host" >&2
    return 1
  }

  root="$(cd "$root" && pwd -P)"
  stage_parent="$(cd "$(dirname "$stage")" 2> /dev/null && pwd -P)" || {
    printf 'error: integration stage parent is unavailable: %s\n' "$(dirname "$stage")" >&2
    return 1
  }
  stage_name="$(basename "$stage")"
  stage_candidate="$stage_parent/$stage_name"
  case "$stage_candidate/" in
    "$root/"*)
      printf 'error: integration stage must be outside the consumer checkout: %s\n' "$stage" >&2
      return 1
      ;;
  esac
  case "$root/" in
    "$stage_candidate/"*)
      printf 'error: integration stage must not contain the consumer checkout: %s\n' "$stage" >&2
      return 1
      ;;
  esac

  rm -rf "$stage"
  mkdir -p "$stage"
  chmod 700 "$stage"
  git -C "$root" archive --format=tar --worktree-attributes HEAD | tar -xf - -C "$stage"
  rm -rf \
    "$stage/.beads" \
    "$stage/.git" \
    "$stage/.rumdl_cache" \
    "$stage/docs/book" \
    "$stage/fnox.local.toml" \
    "$stage/hosts" \
    "$stage/result"
  find "$stage" -maxdepth 1 -name 'result-*' -exec rm -rf {} +

  cat >"$stage/inventory.toml" <<EOF
schema = 1

[users.tester]
username = "tester"
full_name = "Linux Integration Test User"
email = "tester@localhost"
github = "RobertDeRose"

[hosts.$host]
system = "aarch64-linux"
user = "tester"
profiles = $profiles
EOF

  if [ -n "$deploy_ip" ]; then
    cat >>"$stage/inventory.toml" <<EOF

[hosts.$host.deploy]
enable = true
hostname = "$deploy_ip"
ssh_user = "root"
user_ssh_user = "tester"
repo_path = "/home/tester/.maison"
remote_build = true
auto_rollback = true
magic_rollback = true
EOF
  fi

  git -C "$stage" init -q -b main
  git -C "$stage" config user.name "Maison Linux Integration Test"
  git -C "$stage" config user.email "maison-linux-test@localhost"
  GIT_AUTHOR_DATE=2000-01-01T00:00:00Z \
    GIT_COMMITTER_DATE=2000-01-01T00:00:00Z \
    git -C "$stage" add -A
  GIT_AUTHOR_DATE=2000-01-01T00:00:00Z \
    GIT_COMMITTER_DATE=2000-01-01T00:00:00Z \
    git -C "$stage" commit -qm 'test: stage consumer fixture'
}

consumer_integration_fnox_spec() {
  local root="$1" config="$1/config/mise/config.toml" spec
  [ -f "$config" ] || {
    printf 'error: consumer mise configuration is missing: %s\n' "$config" >&2
    return 1
  }
  spec="$(
    python3 - "$config" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    value = tomllib.load(handle).get("tools", {}).get("fnox")
if not isinstance(value, str) or not value:
    raise SystemExit("consumer config must declare a string fnox tool")
print(value)
PY
  )"
  if ! python3 - "$spec" <<'PY'
import re
import sys

if not re.fullmatch(r"[-A-Za-z0-9._+:/@~^=,<>\[\]*]+", sys.argv[1]):
    raise SystemExit("consumer fnox version contains unsupported shell characters")
PY
  then
    printf 'error: consumer fnox version contains unsupported shell characters\n' >&2
    return 1
  fi
  printf '%s\n' "$spec"
}

consumer_integration_install_local_fnox() {
  local root="$1" fnox_spec temp_dir fnox_bin fnox_dir

  fnox_spec="$(consumer_integration_fnox_spec "$root")"
  temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/maison-fnox.XXXXXX")"
  chmod 700 "$temp_dir"
  printf '[tools]\nfnox = %s\n' "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$fnox_spec")" \
    >"$temp_dir/mise.toml"
  printf '%s\n' '==> Installing the consumer-declared fnox prerequisite'
  if ! MISE_GLOBAL_CONFIG_FILE="$temp_dir/mise.toml" mise -C "$temp_dir" install fnox; then
    rm -rf "$temp_dir"
    return 1
  fi
  fnox_bin="$(MISE_GLOBAL_CONFIG_FILE="$temp_dir/mise.toml" mise -C "$temp_dir" which fnox)" || {
    rm -rf "$temp_dir"
    return 1
  }
  [ -x "$fnox_bin" ] || {
    printf 'error: mise did not produce an executable fnox path\n' >&2
    rm -rf "$temp_dir"
    return 1
  }
  fnox_dir="$(dirname "$fnox_bin")"
  export PATH="$fnox_dir:$PATH"
  rm -rf "$temp_dir"
  command -v fnox >/dev/null 2>&1
}

consumer_integration_copy_stage_to_container() {
  local stage="$1" name="$2" destination="$3"

  container exec "$name" mkdir -p "$destination"
  container cp "$stage/." "$name:$destination"
}
