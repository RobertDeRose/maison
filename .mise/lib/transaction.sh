#!/usr/bin/env bash

transaction_directory() {
  mktemp -d "${TMPDIR:-/tmp}/maison-transaction.XXXXXX"
}

transaction_helper() {
  local root="${MISE_PROJECT_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)}"
  printf '%s/.mise/lib/repository_mutation.py\n' "$root"
}

transaction_require_authoring_checkout() {
  local repo="$1" operation="$2"
  python3 "$(transaction_helper)" require-authoring \
    --repo "$repo" \
    --operation "$operation"
}

transaction_require_lock() {
  local repo="$1" script="$2"
  shift 2
  if [ "${MAISON_REPOSITORY_MUTATION_LOCKED:-}" != 1 ]; then
    exec python3 "$(transaction_helper)" run --repo "$repo" -- "$script" "$@"
  fi
}

transaction_journal_begin() {
  local repo="$1" operation="$2"
  shift 2
  local -a args=(journal-begin --repo "$repo" --operation "$operation")
  local file
  for file in "$@"; do
    args+=(--file "$file")
  done
  MAISON_REPOSITORY_MUTATION_JOURNAL="$(python3 "$(transaction_helper)" "${args[@]}")"
  export MAISON_REPOSITORY_MUTATION_JOURNAL
}

transaction_journal_record_candidate() {
  [ -n "${MAISON_REPOSITORY_MUTATION_JOURNAL:-}" ] || return 0
  python3 "$(transaction_helper)" journal-candidate \
    --journal "$MAISON_REPOSITORY_MUTATION_JOURNAL" \
    --file "$1" \
    --candidate "$2"
}

transaction_journal_mark() {
  [ -n "${MAISON_REPOSITORY_MUTATION_JOURNAL:-}" ] || return 0
  python3 "$(transaction_helper)" journal-state \
    --journal "$MAISON_REPOSITORY_MUTATION_JOURNAL" \
    --state "$1"
}

transaction_journal_complete() {
  [ -n "${MAISON_REPOSITORY_MUTATION_JOURNAL:-}" ] || return 0
  python3 "$(transaction_helper)" journal-complete \
    --journal "$MAISON_REPOSITORY_MUTATION_JOURNAL"
  unset MAISON_REPOSITORY_MUTATION_JOURNAL
}

transaction_candidate() {
  local source="$1" directory="$2" candidate
  candidate="$directory/$(basename "$source")"
  cp -p "$source" "$candidate"
  printf '%s\n' "$candidate"
}

atomic_replace() {
  local candidate="$1" destination="$2" temporary
  temporary="$(dirname "$destination")/.maison.$(basename "$destination").$$.tmp"
  rm -f "$temporary"
  cp -p "$candidate" "$temporary"
  if [ "${MAISON_REPOSITORY_MUTATION_RECOVERING:-}" != true ]; then
    transaction_journal_record_candidate "$destination" "$candidate"
    transaction_journal_mark replacing
  fi
  if ! mv -f "$temporary" "$destination"; then
    rm -f "$temporary"
    return 1
  fi
  [ "${MAISON_REPOSITORY_MUTATION_RECOVERING:-}" = true ] || transaction_journal_mark committed
}

transaction_restore_file() {
  local original="$1" destination="$2"
  MAISON_REPOSITORY_MUTATION_RECOVERING=true atomic_replace "$original" "$destination"
}

transaction_set_signal_traps() {
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
}
