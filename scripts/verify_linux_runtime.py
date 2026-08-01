#!/usr/bin/env python3
"""Verify the active Linux runtime against Maison's system configuration."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeSnapshot:
    systemd_active: bool
    hostname: str
    timezone: str
    localtime_target: str
    ssh_config_valid: bool
    ssh_reload_succeeded: bool
    active_units: frozenset[str]


class RuntimeVerificationError(RuntimeError):
    """Raised when active Linux runtime state violates the Maison contract."""


def verify_runtime_state(
    snapshot: RuntimeSnapshot,
    *,
    expected_hostname: str,
    expected_timezone: str,
    required_units: tuple[str, ...],
) -> tuple[str, ...]:
    failures: list[str] = []
    if not snapshot.systemd_active:
        failures.append("systemd: systemd is not the active init system")
    if snapshot.hostname != expected_hostname:
        failures.append(f"hostname: expected {expected_hostname!r}, got {snapshot.hostname!r}")
    if snapshot.timezone != expected_timezone:
        failures.append(f"timezone: expected {expected_timezone!r}, got {snapshot.timezone!r}")
    localtime_suffix = f"/{expected_timezone}"
    if not snapshot.localtime_target.endswith(localtime_suffix):
        failures.append(
            f"localtime: expected /etc/localtime to resolve to {expected_timezone!r}, got {snapshot.localtime_target!r}"
        )
    if not snapshot.ssh_config_valid:
        failures.append("ssh: sshd configuration validation failed")
    if not snapshot.ssh_reload_succeeded:
        failures.append("reload: SSH service reload or restart failed")
    missing_units = sorted(set(required_units) - snapshot.active_units)
    for unit in missing_units:
        failures.append(f"service: required unit {unit!r} is not active")
    if failures:
        raise RuntimeVerificationError("\n".join(failures))
    return ()


def _run(argv: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return 127, ""
    return result.returncode, result.stdout.strip()


def _sshd_path() -> str | None:
    return shutil.which("sshd") or ("/usr/sbin/sshd" if Path("/usr/sbin/sshd").is_file() else None)


def collect_runtime_snapshot(
    *,
    localtime_path: Path,
    required_units: tuple[str, ...],
    ssh_reload_succeeded: bool,
) -> RuntimeSnapshot:
    systemd_status, _ = _run(["systemctl", "show", "--property=SystemState", "--value"])
    _, hostname = _run(["hostname", "--static"])
    _, timezone = _run(["timedatectl", "show", "--value", "--property=Timezone"])
    _, localtime_target = _run(["readlink", "-f", str(localtime_path)])

    sshd = _sshd_path()
    ssh_config_valid = sshd is not None and _run([sshd, "-t"])[0] == 0
    active_units = frozenset(
        unit for unit in required_units if _run(["systemctl", "is-active", "--quiet", unit])[0] == 0
    )
    return RuntimeSnapshot(
        systemd_active=systemd_status == 0,
        hostname=hostname,
        timezone=timezone,
        localtime_target=localtime_target,
        ssh_config_valid=ssh_config_valid,
        ssh_reload_succeeded=ssh_reload_succeeded,
        active_units=active_units,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-hostname", required=True)
    parser.add_argument("--expected-timezone", required=True)
    parser.add_argument("--localtime", type=Path, required=True)
    parser.add_argument("--required-unit", action="append", required=True)
    parser.add_argument("--ssh-reload-succeeded", action="store_true")
    arguments = parser.parse_args(argv)
    required_units = tuple(arguments.required_unit)
    snapshot = collect_runtime_snapshot(
        localtime_path=arguments.localtime,
        required_units=required_units,
        ssh_reload_succeeded=arguments.ssh_reload_succeeded,
    )
    try:
        verify_runtime_state(
            snapshot,
            expected_hostname=arguments.expected_hostname,
            expected_timezone=arguments.expected_timezone,
            required_units=required_units,
        )
    except RuntimeVerificationError as error:
        print(f"Linux runtime verification failed:\n{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
