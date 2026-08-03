#!/usr/bin/env python3
"""Safe Git lifecycle operations for Maison private overlays."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TypeVar

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from maison_overlay import active_overlay_path, default_state_file


class OverlayGitError(RuntimeError):
    """Raised when an overlay Git operation cannot safely continue."""


@dataclass(frozen=True)
class Upstream:
    """The configured upstream branch."""

    name: str
    remote: str | None
    branch: str
    ref: str


@dataclass(frozen=True)
class FetchResult:
    succeeded: bool
    error: str | None = None


@dataclass(frozen=True)
class RepositoryStatus:
    path: str
    branch: str
    upstream: str | None
    worktree: str
    tracked_changes: bool
    untracked_changes: bool
    changed_paths: tuple[str, ...]
    relationship: str
    ahead: int | None
    behind: int | None
    comparison: str
    fetch_error: str | None

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["changed_paths"] = list(self.changed_paths)
        return result


@dataclass(frozen=True)
class RefreshResult:
    updated: bool
    ahead: int
    behind: int


@dataclass(frozen=True)
class PublishResult:
    pushed: bool
    commits: int


@dataclass(frozen=True)
class Stash:
    ref: str
    commit: str
    message: str


@dataclass(frozen=True)
class CommitResult:
    sha: str
    subject: str
    paths: tuple[str, ...]


T = TypeVar("T")


def _git_environment(overrides: dict[str, str] | None = None) -> dict[str, str]:
    environment = os.environ.copy()
    if overrides:
        environment.update(overrides)
    return environment


def _git(
    repository: Path,
    arguments: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        env=_git_environment(env),
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        command = " ".join(["git", "-C", str(repository), *arguments])
        raise OverlayGitError(f"{command} failed: {detail or f'exit {result.returncode}'}")
    return result


def _result_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout).strip() or f"exit {result.returncode}"


def require_repository(path: Path) -> Path:
    """Return the canonical Git root or raise an actionable error."""

    candidate = path.expanduser()
    if not candidate.exists():
        raise OverlayGitError(f"overlay repository does not exist: {candidate}")
    if not candidate.is_dir():
        raise OverlayGitError(f"overlay repository is not a directory: {candidate}")
    result = _git(candidate, ["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise OverlayGitError(f"overlay is not a Git authoring checkout: {candidate}")
    return Path(result.stdout.strip()).resolve()


def active_repository(*, root: Path | None = None, state_file: Path | None = None) -> Path:
    """Resolve and require the active private overlay."""

    path = active_overlay_path(state_file or default_state_file())
    if path is None:
        raise OverlayGitError(
            "no active private overlay; pass --overlay, set MAISON_OVERLAY, or configure overlay.toml"
        )
    repository = require_repository(path)
    if root is not None and repository == root.expanduser().resolve():
        raise OverlayGitError("public Maison is not a private overlay; select an active private overlay repository")
    return repository


def _branch(repository: Path) -> str:
    result = _git(repository, ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "(detached HEAD)"


def _upstream(repository: Path) -> Upstream | None:
    result = _git(
        repository,
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    name = result.stdout.strip()
    if "/" not in name:
        return Upstream(name=name, remote=None, branch=name, ref=name)
    remote, branch = name.split("/", 1)
    return Upstream(name=name, remote=remote, branch=branch, ref=name)


def fetch_upstream(repository: Path, upstream: Upstream) -> FetchResult:
    if upstream.remote in (None, "."):
        return FetchResult(succeeded=True)
    result = _git(repository, ["fetch", "--prune", "--quiet", upstream.remote], check=False)
    if result.returncode == 0:
        return FetchResult(succeeded=True)
    return FetchResult(succeeded=False, error=_result_error(result))


def _comparison(repository: Path, upstream: Upstream) -> tuple[int, int] | None:
    result = _git(
        repository,
        ["rev-list", "--left-right", "--count", f"HEAD...{upstream.ref}"],
        check=False,
    )
    if result.returncode != 0:
        return None
    fields = result.stdout.split()
    if len(fields) != 2:
        return None
    try:
        return int(fields[0]), int(fields[1])
    except ValueError:
        return None


def _relationship(ahead: int | None, behind: int | None) -> str:
    if ahead is None or behind is None:
        return "unavailable"
    if ahead == 0 and behind == 0:
        return "in-sync"
    if ahead > 0 and behind == 0:
        return "ahead"
    if ahead == 0 and behind > 0:
        return "behind"
    return "diverged"


def _worktree_changes(repository: Path) -> tuple[bool, bool, tuple[str, ...]]:
    result = _git(repository, ["status", "--porcelain=v1", "--untracked-files=all"])
    lines = tuple(line for line in result.stdout.splitlines() if line)
    tracked = any(not line.startswith("??") for line in lines)
    untracked = any(line.startswith("??") for line in lines)
    paths: list[str] = []
    for line in lines:
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return tracked, untracked, tuple(paths)


def inspect_repository(repository: Path, *, fetch: bool = True) -> RepositoryStatus:
    repository = require_repository(repository)
    tracked, untracked, changed_paths = _worktree_changes(repository)
    upstream = _upstream(repository)
    fetch_error: str | None = None
    ahead: int | None = None
    behind: int | None = None

    if upstream is None:
        comparison = "not-configured"
        relationship = "no-upstream"
        upstream_name = None
    else:
        upstream_name = upstream.name
        fetch_result = (
            fetch_upstream(repository, upstream) if fetch else FetchResult(succeeded=False, error="fetch skipped")
        )
        if not fetch_result.succeeded:
            fetch_error = fetch_result.error
        counts = _comparison(repository, upstream)
        if counts is None:
            comparison = "unavailable"
            relationship = "unavailable"
            fetch_error = fetch_error or "the configured upstream reference is unavailable"
        else:
            ahead, behind = counts
            comparison = "fresh" if fetch_result.succeeded else "last-known"
            relationship = _relationship(ahead, behind)

    return RepositoryStatus(
        path=str(repository),
        branch=_branch(repository),
        upstream=upstream_name,
        worktree="dirty" if tracked or untracked else "clean",
        tracked_changes=tracked,
        untracked_changes=untracked,
        changed_paths=changed_paths,
        relationship=relationship,
        ahead=ahead,
        behind=behind,
        comparison=comparison,
        fetch_error=fetch_error,
    )


def format_status(status: RepositoryStatus) -> str:
    lines = [
        f"Overlay: {status.path}",
        f"Branch: {status.branch}",
        f"Upstream: {status.upstream or 'none configured'}",
        f"Worktree: {status.worktree}",
    ]
    if status.comparison == "fresh":
        lines.append("Remote comparison: fresh")
    elif status.comparison == "last-known":
        lines.append("Remote comparison: unavailable; showing last-known tracking state")
    elif status.comparison == "not-configured":
        lines.append("Remote comparison: unavailable; no upstream configured")
    else:
        lines.append("Remote comparison: unavailable")
    relationship = status.relationship
    if status.comparison == "last-known":
        relationship += " (last-known)"
    lines.append(f"Relationship: {relationship}")
    if status.fetch_error:
        lines.append(f"Fetch: unavailable ({status.fetch_error})")
    return "\n".join(lines)


def create_stash(repository: Path) -> Stash | None:
    """Stash tracked and untracked, but not ignored, worktree changes."""

    repository = require_repository(repository)
    tracked, untracked, _ = _worktree_changes(repository)
    if not tracked and not untracked:
        return None
    message = f"maison-overlay-{uuid.uuid4().hex}"
    result = _git(
        repository,
        ["stash", "push", "--include-untracked", "--message", message],
        check=False,
    )
    if result.returncode != 0:
        raise OverlayGitError(f"unable to stash overlay changes: {_result_error(result)}")
    ref_result = _git(repository, ["rev-parse", "--verify", "refs/stash"], check=False)
    if ref_result.returncode != 0 or not ref_result.stdout.strip():
        raise OverlayGitError("Git reported a stash but its reference could not be recovered")
    return Stash(ref="stash@{0}", commit=ref_result.stdout.strip(), message=message)


def restore_stash(repository: Path, stash: Stash | None) -> None:
    if stash is None:
        return
    result = _git(repository, ["stash", "pop", "--index", stash.ref], check=False)
    if result.returncode != 0:
        raise OverlayGitError(
            f"stash restoration conflict; stash remains recoverable at {stash.ref} "
            f"({stash.commit}): {_result_error(result)}"
        )


def _with_stash(repository: Path, operation: Callable[[], T]) -> T:
    stash = create_stash(repository)
    try:
        value = operation()
    except Exception as error:
        try:
            restore_stash(repository, stash)
        except OverlayGitError as restore_error:
            raise OverlayGitError(f"{error}; {restore_error}") from error
        raise
    restore_stash(repository, stash)
    return value


def _require_fetch_and_compare(repository: Path) -> tuple[Upstream, int, int]:
    upstream = _upstream(repository)
    if upstream is None:
        raise OverlayGitError("overlay has no configured upstream branch")
    fetch_result = fetch_upstream(repository, upstream)
    if not fetch_result.succeeded:
        raise OverlayGitError(f"unable to fetch overlay upstream: {fetch_result.error}")
    counts = _comparison(repository, upstream)
    if counts is None:
        raise OverlayGitError("unable to compare overlay with its configured upstream")
    return upstream, counts[0], counts[1]


def refresh_repository(repository: Path) -> RefreshResult:
    """Fetch, fast-forward if necessary, and restore local worktree changes."""

    repository = require_repository(repository)
    upstream, ahead, behind = _require_fetch_and_compare(repository)
    if ahead > 0 and behind > 0:
        raise OverlayGitError("overlay history has diverged from its upstream")

    def update() -> bool:
        if behind == 0:
            return False
        _git(repository, ["merge", "--ff-only", upstream.ref])
        return True

    updated = _with_stash(repository, update)
    return RefreshResult(updated=updated, ahead=ahead, behind=behind)


def publish_repository(repository: Path) -> PublishResult:
    """Push committed changes to the configured upstream, preserving local work."""

    repository = require_repository(repository)
    upstream, ahead, behind = _require_fetch_and_compare(repository)
    remote = upstream.remote
    if remote is None or remote == ".":
        raise OverlayGitError("overlay upstream is not a publishable remote branch")
    if behind > 0:
        if ahead > 0:
            raise OverlayGitError("overlay history has diverged from its upstream")
        raise OverlayGitError("overlay is behind its upstream; refresh before publishing")
    if ahead == 0:
        return PublishResult(pushed=False, commits=0)

    def push() -> bool:
        result = _git(
            repository,
            ["push", remote, f"HEAD:{upstream.branch}"],
            check=False,
        )
        if result.returncode != 0:
            raise OverlayGitError(f"push failed: {_result_error(result)}")
        return True

    _with_stash(repository, push)
    return PublishResult(pushed=True, commits=ahead)


def _relative_paths(repository: Path, paths: list[Path]) -> tuple[str, ...]:
    result: list[str] = []
    root = repository.resolve()
    for path in paths:
        candidate = path if path.is_absolute() else root / path
        resolved = candidate.resolve(strict=False)
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise OverlayGitError(f"commit path is outside overlay repository: {path}") from error
        result.append(str(relative))
    if not result:
        raise OverlayGitError("focused commit requires at least one path")
    return tuple(dict.fromkeys(result))


def commit_paths(
    repository: Path,
    *,
    operation: str,
    scope: str,
    identifier: str,
    paths: list[Path],
) -> CommitResult:
    """Commit only the supplied paths while preserving the real Git index."""

    repository = require_repository(repository)
    if operation not in {"added", "removed"}:
        raise OverlayGitError("focused commit operation must be added or removed")
    if any("\n" in value or "\r" in value for value in (scope, identifier)):
        raise OverlayGitError("focused commit scope and identifier cannot contain newlines")
    relative_paths = _relative_paths(repository, paths)
    subject = f"{operation}({scope}): `{identifier}`"

    with tempfile.TemporaryDirectory(prefix="maison-overlay-index-") as directory:
        index = Path(directory) / "index"
        environment = {"GIT_INDEX_FILE": str(index)}
        _git(repository, ["read-tree", "HEAD"], env=environment)
        _git(repository, ["add", "--all", "--", *relative_paths], env=environment)
        staged = _git(repository, ["diff", "--cached", "--name-only"], env=environment)
        changed_paths = tuple(line for line in staged.stdout.splitlines() if line)
        if not changed_paths:
            raise OverlayGitError("focused commit has no changes in its requested paths")
        unexpected = set(changed_paths) - set(relative_paths)
        if unexpected:
            raise OverlayGitError(f"focused commit selected unexpected paths: {sorted(unexpected)}")
        _git(repository, ["commit", "--message", subject], env=environment)

    # Align only the committed paths in the real index; unrelated staged work is untouched.
    _git(repository, ["add", "--all", "--", *relative_paths])
    sha = _git(repository, ["rev-parse", "HEAD"]).stdout.strip()
    return CommitResult(sha=sha, subject=subject, paths=changed_paths)


def _repository_argument(args: argparse.Namespace) -> Path:
    if args.repo is not None:
        repository = require_repository(args.repo)
        if args.root is not None and repository == args.root.expanduser().resolve():
            raise OverlayGitError("public Maison is not a private overlay")
        return repository
    return active_repository(root=args.root, state_file=args.state_file)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    for name in ("status", "publish"):
        command = commands.add_parser(name)
        command.add_argument("--repo", type=Path)
        command.add_argument("--root", type=Path)
        command.add_argument("--state-file", type=Path)
        if name == "status":
            command.add_argument("--json", action="store_true", dest="as_json")

    refresh = commands.add_parser("refresh")
    refresh.add_argument("--repo", type=Path, required=True)

    commit = commands.add_parser("commit")
    commit.add_argument("--repo", type=Path, required=True)
    commit.add_argument("--operation", choices=("added", "removed"), required=True)
    commit.add_argument("--scope", required=True)
    commit.add_argument("--identifier", required=True)
    commit.add_argument("--path", action="append", required=True, type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "status":
            status = inspect_repository(_repository_argument(args))
            if args.as_json:
                print(json.dumps(status.as_dict(), sort_keys=True))
            else:
                print(format_status(status))
        elif args.command == "publish":
            result = publish_repository(_repository_argument(args))
            if result.pushed:
                print(f"Published {result.commits} committed change(s) to the configured upstream.")
            else:
                print("Overlay is already up to date; no commits to publish.")
        elif args.command == "refresh":
            result = refresh_repository(require_repository(args.repo))
            if result.updated:
                print("Overlay refreshed with a fast-forward update.")
            else:
                print("Overlay already has the latest upstream commit.")
        elif args.command == "commit":
            result = commit_paths(
                require_repository(args.repo),
                operation=args.operation,
                scope=args.scope,
                identifier=args.identifier,
                paths=args.path,
            )
            print(f"Created {result.subject} ({result.sha}).")
    except (OSError, OverlayGitError) as error:
        print(f"error: maison overlay git: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
