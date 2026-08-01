from __future__ import annotations

# These imports intentionally form the shared fixture namespace used by tests
# that import this support module with `from ...topology import *`.
# ruff: noqa: F401
import hashlib
import json
import os
import pty
import re
import shutil
import stat
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import cast

import tomllib

from tests.support.processes import (
    DEVNULL,
    PIPE,
    STDOUT,
    CompletedProcess,
    check_output,
    run,
    start_process,
    terminate_process_tree,
)

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


def copy_files(destination: Path, *names: str) -> None:
    for name in names:
        source = ROOT / name
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def fixture_git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def git_init(path: Path) -> None:
    env = fixture_git_env()
    run(["git", "init", "-q", "-b", "main"], cwd=path, env=env, check=True)
    run(["git", "config", "user.name", "Maison Tests"], cwd=path, env=env, check=True)
    run(["git", "config", "user.email", "tests@example.invalid"], cwd=path, env=env, check=True)
    run(["git", "config", "commit.gpgSign", "false"], cwd=path, env=env, check=True)


def git_commit_all(path: Path, message: str = "fixture") -> str:
    env = fixture_git_env()
    run(["git", "add", "-A"], cwd=path, env=env, check=True)
    run(
        ["git", "commit", "--no-gpg-sign", "-q", "-m", message],
        cwd=path,
        env=env,
        check=True,
    )
    return cast(
        str,
        check_output(["git", "rev-parse", "HEAD"], cwd=path, env=env, text=True),
    ).strip()
