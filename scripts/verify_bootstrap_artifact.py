#!/usr/bin/env python3
"""Verify a Maison bootstrap artifact against checked-in metadata."""

from __future__ import annotations

import argparse
import hashlib
import platform
import sys
from pathlib import Path
from typing import Any

import tomllib


class VerificationError(RuntimeError):
    """Raised when artifact metadata or content is invalid."""


def current_system() -> str:
    machine = platform.machine().lower()
    system = platform.system()
    if machine in {"arm64", "aarch64"}:
        arch = "aarch64"
    elif machine in {"x86_64", "amd64"}:
        arch = "x86_64"
    else:
        raise VerificationError(f"unsupported architecture: {machine}")
    if system == "Darwin":
        os_name = "darwin"
    elif system == "Linux":
        os_name = "linux"
    else:
        raise VerificationError(f"unsupported operating system: {system}")
    return f"{arch}-{os_name}"


def load_artifact(manifest_path: Path, artifact_name: str, system: str) -> dict[str, Any]:
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise VerificationError("manifest is missing [artifacts]")
    artifact = artifacts.get(artifact_name)
    if not isinstance(artifact, dict):
        raise VerificationError(f"manifest is missing artifact '{artifact_name}'")

    systems = artifact.get("systems")
    if not isinstance(systems, list) or not all(isinstance(item, str) for item in systems):
        raise VerificationError(f"artifact '{artifact_name}' is missing supported systems")
    if system not in systems:
        raise VerificationError(f"artifact '{artifact_name}' does not support {system}")

    selected = dict(artifact)
    platforms = artifact.get("platforms")
    if isinstance(platforms, dict):
        platform_data = platforms.get(system)
        if not isinstance(platform_data, dict):
            raise VerificationError(f"artifact '{artifact_name}' is missing metadata for {system}")
        selected.update(platform_data)

    for field in ("version", "url", "recovery_hint"):
        if not isinstance(selected.get(field), str) or not selected[field]:
            raise VerificationError(f"artifact '{artifact_name}' is missing {field}")
    if not (isinstance(selected.get("sha256"), str) and selected["sha256"]):
        raise VerificationError(f"artifact '{artifact_name}' is missing checksum metadata")
    return selected


def sha256_hex(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, artifact: dict[str, Any]) -> None:
    expected = artifact["sha256"]
    if not expected.startswith("sha256:"):
        raise VerificationError("checksum must use sha256:<hex> format")
    expected_hex = expected.removeprefix("sha256:")
    actual_hex = sha256_hex(path)
    if actual_hex != expected_hex:
        raise VerificationError(
            "checksum mismatch for verified bootstrap artifact; "
            f"expected sha256:{expected_hex}, got sha256:{actual_hex}. "
            f"Recovery: {artifact['recovery_hint']}"
        )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--system", default=current_system())
    result.add_argument("artifact")
    result.add_argument("path", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        artifact = load_artifact(args.manifest, args.artifact, args.system)
        verify(args.path, artifact)
    except (OSError, tomllib.TOMLDecodeError, VerificationError) as exc:
        print(f"error: bootstrap artifact verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
