#!/usr/bin/env bash

host_override_dir() {
  printf '%s/hosts/%s\n' "$1" "$2"
}

create_host_override_dir() {
  local root="$1" host="$2"
  mkdir -p "$(host_override_dir "$root" "$host")"
}
