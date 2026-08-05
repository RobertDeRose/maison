#!/usr/bin/env bash
# Prepare one-time user-state migrations before mise applies whole-file targets.
set -euo pipefail

root="${MAISON_USER_PREPARE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}"
framework_root="${MAISON_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}"
backup_root="$HOME/.local/state/maison/backups"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
force_dotfiles=false
dry_run=false
recovery=false
platform="${MAISON_PLATFORM:-$(uname -s)}"
ditto_bin="${MAISON_DITTO_BIN:-/usr/bin/ditto}"
unzip_bin="${MAISON_UNZIP_BIN:-/usr/bin/unzip}"
lsregister_default="/System/Library/Frameworks/CoreServices.framework"
lsregister_default+="/Frameworks/LaunchServices.framework/Support/lsregister"
lsregister_bin="${MAISON_LSREGISTER_BIN:-$lsregister_default}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --force-dotfiles) force_dotfiles=true ;;
    --dry-run) dry_run=true ;;
    --recovery) recovery=true ;;
    *)
      printf 'usage: %s [--force-dotfiles] [--dry-run] [--recovery]\n' "${0##*/}" >&2
      exit 2
      ;;
  esac
  shift
done

archive_path_for_app() {
  local app="$1" archive suffix=0
  archive="$app.zip"
  while [ -e "$archive" ] || [ -L "$archive" ]; do
    suffix=$((suffix + 1))
    archive="$app.$timestamp.$suffix.zip"
  done
  printf '%s\n' "$archive"
}

archive_backup_application_bundles() {
  local app archive marker temporary

  [ "$platform" = Darwin ] || return 0
  [ -d "$backup_root" ] || return 0

  if [ "$dry_run" = false ]; then
    if [ ! -x "$ditto_bin" ]; then
      printf 'error: cannot archive application backups because ditto is unavailable: %s\n' "$ditto_bin" >&2
      return 1
    fi
    if [ ! -x "$unzip_bin" ]; then
      printf 'error: cannot verify application backups because unzip is unavailable: %s\n' "$unzip_bin" >&2
      return 1
    fi
  fi

  # A live .app bundle retains its App Store receipt and install metadata. If it
  # remains inside a backup directory, macOS Installer can relocate later MAS
  # updates back into that backup instead of /Applications. Prevent Spotlight
  # indexing the backup root and convert every app bundle to an inert archive.
  marker="$backup_root/.metadata_never_index"
  if [ "$dry_run" = false ] && [ ! -e "$marker" ] && [ ! -L "$marker" ]; then
    : > "$marker"
  fi

  while IFS= read -r -d '' app; do
    archive="$(archive_path_for_app "$app")"
    if [ "$dry_run" = true ]; then
      printf 'Would archive backed-up application %s to %s\n' "$app" "$archive"
      continue
    fi

    temporary="$archive.tmp.$$"
    rm -f "$temporary"
    if ! "$ditto_bin" -c -k --sequesterRsrc --keepParent "$app" "$temporary"; then
      rm -f "$temporary"
      printf 'error: failed to archive backed-up application %s\n' "$app" >&2
      return 1
    fi
    if [ ! -s "$temporary" ]; then
      rm -f "$temporary"
      printf 'error: application backup archive is empty for %s\n' "$app" >&2
      return 1
    fi
    if ! "$unzip_bin" -tqq "$temporary"; then
      rm -f "$temporary"
      printf 'error: application backup archive failed verification for %s\n' "$app" >&2
      return 1
    fi

    mv "$temporary" "$archive"
    if [ -x "$lsregister_bin" ]; then
      if ! "$lsregister_bin" -u "$app" > /dev/null 2>&1; then
        printf 'warning: failed to unregister backed-up application %s\n' "$app" >&2
      fi
    fi
    rm -rf "$app"
    printf 'Archived backed-up application %s to %s\n' "$app" "$archive"
  done < <(find "$backup_root" -type d -name '*.app' -prune -print0)
}

backup_conflicting_dotfiles() {
  local output_file status backup_dir conflict target relative backup count
  local -a targets helper_args
  output_file="$(mktemp)"
  status=0

  if (
    cd "$root"
    mise bootstrap --only dotfiles --dry-run
  ) > "$output_file" 2>&1; then
    rm -f "$output_file"
    return 0
  else
    status=$?
  fi

  if ! grep -qF 'refusing to overwrite existing files' "$output_file"; then
    cat "$output_file" >&2
    rm -f "$output_file"
    return "$status"
  fi

  backup_dir="$backup_root/dotfiles/$timestamp"
  [ ! -e "$backup_dir" ] || backup_dir="$backup_dir.$$"
  count=0

  while IFS= read -r conflict; do
    case "$conflict" in
      \~/*) target="$HOME/${conflict#\~/}" ;;
      "$HOME"/*) target="$conflict" ;;
      *)
        printf 'error: cannot back up unexpected dotfile target: %s\n' "$conflict" >&2
        rm -f "$output_file"
        return 1
        ;;
    esac

    if [ ! -e "$target" ] && [ ! -L "$target" ]; then
      continue
    fi

    relative="${target#"$HOME"/}"
    backup="$backup_dir/$relative"

    if [ "$dry_run" = true ]; then
      count=$((count + 1))
      printf 'Would back up conflicting dotfile %s to %s\n' "$target" "$backup"
      continue
    fi

    targets+=("$target")
    count=$((count + 1))
  done < <(
    awk '
      /refusing to overwrite existing files/ { conflicts = 1; next }
      conflicts && /^  / { sub(/^  /, ""); print; next }
      conflicts { exit }
    ' "$output_file"
  )

  if [ "$count" -eq 0 ]; then
    cat "$output_file" >&2
    rm -f "$output_file"
    return "$status"
  fi

  rm -f "$output_file"
  if [ "$dry_run" = true ]; then
    printf 'Would use dotfile migration backup: %s\n' "$backup_dir"
    return 0
  fi

  helper_args=(backup --home "$HOME" --backup-dir "$backup_dir")
  for target in "${targets[@]}"; do
    helper_args+=(--target "$target")
  done
  python3 "$framework_root/.mise/lib/dotfile_backups.py" "${helper_args[@]}"
  for target in "${targets[@]}"; do
    relative="${target#"$HOME"/}"
    backup="$backup_dir/$relative"
    rm -rf "$target"
    printf 'Backed up conflicting dotfile %s to %s\n' "$target" "$backup"
  done
  printf 'Dotfile migration backup: %s\n' "$backup_dir"
}

if [ "$recovery" = false ]; then
  archive_backup_application_bundles
fi

if [ "$force_dotfiles" = true ]; then
  backup_conflicting_dotfiles
fi

if [ "$recovery" = false ]; then
  # Git now reads its canonical configuration from ~/.config/git/config. A legacy
  # ~/.gitconfig would take precedence over parts of that configuration, so retain
  # it as an explicit migration backup instead of deleting it.
  legacy_git="$HOME/.gitconfig"
  if [ -e "$legacy_git" ] || [ -L "$legacy_git" ]; then
    legacy_backup="$backup_root/git/gitconfig.$timestamp"
    if [ "$dry_run" = true ]; then
      printf 'Would back up legacy Git configuration to %s\n' "$legacy_backup"
    else
      mkdir -p "$backup_root/git"
      mv "$legacy_git" "$legacy_backup"
      printf 'Backed up legacy Git configuration to %s\n' "$legacy_backup"
    fi
  fi
fi
