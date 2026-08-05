#!/usr/bin/env python3
"""Validate the provider-neutral fnox contract used by Maison consumers.

Maison validates only the shape and safety boundary of ``fnox.toml``. Provider
names and provider-specific configuration remain consumer-owned. Secret values
are never read or printed here; fnox resolves them later during a runtime
preflight or an activation command.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, NoReturn

import tomllib


def load_schema() -> dict[str, Any]:
    schema_path = Path(
        os.environ.get(
            "MAISON_FNOX_SCHEMA",
            Path(__file__).resolve().parents[2] / "schemas/fnox.toml",
        )
    )
    try:
        with schema_path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(f"unable to load fnox schema {schema_path}: {exc}") from exc


SCHEMA = load_schema()
SECRET_NAME_RE = re.compile(SCHEMA["secret"]["name_pattern"])
PROVIDER_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SENSITIVE_FIELD_RE = re.compile(
    r"(?:^|_)(?:access[_-]?key|api[_-]?key|client[_-]?secret|credential|password|passwd|private[_-]?key|secret|token)(?:$|_)",
    re.IGNORECASE,
)

ALLOWED_SECRET_FIELDS = {
    "as_file",
    "daemon_cache",
    "description",
    "encrypted",
    "env",
    "if_missing",
    "json_path",
    "key",
    "line",
    "provider",
}


class FnoxError(RuntimeError):
    """Raised when a consumer fnox declaration violates Maison's contract."""


def fail(message: str) -> NoReturn:
    raise FnoxError(message)


def require_table(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be a TOML table")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{label} must be a non-empty string")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        fail(f"{label} must be true or false")
    return value


def require_choice(value: Any, label: str, choices: tuple[str, ...]) -> str:
    value = require_string(value, label)
    if value not in choices:
        fail(f"{label} must be one of: {', '.join(choices)}")
    return value


def validate_owner_only(path: Path, label: str) -> None:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        fail(f"{label} cannot be inspected: {exc.strerror or 'permission denied'}")
    if mode & 0o077:
        fail(f"{label} must be owner-only (mode 0600 or stricter)")


def validate_provider_fields(value: Any, label: str) -> None:
    """Reject credential material without knowing which provider is selected."""

    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                fail(f"{label} contains a non-string field name")
            if SENSITIVE_FIELD_RE.search(key):
                fail(
                    f"{label}.{key} looks like inline credential material; resolve it from the selected provider at runtime"
                )
            validate_provider_fields(nested, f"{label}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            validate_provider_fields(nested, f"{label}[{index}]")


def validate_provider_table(value: Any, label: str) -> None:
    provider = require_table(value, label)
    provider_type = require_string(provider.get("type"), f"{label}.type")
    if not provider_type.strip():
        fail(f"{label}.type must be a non-empty string")
    validate_provider_fields(provider, label)


def validate_providers(value: Any, label: str = "providers") -> tuple[str, ...]:
    providers = require_table(value, label)
    names: list[str] = []
    for name, provider in sorted(providers.items()):
        if not isinstance(name, str) or not PROVIDER_NAME_RE.fullmatch(name):
            fail(f"{label} contains invalid provider name")
        validate_provider_table(provider, f"{label}.{name}")
        names.append(name)
    return tuple(names)


def validate_secret_name(name: Any, label: str) -> str:
    if not isinstance(name, str) or not SECRET_NAME_RE.fullmatch(name):
        fail(f"{label} must be a shell-compatible logical secret name")
    return name


def validate_secret(value: Any, label: str) -> None:
    secret = require_table(value, label)
    unknown = set(secret) - ALLOWED_SECRET_FIELDS
    if unknown:
        names = ", ".join(sorted(str(item) for item in unknown))
        fail(f"{label} contains unsupported fields: {names}")

    for key in secret:
        if SENSITIVE_FIELD_RE.search(key) and key not in {"description"}:
            fail(f"{label}.{key} looks like inline credential material; resolve it at runtime")

    if "provider" in secret:
        require_string(secret["provider"], f"{label}.provider")
    if "key" in secret:
        require_string(secret["key"], f"{label}.key")
    if "encrypted" in secret:
        require_string(secret["encrypted"], f"{label}.encrypted")
    if "description" in secret:
        require_string(secret["description"], f"{label}.description")
    if "if_missing" in secret:
        require_choice(secret["if_missing"], f"{label}.if_missing", ("error",))
    if "env" in secret:
        env = secret["env"]
        if env is True or env == "true":
            fail(f'{label}.env must be "exec" or false; ambient shell injection is not allowed')
        if env is not False:
            require_choice(env, f"{label}.env", ("exec",))
    if "as_file" in secret:
        require_bool(secret["as_file"], f"{label}.as_file")
    if "daemon_cache" in secret:
        require_bool(secret["daemon_cache"], f"{label}.daemon_cache")
    if "json_path" in secret:
        require_string(secret["json_path"], f"{label}.json_path")
    if "line" in secret:
        line = secret["line"]
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            fail(f"{label}.line must be a positive integer")


def validate_secrets(value: Any, label: str = "secrets") -> tuple[str, ...]:
    secrets = require_table(value, label)
    names: list[str] = []
    for name, secret in sorted(secrets.items()):
        logical_name = validate_secret_name(name, f"{label}.{name}")
        validate_secret(secret, f"{label}.{logical_name}")
        names.append(logical_name)
    return tuple(names)


def validate_profile(value: Any, label: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    profile = require_table(value, label)
    allowed = {"env", "if_missing", "providers", "secrets"}
    unknown = set(profile) - allowed
    if unknown:
        names = ", ".join(sorted(str(item) for item in unknown))
        fail(f"{label} contains unsupported fields: {names}")
    if "if_missing" in profile:
        require_choice(profile["if_missing"], f"{label}.if_missing", ("error",))
    if "env" in profile:
        require_choice(profile["env"], f"{label}.env", ("exec",))
    providers = validate_providers(profile["providers"], f"{label}.providers") if "providers" in profile else ()
    secrets = validate_secrets(profile["secrets"], f"{label}.secrets") if "secrets" in profile else ()
    return providers, secrets


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"configuration file is missing: {path}")
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        fail(f"{path}: unable to parse TOML: {exc}")
    return require_table(value, f"{path}")


def validate(path: Path) -> dict[str, Any]:
    config = load_config(path)
    if config.get("root") is not SCHEMA["required_root"]:
        fail("root must be true so parent and global fnox configuration cannot silently enter Maison evaluation")
    require_choice(config.get("if_missing"), "if_missing", (SCHEMA["required_if_missing"],))
    require_choice(config.get("env"), "env", (SCHEMA["required_env"],))

    allowed = {
        "daemon",
        "encryption",
        "env",
        "if_missing",
        "import",
        "profiles",
        "providers",
        "proxy",
        "root",
        "secrets",
    }
    unknown = set(config) - allowed
    if unknown:
        names = ", ".join(sorted(str(item) for item in unknown))
        fail(f"configuration contains unsupported fields: {names}")

    imports = config.get("import", [])
    if not isinstance(imports, list) or not all(isinstance(item, str) and item for item in imports):
        fail("import must be a list of non-empty paths")

    providers = validate_providers(config.get("providers", {}))
    secrets = validate_secrets(config.get("secrets", {}))
    profiles_data = require_table(config.get("profiles", {}), "profiles")
    profile_providers: list[str] = []
    profile_secrets: list[str] = []
    for name, profile in sorted(profiles_data.items()):
        if not isinstance(name, str) or not PROVIDER_NAME_RE.fullmatch(name):
            fail("profiles contains an invalid profile name")
        profile_provider_names, profile_secret_names = validate_profile(profile, f"profiles.{name}")
        profile_providers.extend(f"{name}.{provider}" for provider in profile_provider_names)
        profile_secrets.extend(f"{name}.{secret}" for secret in profile_secret_names)

    encryption = config.get("encryption")
    if encryption is not None:
        validate_provider_fields(require_table(encryption, "encryption"), "encryption")
    if "daemon" in config:
        require_table(config["daemon"], "daemon")
    if "proxy" in config:
        require_table(config["proxy"], "proxy")

    local_override = path.with_name(SCHEMA["local_override"])
    if local_override.exists():
        validate_owner_only(local_override, str(local_override))

    return {
        "schema_version": SCHEMA["schema_version"],
        "path": str(path),
        "providers": sorted((*providers, *profile_providers)),
        "secrets": sorted((*secrets, *profile_secrets)),
        "profiles": sorted(str(name) for name in profiles_data),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--file", type=Path, default=Path(os.environ.get("MAISON_FNOX_CONFIG", "fnox.toml")))
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    commands.add_parser("list-secrets")
    has_secret = commands.add_parser("has-secret")
    has_secret.add_argument("name")
    return result


def main() -> int:
    arguments = parser().parse_args()
    try:
        summary = validate(arguments.file)
    except FnoxError as exc:
        print(f"error: fnox.toml: {exc}", file=sys.stderr)
        return 1

    if arguments.command == "has-secret":
        return 0 if arguments.name in summary["secrets"] else 1
    if arguments.command == "list-secrets":
        print("\n".join(summary["secrets"]))
        return 0
    if arguments.command == "validate":
        if os.environ.get("MAISON_FNOX_JSON") == "1":
            print(json.dumps(summary, sort_keys=True))
        elif summary["secrets"]:
            print(f"{arguments.file} is valid; logical secrets: {', '.join(summary['secrets'])}")
        else:
            print(f"{arguments.file} is valid; no logical secrets declared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
