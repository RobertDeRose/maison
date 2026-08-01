#!/usr/bin/env python3
"""Create and restore exact, manifest-backed Maison dotfile snapshots."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1
DOTFILE_BACKUP_ROOT = Path(".local/state/maison/backups/dotfiles")


class BackupError(Exception):
    """Raised for invalid backup or restoration input."""


def _lexical_path(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _relative_to(path: Path, root: Path, *, message: str) -> Path:
    try:
        return _lexical_path(path).relative_to(_lexical_path(root))
    except ValueError as error:
        raise BackupError(message) from error


def _path_from_relative(value: object, root: Path, *, message: str) -> Path:
    if not isinstance(value, str):
        raise BackupError(message)
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
        raise BackupError(message)
    return root / relative


def _ensure_safe_ancestors(path: Path, home: Path) -> None:
    relative = _relative_to(path, home, message="path is outside home")
    current = home
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise BackupError(f"path has symlink ancestor: {current}")
        if current.exists() and not current.is_dir():
            raise BackupError(f"path has non-directory ancestor: {current}")


def _backup_root(home: Path) -> Path:
    return home / DOTFILE_BACKUP_ROOT


def _validate_backup_dir(backup_dir: Path, home: Path) -> Path:
    backup_dir = _lexical_path(backup_dir)
    _relative_to(
        backup_dir,
        _backup_root(home),
        message="backup directory is outside Maison dotfile backups",
    )
    if backup_dir == _backup_root(home):
        raise BackupError("backup directory must name one timestamped backup")
    _ensure_safe_ancestors(backup_dir, home)
    return backup_dir


def _object_type(path: Path) -> str:
    mode = path.lstat().st_mode
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    raise BackupError(f"unsupported filesystem object: {path}")


def _entry_for(source: Path, home: Path) -> dict[str, Any]:
    relative = _relative_to(source, home, message="source is outside home")
    _ensure_safe_ancestors(source, home)
    object_type = _object_type(source)
    metadata = source.lstat()
    entry: dict[str, Any] = {
        "source": relative.as_posix(),
        "type": object_type,
        "mode": stat.S_IMODE(metadata.st_mode),
        "atime_ns": metadata.st_atime_ns,
        "mtime_ns": metadata.st_mtime_ns,
        "backup_path": relative.as_posix(),
        "restore_status": "pending",
    }
    if object_type == "symlink":
        entry["symlink_target"] = os.readlink(source)
    return entry


def _write_manifest(backup_dir: Path, manifest: dict[str, Any]) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{MANIFEST_NAME}.", dir=backup_dir, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, backup_dir / MANIFEST_NAME)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _copy_object(source: Path, destination: Path, object_type: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if object_type == "file":
        shutil.copy2(source, destination, follow_symlinks=False)
    elif object_type == "directory":
        shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)
    elif object_type == "symlink":
        os.symlink(os.readlink(source), destination)
    else:  # pragma: no cover - entries are validated before this call.
        raise BackupError(f"unsupported manifest object type: {object_type}")


def _remove_object(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _apply_metadata(path: Path, entry: dict[str, Any], object_type: str) -> None:
    if object_type != "symlink":
        path.chmod(entry["mode"])
    if object_type != "symlink":
        os.utime(path, ns=(entry["atime_ns"], entry["mtime_ns"]))


def backup(home: Path, backup_dir: Path, targets: list[Path]) -> None:
    home = _lexical_path(home)
    backup_dir = _validate_backup_dir(backup_dir, home)
    if backup_dir.exists() or backup_dir.is_symlink():
        raise BackupError(f"backup directory already exists: {backup_dir}")
    if not targets:
        raise BackupError("at least one backup target is required")

    entries = [_entry_for(_lexical_path(target), home) for target in targets]
    sources = [entry["source"] for entry in entries]
    if len(sources) != len(set(sources)):
        raise BackupError("backup targets must be unique")

    try:
        for entry in entries:
            source = _path_from_relative(entry["source"], home, message="source is outside home")
            payload = _path_from_relative(
                entry["backup_path"], backup_dir, message="backup payload escapes backup directory"
            )
            _copy_object(source, payload, entry["type"])
        _write_manifest(backup_dir, {"version": MANIFEST_VERSION, "entries": entries})
    except BaseException:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise


def _load_manifest(backup_dir: Path) -> dict[str, Any]:
    manifest_path = backup_dir / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BackupError(f"cannot read manifest: {manifest_path}") from error
    if not isinstance(manifest, dict) or manifest.get("version") != MANIFEST_VERSION:
        raise BackupError("unsupported dotfile backup manifest")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise BackupError("manifest entries must be a list")
    return manifest


def _validated_pending_entries(
    manifest: dict[str, Any], backup_dir: Path, home: Path
) -> list[tuple[dict[str, Any], Path, Path]]:
    result: list[tuple[dict[str, Any], Path, Path]] = []
    seen_sources: set[str] = set()
    for entry in manifest["entries"]:
        if not isinstance(entry, dict):
            raise BackupError("manifest entry must be an object")
        object_type = entry.get("type")
        if object_type not in {"file", "directory", "symlink"}:
            raise BackupError("unsupported manifest object type")
        source_value = entry.get("source")
        source = _path_from_relative(source_value, home, message="manifest source is outside home")
        if source_value in seen_sources:
            raise BackupError("manifest has duplicate source paths")
        seen_sources.add(source_value)
        _ensure_safe_ancestors(source, home)
        payload = _path_from_relative(
            entry.get("backup_path"), backup_dir, message="manifest payload escapes backup directory"
        )
        if object_type == "symlink":
            if not isinstance(entry.get("symlink_target"), str):
                raise BackupError("symlink manifest entry is missing target")
        elif not all(isinstance(entry.get(name), int) for name in ("mode", "atime_ns", "mtime_ns")):
            raise BackupError("manifest entry is missing filesystem metadata")
        if entry.get("restore_status") == "restored":
            continue
        if entry.get("restore_status") != "pending":
            raise BackupError("manifest restore status must be pending or restored")
        result.append((entry, source, payload))
    return result


def restore(home: Path, backup_dir: Path, *, force: bool) -> None:
    if not force:
        raise BackupError("restore requires --force")
    home = _lexical_path(home)
    backup_dir = _validate_backup_dir(backup_dir, home)
    if not backup_dir.is_dir() or backup_dir.is_symlink():
        raise BackupError(f"backup directory is unavailable: {backup_dir}")
    manifest = _load_manifest(backup_dir)
    entries = _validated_pending_entries(manifest, backup_dir, home)

    for entry, source, payload in entries:
        if not os.path.lexists(payload):
            raise BackupError(f"backup payload is unavailable: {payload}")
        if _object_type(payload) != entry["type"]:
            raise BackupError(f"backup payload type does not match manifest: {payload}")
        _ensure_safe_ancestors(source, home)
        source.parent.mkdir(parents=True, exist_ok=True)
        _remove_object(source)
        _copy_object(payload, source, entry["type"])
        _apply_metadata(source, entry, entry["type"])
        entry["restore_status"] = "restored"
        _write_manifest(backup_dir, manifest)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for command in ("backup", "restore"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--home", type=Path, required=True)
        subparser.add_argument("--backup-dir", type=Path, required=True)
        if command == "backup":
            subparser.add_argument("--target", type=Path, action="append", required=True)
        else:
            subparser.add_argument("--force", action="store_true")
    return result


def main() -> int:
    arguments = parser().parse_args()
    try:
        if arguments.command == "backup":
            backup(arguments.home, arguments.backup_dir, arguments.target)
        else:
            restore(arguments.home, arguments.backup_dir, force=arguments.force)
    except BackupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
