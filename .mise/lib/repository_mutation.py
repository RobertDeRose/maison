#!/usr/bin/env python3
"""Repository mutation lock and journal helper for Maison tasks."""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


class MutationError(RuntimeError):
    pass


class RepositoryState:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.lock_path = directory / "repository.lock"
        self.journals = directory / "journals"


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.manifest_path = path / "journal.json"
        self.originals = path / "originals"
        self.candidates = path / "candidates"


def state_root() -> Path:
    if override := os.environ.get("MAISON_REPOSITORY_MUTATION_STATE_DIR"):
        return Path(override)
    if xdg := os.environ.get("XDG_STATE_HOME"):
        return Path(xdg) / "maison" / "repository-mutations"
    return Path.home() / ".local" / "state" / "maison" / "repository-mutations"


def repository_key(repo: Path) -> str:
    return hashlib.sha256(str(repo.resolve()).encode()).hexdigest()[:24]


def repository_state(repo: Path, *, state_root: Path | None = None) -> RepositoryState:
    root = state_root or globals()["state_root"]()
    directory = root / f"{repository_key(repo)}-{repo.resolve().name}"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    state = RepositoryState(directory)
    state.journals.mkdir(mode=0o700, parents=True, exist_ok=True)
    state.journals.chmod(0o700)
    return state


def has_git_checkout_marker(repo: Path) -> bool:
    marker = repo / ".git"
    return marker.is_dir() or marker.is_file()


def require_authoring_checkout(repo: Path, *, operation: str) -> None:
    repo = repo.resolve()
    if has_git_checkout_marker(repo):
        return
    if (repo / ".maison-revision").is_file():
        raise MutationError(
            f"{operation}: {repo} is a deployed Maison snapshot "
            "(found .maison-revision without .git). "
            "Edit source in a Git authoring checkout of the consumer "
            "repository, then deploy or apply the result again."
        )
    raise MutationError(
        f"{operation}: {repo} is not a Git authoring checkout. "
        "Run this authoring command from a Git authoring checkout of "
        "the consumer repository."
    )


def _relativize(path: Path, repo: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return str(resolved.relative_to(repo.resolve()))
    except ValueError as exc:
        raise MutationError(f"{path} is not inside repository {repo.resolve()}") from exc


def _copy_path(source: Path, destination: Path) -> str:
    if not source.exists() and not source.is_symlink():
        return "missing"
    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, destination, symlinks=True)
        return "directory"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination, follow_symlinks=False)
    return "file"


def _load(journal: Journal) -> dict[str, Any]:
    try:
        return json.loads(journal.manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise MutationError(f"unable to read mutation journal {journal.manifest_path}: {exc}") from exc


def _save(journal: Journal, manifest: dict[str, Any]) -> None:
    temporary = journal.manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temporary.replace(journal.manifest_path)


def begin_journal(
    repo: Path,
    *,
    operation: str,
    files: list[Path],
    state_root: Path | None = None,
) -> Journal:
    repo = repo.resolve()
    state = repository_state(repo, state_root=state_root)
    journal = Journal(state.journals / f"{int(time.time())}-{uuid.uuid4().hex}")
    journal.originals.mkdir(mode=0o700, parents=True)
    journal.candidates.mkdir(mode=0o700, parents=True)
    manifest: dict[str, Any] = {
        "repo": str(repo),
        "operation": operation,
        "state": "created",
        "created_at": time.time(),
        "files": [],
    }
    for path in files:
        relative = _relativize(path, repo)
        original_copy = journal.originals / relative
        original_kind = _copy_path(path, original_copy)
        manifest["files"].append(
            {
                "path": str(path.resolve(strict=False)),
                "relative": relative,
                "original": str(original_copy),
                "original_kind": original_kind,
            }
        )
    _save(journal, manifest)
    return journal


def record_candidate(journal: Journal, file_path: Path, candidate: Path) -> None:
    manifest = _load(journal)
    repo = Path(manifest["repo"])
    relative = _relativize(file_path, repo)
    candidate_copy = journal.candidates / relative
    candidate_kind = _copy_path(candidate, candidate_copy)
    for item in manifest["files"]:
        if item["relative"] == relative:
            item["candidate"] = str(candidate_copy)
            item["candidate_kind"] = candidate_kind
            break
    else:
        manifest["files"].append(
            {
                "path": str(file_path.resolve(strict=False)),
                "relative": relative,
                "original_kind": "missing",
                "candidate": str(candidate_copy),
                "candidate_kind": candidate_kind,
            }
        )
    _save(journal, manifest)


def mark_journal_state(journal: Journal, state: str) -> None:
    manifest = _load(journal)
    manifest["state"] = state
    manifest["updated_at"] = time.time()
    _save(journal, manifest)


def complete_journal(journal: Journal) -> None:
    if journal.path.exists():
        shutil.rmtree(journal.path)


def _restore_file(item: dict[str, Any]) -> None:
    destination = Path(item["path"])
    kind = item.get("original_kind", "missing")
    if kind == "missing":
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        elif destination.exists() or destination.is_symlink():
            destination.unlink()
        return
    original = Path(item["original"])
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            if kind != "directory":
                raise IsADirectoryError(str(destination))
            shutil.rmtree(destination)
        else:
            destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if kind == "directory":
        shutil.copytree(original, destination, symlinks=True)
    else:
        shutil.copy2(original, destination, follow_symlinks=False)


def recover_journal(journal: Journal) -> None:
    manifest = _load(journal)
    try:
        for item in manifest.get("files", []):
            _restore_file(item)
    except OSError as exc:
        raise MutationError(f"rollback failed for {journal.path}: {exc}") from exc
    complete_journal(journal)


def recover_repository(repo: Path) -> None:
    state = repository_state(repo)
    for manifest_path in sorted(state.journals.glob("*/journal.json")):
        recover_journal(Journal(manifest_path.parent))


def run_with_lock(repo: Path, command: list[str]) -> int:
    repo = repo.resolve()
    state = repository_state(repo)
    with state.lock_path.open("a+") as lock_file:
        try:
            fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                print(
                    "repository mutation lock is busy for "
                    f"{repo}; wait for the active command or inspect {state.journals}",
                    file=sys.stderr,
                )
                return 75
            raise
        recover_repository(repo)
        env = os.environ.copy()
        env["MAISON_REPOSITORY_MUTATION_LOCKED"] = "1"
        env["MAISON_REPOSITORY_MUTATION_REPO"] = str(repo)
        env["MAISON_REPOSITORY_MUTATION_STATE"] = str(state.directory)
        return subprocess.run(command, env=env, check=False).returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run")
    run.add_argument("--repo", required=True, type=Path)
    run.add_argument("argv", nargs=argparse.REMAINDER)

    recover = sub.add_parser("recover")
    recover.add_argument("--repo", required=True, type=Path)

    require = sub.add_parser("require-authoring")
    require.add_argument("--repo", required=True, type=Path)
    require.add_argument("--operation", required=True)

    begin = sub.add_parser("journal-begin")
    begin.add_argument("--repo", required=True, type=Path)
    begin.add_argument("--operation", required=True)
    begin.add_argument("--file", action="append", required=True, type=Path)

    candidate = sub.add_parser("journal-candidate")
    candidate.add_argument("--journal", required=True, type=Path)
    candidate.add_argument("--file", required=True, type=Path)
    candidate.add_argument("--candidate", required=True, type=Path)

    state = sub.add_parser("journal-state")
    state.add_argument("--journal", required=True, type=Path)
    state.add_argument("--state", required=True)

    complete = sub.add_parser("journal-complete")
    complete.add_argument("--journal", required=True, type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "run":
            command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
            if not command:
                raise MutationError("run requires a command")
            return run_with_lock(args.repo, command)
        if args.command == "recover":
            recover_repository(args.repo)
        elif args.command == "require-authoring":
            require_authoring_checkout(args.repo, operation=args.operation)
        elif args.command == "journal-begin":
            print(begin_journal(args.repo, operation=args.operation, files=args.file).path)
        elif args.command == "journal-candidate":
            record_candidate(Journal(args.journal), args.file, args.candidate)
        elif args.command == "journal-state":
            mark_journal_state(Journal(args.journal), args.state)
        elif args.command == "journal-complete":
            complete_journal(Journal(args.journal))
    except MutationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
