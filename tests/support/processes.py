from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

DEFAULT_TIMEOUT = 30.0
MAX_TIMEOUT = 300.0
DIAGNOSTIC_LIMIT = 1200
PIPE = subprocess.PIPE
DEVNULL = subprocess.DEVNULL
STDOUT = subprocess.STDOUT
CompletedProcess = subprocess.CompletedProcess


class CommandTimeout(AssertionError):
    """Raised when a test subprocess exceeds its explicit time budget."""


def _validate_timeout(timeout: float | None) -> float:
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    timeout = float(timeout)
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if timeout > MAX_TIMEOUT:
        raise ValueError(f"timeout must be no greater than {MAX_TIMEOUT:g} seconds")
    return timeout


def _start_new_process_group_kwargs() -> dict[str, bool]:
    if os.name == "posix":
        return {"start_new_session": True}
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}  # type: ignore[attr-defined]
    return {}


def _terminate_process_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    elif os.name == "nt":
        with contextlib.suppress(ProcessLookupError):
            process.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
    else:
        process.terminate()
    try:
        process.wait(timeout=1)
        return
    except subprocess.TimeoutExpired:
        pass
    if os.name == "posix":
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    else:
        process.kill()
    process.wait(timeout=1)


def _decode(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _truncate(text: str, limit: int = DIAGNOSTIC_LIMIT) -> str:
    if len(text) <= limit:
        return text
    half = max(1, (limit - 40) // 2)
    return f"{text[:half]}\n... truncated {len(text) - (2 * half)} bytes ...\n{text[-half:]}"


def diagnostics(result: subprocess.CompletedProcess[Any]) -> str:
    command = result.args if isinstance(result.args, str) else " ".join(map(str, result.args))
    return (
        f"command failed with exit code {result.returncode}: {command}\n"
        f"stdout:\n{_truncate(_decode(result.stdout))}\n"
        f"stderr:\n{_truncate(_decode(result.stderr))}"
    )


def run(
    args: Sequence[str | os.PathLike[str]] | str,
    *,
    timeout: float | None = DEFAULT_TIMEOUT,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = False,
    text: bool = True,
    input: str | bytes | None = None,
    capture_output: bool = True,
    stdout: int | None = None,
    stderr: int | None = None,
    stdin: int | None = None,
    shell: bool = False,
) -> subprocess.CompletedProcess[Any]:
    """Run a test subprocess with bounded time, captured diagnostics, and group cleanup."""

    budget = _validate_timeout(timeout)
    if capture_output and stdout is None and stderr is None:
        stdout = subprocess.PIPE
        stderr = subprocess.PIPE
    popen = cast(Any, subprocess.Popen)
    process = popen(
        args,
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=subprocess.PIPE if input is not None else stdin,
        stdout=stdout,
        stderr=stderr,
        text=text,
        shell=shell,
        **_start_new_process_group_kwargs(),
    )
    try:
        communicate = process.communicate
        out, err = communicate(input=input, timeout=budget)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        out, err = process.communicate()
        result = subprocess.CompletedProcess(args, process.returncode, out, err)
        raise CommandTimeout(f"command timed out after {budget:g} seconds\n{diagnostics(result)}") from exc

    result = subprocess.CompletedProcess(args, process.returncode, out, err)
    if check and result.returncode != 0:
        raise AssertionError(diagnostics(result))
    return result


def check_output(
    args: Sequence[str | os.PathLike[str]] | str,
    *,
    timeout: float | None = DEFAULT_TIMEOUT,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    text: bool = True,
) -> str | bytes:
    result = run(args, timeout=timeout, cwd=cwd, env=env, check=True, text=text)
    return result.stdout


def start_process(
    args: Sequence[str | os.PathLike[str]] | str,
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    text: bool = True,
    stdout: int | None = None,
    stderr: int | None = None,
    stdin: int | None = None,
) -> subprocess.Popen[Any]:
    popen = cast(Any, subprocess.Popen)
    return popen(
        args,
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        text=text,
        **_start_new_process_group_kwargs(),
    )


def terminate_process_tree(process: subprocess.Popen[Any]) -> None:
    _terminate_process_tree(process)


@contextlib.contextmanager
def temporary_directory(*, prefix: str = "maison-test-") -> Iterator[Path]:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
