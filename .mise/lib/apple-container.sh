#!/usr/bin/env bash

apple_container_state() {
  local name="$1"

  container inspect "$name" 2> /dev/null |
    jq -r '.[0].status.state // "unknown"'
}

apple_container_ipv4() {
  local name="$1"

  container inspect "$name" |
    jq -er '
      (
        .[0].status.networks[0].ipv4Address
        // .[0].networks[0].ipv4Address
        // empty
      )
      | split("/")[0]
      | select(length > 0)
    '
}

apple_container_exists() {
  local name="$1"

  container inspect "$name" > /dev/null 2>&1
}

print_apple_container_diagnostics() {
  local name="$1"

  printf '\nContainer inspection:\n' >&2
  container inspect "$name" >&2 || true

  printf '\nContainer logs:\n' >&2
  container logs "$name" >&2 || true
}

ensure_apple_test_container() {
  local name="$1"
  shift

  local state

  if ! apple_container_exists "$name"; then
    printf "==> Creating Apple container '%s'...\n" "$name"
    container run -d --name "$name" "$@" > /dev/null
    return 0
  fi

  state="$(apple_container_state "$name")"
  case "$state" in
    running)
      printf "==> Reusing running Apple container '%s'...\n" "$name"
      ;;
    stopped)
      printf "==> Starting existing Apple container '%s'...\n" "$name"
      container start "$name" > /dev/null
      ;;
    *)
      printf "ERROR: Apple container '%s' exists in unsupported state '%s'.\n" \
        "$name" "$state" >&2
      print_apple_container_diagnostics "$name"
      return 1
      ;;
  esac
}

wait_for_apple_container() {
  local name="$1"
  local attempts="${2:-60}"
  local delay="${3:-1}"
  local attempt state

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    state="$(apple_container_state "$name")"

    case "$state" in
      running)
        if container exec "$name" true > /dev/null 2>&1; then
          return 0
        fi
        ;;
      stopped)
        printf "ERROR: Apple container '%s' stopped during startup.\n" "$name" >&2
        print_apple_container_diagnostics "$name"
        return 1
        ;;
    esac

    sleep "$delay"
  done

  printf "ERROR: Apple container '%s' did not become ready after %s attempt(s).\n" \
    "$name" "$attempts" >&2
  print_apple_container_diagnostics "$name"
  return 1
}

apple_container_test_child_pid=""
apple_container_test_name=""

stop_and_delete_apple_test_container() {
  local name="$1"

  [ -n "$name" ] || return 0

  container stop "$name" > /dev/null 2>&1 || true
  container delete --force "$name" > /dev/null 2>&1 || true
}

interrupt_apple_container_test() {
  local signal="$1"
  local status

  case "$signal" in
    HUP) status=129 ;;
    INT) status=130 ;;
    PIPE) status=141 ;;
    TERM) status=143 ;;
    *) status=1 ;;
  esac

  trap - HUP INT PIPE TERM

  printf "\n==> Received SIG%s; stopping Apple container test...\n" "$signal" >&2 || true
  stop_and_delete_apple_test_container "$apple_container_test_name"

  exit "$status"
}

install_apple_container_test_signal_handlers() {
  apple_container_test_name="$1"
  trap 'interrupt_apple_container_test HUP' HUP
  trap 'interrupt_apple_container_test INT' INT
  trap 'interrupt_apple_container_test PIPE' PIPE
  trap 'interrupt_apple_container_test TERM' TERM
}

run_apple_container_test_command() {
  local status

  "$@" &
  apple_container_test_child_pid=$!

  set +e
  wait "$apple_container_test_child_pid"
  status=$?
  set -e

  apple_container_test_child_pid=""

  # mise may deliver the terminal signal to the foreground child without the
  # task shell receiving it. Convert conventional signal exit statuses back
  # into the same container cleanup path used by the shell traps.
  case "$status" in
    129) interrupt_apple_container_test HUP ;;
    130) interrupt_apple_container_test INT ;;
    141) interrupt_apple_container_test PIPE ;;
    143) interrupt_apple_container_test TERM ;;
  esac

  return "$status"
}
