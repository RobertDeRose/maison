#!/usr/bin/env python3
"""Root-owned Maison deployment transaction manager.

This module is stdlib-only so it can be streamed to a remote host during
bootstrap. It keeps repository transaction state outside the managed user's
writable home while preserving a same-filesystem transaction boundary.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DeploymentTransactionError(ValueError):
    """Raised when deployment transaction paths violate the safety contract."""


@dataclass(frozen=True, slots=True)
class TransactionPaths:
    """Concrete paths for one deployment transaction."""

    root: Path
    transaction_id: str
    transaction_dir: Path
    staging_dir: Path
    rollback_dir: Path
    journal_path: Path
    lock_path: Path
    active_path: Path


def repo_hash(repo_path: Path) -> str:
    """Return a stable non-secret namespace hash for a repository path."""

    return hashlib.sha256(str(repo_path).encode("utf-8")).hexdigest()[:16]


def default_transaction_root(repo_path: Path, managed_user: str, managed_home: Path) -> Path:
    """Return the default root-owned same-filesystem transaction namespace."""

    del repo_path
    return managed_home.parent / ".maison-deploy" / "transactions" / managed_user


def _is_relative_to(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
    except ValueError:
        return False
    return True


def _existing_ancestor(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _assert_not_symlink(path: Path, *, label: str) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise DeploymentTransactionError(f"{label} does not exist: {path}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise DeploymentTransactionError(f"{label} must not be a symlink: {path}")
    return info


def _assert_no_symlink_components(path: Path, *, label: str) -> None:
    checked: list[Path] = []
    current = path
    while current != current.parent:
        checked.append(current)
        current = current.parent
    checked.append(current)
    for component in reversed(checked):
        # macOS exposes /var as a system compatibility symlink to
        # /private/var. Local contract tests run in /var/folders; production
        # Linux deployment paths are still checked component-by-component.
        if str(component) == "/var" and component.is_symlink():
            continue
        if component.exists() or component.is_symlink():
            _assert_not_symlink(component, label=label)


def _assert_same_filesystem(
    *,
    transaction_root: Path,
    transaction_root_info: os.stat_result,
    repo_anchor: Path,
    repo_anchor_info: os.stat_result,
) -> None:
    if transaction_root_info.st_dev != repo_anchor_info.st_dev:
        raise DeploymentTransactionError(
            f"transaction root must be on the same filesystem as {repo_anchor}: {transaction_root}"
        )


def validate_transaction_root(
    *,
    repo_path: Path,
    managed_home: Path,
    transaction_root: Path,
    expected_owner_uid: int = 0,
) -> None:
    """Validate the transaction root before privileged repository mutation."""

    repo_path = repo_path.resolve(strict=False)
    managed_home = managed_home.resolve(strict=False)
    transaction_root = transaction_root.absolute()

    transaction_root_real = transaction_root.resolve(strict=False)
    if _is_relative_to(transaction_root_real, managed_home) or transaction_root_real == managed_home:
        raise DeploymentTransactionError(
            f"transaction root must be outside managed home {managed_home}: {transaction_root}"
        )

    _assert_no_symlink_components(transaction_root, label="transaction root")
    root_info = _assert_not_symlink(transaction_root, label="transaction root")
    if not stat.S_ISDIR(root_info.st_mode):
        raise DeploymentTransactionError(f"transaction root must be a directory: {transaction_root}")
    if root_info.st_uid != expected_owner_uid:
        raise DeploymentTransactionError(
            f"transaction root must be owned by uid {expected_owner_uid}: {transaction_root}"
        )
    if root_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise DeploymentTransactionError(f"transaction root must not be group/world writable: {transaction_root}")

    repo_anchor = _existing_ancestor(repo_path.parent)
    _assert_no_symlink_components(repo_anchor, label="repository ancestor")
    repo_info = _assert_not_symlink(repo_anchor, label="repository ancestor")
    _assert_same_filesystem(
        transaction_root=transaction_root,
        transaction_root_info=root_info,
        repo_anchor=repo_anchor,
        repo_anchor_info=repo_info,
    )


def allocate_transaction_paths(
    *,
    repo_path: Path,
    managed_user: str,
    managed_home: Path,
    transaction_root: Path | None = None,
    transaction_id: str | None = None,
    expected_owner_uid: int = 0,
) -> TransactionPaths:
    """Validate the transaction root and allocate paths for one transaction."""

    namespace = transaction_root or default_transaction_root(repo_path, managed_user, managed_home)
    namespace = namespace / repo_hash(repo_path)
    validate_transaction_root(
        repo_path=repo_path,
        managed_home=managed_home,
        transaction_root=namespace,
        expected_owner_uid=expected_owner_uid,
    )

    if transaction_id is None:
        transaction_id = secrets.token_urlsafe(24)
    if not transaction_id or any(character in transaction_id for character in "/\0"):
        raise DeploymentTransactionError(f"invalid transaction id: {transaction_id!r}")

    transaction_dir = namespace / transaction_id
    return TransactionPaths(
        root=namespace,
        transaction_id=transaction_id,
        transaction_dir=transaction_dir,
        staging_dir=transaction_dir / "staging",
        rollback_dir=transaction_dir / "rollback",
        journal_path=transaction_dir / "journal.jsonl",
        lock_path=namespace / "transaction.lock",
        active_path=namespace / "active.json",
    )


def _expected_owner_uid() -> int:
    return int(os.environ.get("MAISON_TRANSACTION_EXPECTED_OWNER_UID", "0"))


def _managed_home(managed_user: str) -> Path:
    return Path(os.environ.get("MAISON_MANAGED_HOME", f"/home/{managed_user}"))


def _validate_inputs(repo_path: Path, managed_user: str) -> Path:
    if not re.fullmatch(r"[a-z0-9_-]+", managed_user) or managed_user == "root":
        raise DeploymentTransactionError(f"invalid managed user: {managed_user}")
    managed_home = _managed_home(managed_user)
    repo_text = str(repo_path)
    home_text = str(managed_home)
    if not repo_text.startswith(f"{home_text}/"):
        raise DeploymentTransactionError(f"repository path must be below {managed_home}: {repo_path}")
    if re.search(r"[^A-Za-z0-9_./-]", repo_text):
        raise DeploymentTransactionError(f"repository path contains unsupported characters: {repo_path}")
    if "//" in repo_text or repo_text.endswith("/"):
        raise DeploymentTransactionError(f"repository path must be normalized: {repo_path}")
    if any(part in {".", ".."} for part in repo_path.parts):
        raise DeploymentTransactionError(f"repository path may not contain dot segments: {repo_path}")
    return managed_home


def _make_namespace(repo_path: Path, managed_user: str, managed_home: Path) -> Path:
    configured = os.environ.get("MAISON_TRANSACTION_ROOT")
    base = Path(configured) if configured else default_transaction_root(repo_path, managed_user, managed_home)
    base_real = base.absolute().resolve(strict=False)
    managed_home_real = managed_home.resolve(strict=False)
    if _is_relative_to(base_real, managed_home_real) or base_real == managed_home_real:
        raise DeploymentTransactionError(f"transaction root must be outside managed home {managed_home}: {base}")
    namespace = base / repo_hash(repo_path)
    namespace.mkdir(parents=True, mode=0o700, exist_ok=True)
    namespace.chmod(0o700)
    return namespace


def _fsync_file(handle: int) -> None:
    try:
        os.fsync(handle)
    except OSError:
        # Some filesystems/environments disable fsync on temporary descriptors.
        return


def _fsync_dir(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except (FileNotFoundError, NotADirectoryError, OSError):
        return
    try:
        _fsync_file(descriptor)
    finally:
        os.close(descriptor)


def _write_journal(path: Path, event: str, **fields: object) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, **fields}, sort_keys=True) + "\n")
        handle.flush()
        _fsync_file(handle.fileno())
    _fsync_dir(path.parent)


def _safe_rename(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        raise DeploymentTransactionError(f"move destination already exists: {dst}")
    src.replace(dst)


def _read_journal_events(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    events: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def _has_terminal_event(path: Path) -> bool:
    events = _read_journal_events(path)
    if not events:
        return False
    terminal = {"commit", "rollback"}
    return any(event.get("event") in terminal for event in events[-1:])


def _active_record(
    paths: TransactionPaths,
    *,
    repo_path: Path,
    managed_user: str,
    state: str,
    new_revision: str,
    old_revision: str | None,
    recovery_action: str | None = None,
) -> dict[str, Any]:
    return {
        "transaction_id": paths.transaction_id,
        "repo_path": str(repo_path),
        "managed_user": managed_user,
        "state": state,
        "revision": new_revision,
        "expected_old_revision": old_revision,
        "expected_new_revision": new_revision,
        "recovery_action": recovery_action,
        "transaction_dir": str(paths.transaction_dir),
        "rollback_dir": str(paths.rollback_dir / "repository"),
        "journal_path": str(paths.journal_path),
    }


def _write_active(paths: TransactionPaths, record: dict[str, Any]) -> None:
    temporary = paths.active_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with temporary.open("r+", encoding="utf-8") as handle:
        _fsync_file(handle.fileno())
    temporary.replace(paths.active_path)
    _fsync_dir(paths.active_path.parent)


def _load_active(namespace: Path, repo_path: Path, managed_user: str) -> dict[str, Any]:
    active_path = namespace / "active.json"
    if not active_path.is_file() or active_path.is_symlink():
        raise DeploymentTransactionError(f"deployment state is missing or unsafe: {active_path}")
    record = json.loads(active_path.read_text(encoding="utf-8"))
    if record.get("repo_path") != str(repo_path) or record.get("managed_user") != managed_user:
        raise DeploymentTransactionError(f"deployment state does not match repository: {active_path}")
    return record


def _safe_extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            if not (member.isdir() or member.isfile()):
                raise DeploymentTransactionError(f"archive member has unsupported type: {member.name}")
            target = destination / member.name
            resolved = target.resolve(strict=False)
            if not _is_relative_to(resolved, destination.resolve(strict=False)):
                raise DeploymentTransactionError(f"archive member escapes staging directory: {member.name}")
        bundle.extractall(destination)


def _revision(source: Path) -> str:
    for required in ("mise.toml", "flake.nix", ".maison-revision"):
        path = source / required
        if not path.is_file() or path.is_symlink():
            raise DeploymentTransactionError(f"deployment archive is missing regular file {required}")
    revision = (source / ".maison-revision").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise DeploymentTransactionError("deployment archive has an invalid revision stamp")
    if (source / ".git").exists() or (source / ".git").is_symlink():
        raise DeploymentTransactionError("deployment archive unexpectedly contains .git")
    return revision


def _active_revision(repo_path: Path) -> str:
    return _revision(repo_path)


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _fsync_dir(path)


def _verify_revision(expected: str | None, actual: str, label: str) -> None:
    if expected is None:
        return
    if actual != expected:
        raise DeploymentTransactionError(f"{label} revision mismatch: expected {expected}, found {actual}")


def _cleanup_transaction(
    *,
    namespace: Path,
    transaction_dir: Path,
    active_path: Path,
    rescue_path: Path | None = None,
) -> None:
    if rescue_path is not None and rescue_path.exists() and not rescue_path.is_symlink():
        shutil.rmtree(rescue_path, ignore_errors=True)
    active_path.unlink(missing_ok=True)
    shutil.rmtree(transaction_dir, ignore_errors=True)
    _fsync_dir(namespace)


def _rescue_path(repo_path: Path, transaction_id: str) -> Path:
    return repo_path.with_name(f"{repo_path.name}.maison-deploy-rescue-{transaction_id}")


def _transaction_dir_paths(namespace: Path, record: dict[str, Any]) -> TransactionPaths:
    required = {
        "transaction_id",
        "journal_path",
        "transaction_dir",
        "rollback_dir",
    }
    missing = required - record.keys()
    if missing:
        raise DeploymentTransactionError(f"deployment state is missing fields: {', '.join(sorted(missing))}")

    return TransactionPaths(
        root=namespace,
        transaction_id=str(record["transaction_id"]),
        transaction_dir=Path(record["transaction_dir"]),
        staging_dir=Path(record["transaction_dir"]) / "staging",
        rollback_dir=Path(record["rollback_dir"]),
        journal_path=Path(record["journal_path"]),
        lock_path=namespace / "transaction.lock",
        active_path=namespace / "active.json",
    )


def stage(repo_path: Path, managed_user: str, archive: Path) -> str:
    managed_home = _validate_inputs(repo_path, managed_user)
    if not archive.is_file() or archive.is_symlink():
        raise DeploymentTransactionError(f"deployment archive must be a regular non-symlink file: {archive}")

    namespace = _make_namespace(repo_path, managed_user, managed_home)
    paths = allocate_transaction_paths(
        repo_path=repo_path,
        managed_user=managed_user,
        managed_home=managed_home,
        transaction_root=namespace.parent,
        expected_owner_uid=_expected_owner_uid(),
    )

    with paths.lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if paths.active_path.exists() or paths.active_path.is_symlink():
            raise DeploymentTransactionError(f"unfinished Maison deployment state exists at {paths.active_path}")

        paths.transaction_dir.mkdir(mode=0o700)
        paths.staging_dir.mkdir(mode=0o700)
        paths.rollback_dir.mkdir(mode=0o700)
        staged_repo = paths.staging_dir / "repository"
        rollback_repo = paths.rollback_dir / "repository"
        repo_moved = False
        installed = False

        try:
            _write_journal(paths.journal_path, "created", repo_path=str(repo_path))
            staged_repo.mkdir(mode=0o700)
            _safe_extract(archive, staged_repo)
            new_revision = _revision(staged_repo)
            _write_journal(paths.journal_path, "archive-extracted", revision=new_revision)

            state = "absent"
            old_revision: str | None = None
            if repo_path.exists() or repo_path.is_symlink():
                if not repo_path.is_dir() or repo_path.is_symlink():
                    raise DeploymentTransactionError(f"existing repository path is not a real directory: {repo_path}")
                required_for_revision = ("mise.toml", "flake.nix", ".maison-revision")
                if all((repo_path / name).is_file() for name in required_for_revision):
                    old_revision = _active_revision(repo_path)
                _write_journal(paths.journal_path, "move-active-to-rollback", rollback_path=str(rollback_repo))
                _safe_rename(repo_path, rollback_repo)
                repo_moved = True
                state = "previous"

            _write_active(
                paths,
                _active_record(
                    paths,
                    repo_path=repo_path,
                    managed_user=managed_user,
                    state=state,
                    new_revision=new_revision,
                    old_revision=old_revision,
                ),
            )
            _write_journal(paths.journal_path, "install-staged", destination=str(repo_path))
            _ensure_directory(repo_path.parent)
            _safe_rename(staged_repo, repo_path)
            _fsync_dir(repo_path.parent)
            installed = True
            archive.unlink(missing_ok=True)
            _write_journal(paths.journal_path, "staged", revision=new_revision)
            _fsync_dir(paths.transaction_dir)
            return new_revision
        except Exception:
            if installed and repo_path.exists() and not repo_path.is_symlink():
                shutil.rmtree(repo_path)
            if repo_moved and rollback_repo.is_dir() and not rollback_repo.is_symlink() and not repo_path.exists():
                _safe_rename(rollback_repo, repo_path)
            paths.active_path.unlink(missing_ok=True)
            shutil.rmtree(paths.transaction_dir, ignore_errors=True)
            raise


def finalize(repo_path: Path, managed_user: str, action: str) -> None:
    managed_home = _validate_inputs(repo_path, managed_user)
    namespace = _make_namespace(repo_path, managed_user, managed_home)
    validate_transaction_root(
        repo_path=repo_path,
        managed_home=managed_home,
        transaction_root=namespace,
        expected_owner_uid=_expected_owner_uid(),
    )

    with (namespace / "transaction.lock").open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = _load_active(namespace, repo_path, managed_user)
        paths = _transaction_dir_paths(namespace, record)
        expected_old_revision = record.get("expected_old_revision")
        if expected_old_revision is not None:
            expected_old_revision = str(expected_old_revision)
        expected_new_revision = record.get("expected_new_revision", record.get("revision"))
        if expected_new_revision is not None:
            expected_new_revision = str(expected_new_revision)

        rollback_repo = Path(record["rollback_dir"])
        state = record["state"]

        if state not in {"previous", "absent"}:
            raise DeploymentTransactionError("deployment state has invalid repository state")

        if state == "previous" and (not rollback_repo.is_dir() or rollback_repo.is_symlink()):
            raise DeploymentTransactionError(f"previous repository is missing or unsafe: {rollback_repo}")

        if action == "commit":
            _write_journal(
                paths.journal_path,
                "finalize-start",
                recovery_action="commit",
                destination=str(repo_path),
                expected_old_revision=expected_old_revision,
                expected_new_revision=expected_new_revision,
            )

            if state == "previous" and expected_old_revision is not None:
                _verify_revision(
                    expected_old_revision,
                    _active_revision(rollback_repo),
                    "previous repository",
                )
            _verify_revision(
                expected_new_revision,
                _active_revision(repo_path),
                "active repository",
            )
            if not _has_terminal_event(paths.journal_path):
                _write_journal(
                    paths.journal_path,
                    "commit",
                    destination=str(repo_path),
                    expected_old_revision=expected_old_revision,
                    expected_new_revision=expected_new_revision,
                )
            if rollback_repo.exists():
                shutil.rmtree(rollback_repo)
            _cleanup_transaction(
                namespace=namespace,
                transaction_dir=paths.transaction_dir,
                active_path=paths.active_path,
            )
            return

        if action != "rollback":
            raise DeploymentTransactionError(f"invalid finalize action: {action}")

        _write_journal(
            paths.journal_path,
            "finalize-start",
            recovery_action="rollback",
            destination=str(repo_path),
            expected_old_revision=expected_old_revision,
            expected_new_revision=expected_new_revision,
        )

        _verify_revision(
            expected_new_revision,
            _active_revision(repo_path) if repo_path.exists() and not repo_path.is_symlink() else expected_new_revision,
            "active repository",
        )

        rescue = _rescue_path(repo_path, paths.transaction_id)
        rescued_active = False
        try:
            if repo_path.exists() or repo_path.is_symlink():
                if not repo_path.is_dir() or repo_path.is_symlink():
                    raise DeploymentTransactionError(f"repository path is not a real directory: {repo_path}")
                _safe_rename(repo_path, rescue)
                rescued_active = True
            _safe_rename(rollback_repo, repo_path) if state == "previous" else None
            if repo_path.parent.exists():
                _fsync_dir(repo_path.parent)
        except Exception:
            if (
                rescued_active
                and (not repo_path.exists() or repo_path.is_symlink())
                and not rescue.is_symlink()
                and not repo_path.exists()
            ):
                _safe_rename(rescue, repo_path)
            raise

        if not _has_terminal_event(paths.journal_path):
            _write_journal(paths.journal_path, "rollback", destination=str(repo_path))
        _cleanup_transaction(
            namespace=namespace,
            transaction_dir=paths.transaction_dir,
            active_path=paths.active_path,
            rescue_path=rescue if rescued_active else None,
        )


def recover(repo_path: Path, managed_user: str) -> None:
    managed_home = _validate_inputs(repo_path, managed_user)
    namespace = _make_namespace(repo_path, managed_user, managed_home)
    validate_transaction_root(
        repo_path=repo_path,
        managed_home=managed_home,
        transaction_root=namespace,
        expected_owner_uid=_expected_owner_uid(),
    )

    active_path = namespace / "active.json"
    if not active_path.exists() or active_path.is_symlink():
        return

    record = _load_active(namespace, repo_path, managed_user)
    journal_path = Path(record.get("journal_path", ""))
    if _has_terminal_event(journal_path):
        _cleanup_transaction(
            namespace=namespace,
            transaction_dir=Path(record["transaction_dir"]),
            active_path=active_path,
        )
        return

    if record.get("recovery_action") in {"commit", "rollback"}:
        finalize(repo_path, managed_user, str(record["recovery_action"]))
    else:
        finalize(repo_path, managed_user, "rollback")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    stage_parser = subcommands.add_parser("stage")
    stage_parser.add_argument("repo_path", type=Path)
    stage_parser.add_argument("managed_user")
    stage_parser.add_argument("archive", type=Path)

    finalize_parser = subcommands.add_parser("finalize")
    finalize_parser.add_argument("repo_path", type=Path)
    finalize_parser.add_argument("managed_user")
    finalize_parser.add_argument("action", choices=("commit", "rollback"))

    recover_parser = subcommands.add_parser("recover")
    recover_parser.add_argument("repo_path", type=Path)
    recover_parser.add_argument("managed_user")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "stage":
            revision = stage(args.repo_path, args.managed_user, args.archive)
            print(f"Staged Maison revision {revision} at {args.repo_path}")
        elif args.command == "finalize":
            finalize(args.repo_path, args.managed_user, args.action)
            verb = "Committed" if args.action == "commit" else "Rolled back"
            print(f"{verb} Maison repository transaction at {args.repo_path}")
        else:
            recover(args.repo_path, args.managed_user)
            print(f"Recovered incomplete Maison repository transaction at {args.repo_path}")
    except DeploymentTransactionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
