#!/usr/bin/env bash
# Create a revision-stamped deployment archive from committed Git content only.
set -euo pipefail

root="${1:?usage: create-deploy-archive.sh <repo-root> <archive>}"
archive="${2:?usage: create-deploy-archive.sh <repo-root> <archive>}"

if [ -n "$(git -C "$root" status --porcelain --untracked-files=normal)" ]; then
  printf 'error: deployment requires a clean working tree; commit or remove local changes first\n' >&2
  exit 1
fi

revision="$(git -C "$root" rev-parse --verify HEAD)"
staging="$(mktemp -d "${TMPDIR:-/tmp}/maison-archive.XXXXXX")"
cleanup() {
  local status=$?
  trap - EXIT HUP INT TERM
  rm -rf "$staging"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

git -C "$root" archive --format=tar HEAD | tar -xf - -C "$staging"
printf '%s\n' "$revision" > "$staging/.maison-revision"

# Keep ownership deterministic and never copy the source repository's .git,
# ignored files, untracked files, or local credentials.
tar -czf "$archive" -C "$staging" .
