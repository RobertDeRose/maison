#!/usr/bin/env python3
"""Typed inventory reader and validator for Maison.

All shell tasks, CI helpers, and tests use this module instead of attempting to
parse TOML with awk. Nix mirrors the core host and platform constraints in
`nix/lib/inventory.nix` so invalid deployment data cannot reach either control plane.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

import tomllib


def load_schema() -> dict[str, Any]:
    schema_path = Path(
        os.environ.get(
            "MAISON_INVENTORY_SCHEMA",
            Path(__file__).resolve().parents[2] / "schemas/inventory.toml",
        )
    )
    try:
        with schema_path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(f"unable to load inventory schema {schema_path}: {exc}") from exc


SCHEMA = load_schema()
SUPPORTED_SYSTEMS = tuple(SCHEMA["supported_systems"])
PROFILE_NAMES = tuple(SCHEMA["profiles"])
HOST_LABEL_RE = re.compile(SCHEMA["patterns"]["host_label"])
USERNAME_RE = re.compile(SCHEMA["patterns"]["username"])
GITHUB_RE = re.compile(SCHEMA["patterns"]["github"])
PATH_COMPONENT_RE = re.compile(SCHEMA["patterns"]["path_component"])
FEATURE_SCHEMA = SCHEMA["features"]
DEPLOY_SCHEMA = SCHEMA["deploy"]


class InventoryError(RuntimeError):
    """Raised when inventory data violates the repository contract."""


@dataclass(frozen=True)
class User:
    key: str
    username: str
    full_name: str
    email: str
    github: str
    allow_nonportable: bool


@dataclass(frozen=True)
class Host:
    name: str
    system: str
    user_key: str
    profiles: tuple[str, ...]
    features: dict[str, Any]
    deploy: dict[str, Any]


def fail(message: str) -> NoReturn:
    raise InventoryError(message)


def require_mapping(value: Any, label: str) -> dict[str, Any]:
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


def valid_hostname_label(value: str) -> bool:
    return HOST_LABEL_RE.fullmatch(value) is not None


def valid_remote_hostname(value: str) -> bool:
    if len(value) > 253:
        return False
    return not value.endswith(".") and all(valid_hostname_label(label) for label in value.split("."))


def valid_username(value: str) -> bool:
    return value != "root" and USERNAME_RE.fullmatch(value) is not None


def valid_ssh_username(value: str) -> bool:
    return value == "root" or USERNAME_RE.fullmatch(value) is not None


def valid_github_username(value: str) -> bool:
    return GITHUB_RE.fullmatch(value) is not None


def compatible_profile(system: str, profile: str) -> bool:
    if profile == "mac":
        return system.endswith("-darwin")
    if profile == "linux":
        return system.endswith("-linux")
    return True


def validate_repo_path(path: str, username: str, label: str = "deploy.repo_path") -> str:
    """Require a normalized descendant of the managed Linux user's home."""

    if not path.startswith("/"):
        fail(f"{label} must be an absolute path")
    if path != posixpath.normpath(path):
        fail(f"{label} must be normalized without trailing slashes, '.', or duplicate separators")
    pure = PurePosixPath(path)
    if ".." in pure.parts:
        fail(f"{label} may not contain '..'")
    if any(PATH_COMPONENT_RE.fullmatch(part) is None for part in pure.parts[1:]):
        fail(f"{label} contains unsupported characters")

    home = PurePosixPath("/home") / username
    if pure == home or home not in pure.parents:
        fail(f"{label} must be below {home}, not the home directory itself")
    return path


def load_inventory(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise InventoryError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        fail("inventory root must be a TOML table")
    return data


def parse_users(data: dict[str, Any]) -> dict[str, User]:
    raw_users = require_mapping(data.get("users", {}), "users")
    if not raw_users:
        fail("inventory defines no users")

    users: dict[str, User] = {}
    for key, raw_value in sorted(raw_users.items()):
        raw = require_mapping(raw_value, f"users.{key}")
        username = raw.get("username", key)
        username = require_string(username, f"users.{key}.username")
        allow_nonportable = raw.get("allow_nonportable", False)
        allow_nonportable = require_bool(allow_nonportable, f"users.{key}.allow_nonportable")
        if username == "root":
            fail(f"user '{key}' may not use the root account")
        if not valid_username(username) and not allow_nonportable:
            fail(
                f"user '{key}' has invalid username '{username}'; expected a portable "
                "lowercase account name or allow_nonportable = true"
            )

        full_name = require_string(raw.get("full_name"), f"users.{key}.full_name")
        email = require_string(raw.get("email"), f"users.{key}.email")
        github = require_string(raw.get("github"), f"users.{key}.github")
        if not valid_github_username(github):
            fail(f"user '{key}' has invalid GitHub username '{github}'")

        users[key] = User(
            key=key,
            username=username,
            full_name=full_name,
            email=email,
            github=github,
            allow_nonportable=allow_nonportable,
        )
    return users


def deploy_default(field: str, host_name: str, user: User) -> Any:
    default = DEPLOY_SCHEMA[field]["default"]
    if default == "host-name":
        return host_name
    if default == "managed-user":
        return user.username
    if isinstance(default, str):
        return default.replace("<managed-user>", user.username)
    return default


def deploy_defaults(host_name: str, user: User) -> dict[str, Any]:
    return {field: deploy_default(field, host_name, user) for field in DEPLOY_SCHEMA}


def parse_hosts(data: dict[str, Any], users: dict[str, User]) -> dict[str, Host]:
    raw_hosts = require_mapping(data.get("hosts", {}), "hosts")
    if not raw_hosts:
        fail("inventory defines no hosts")

    defaults = require_mapping(data.get("defaults", {}), "defaults")
    default_user = defaults.get("user")
    if default_user is not None and not isinstance(default_user, str):
        fail("defaults.user must be a string")

    hosts: dict[str, Host] = {}
    for name, raw_value in sorted(raw_hosts.items()):
        if not valid_hostname_label(name):
            fail(f"host '{name}' is not a valid DNS label")
        raw = require_mapping(raw_value, f"hosts.{name}")
        system = require_string(raw.get("system"), f"hosts.{name}.system")
        if system not in SUPPORTED_SYSTEMS:
            fail(f"host '{name}' has unsupported system '{system}'; allowed values: " + ", ".join(SUPPORTED_SYSTEMS))

        user_key = raw.get("user", default_user)
        user_key = require_string(user_key, f"hosts.{name}.user")
        if user_key not in users:
            fail(f"host '{name}' references missing user '{user_key}'")
        user = users[user_key]
        if user.allow_nonportable and not system.endswith("-darwin"):
            fail(f"host '{name}' uses nonportable compatibility user '{user.username}' on non-Darwin system '{system}'")

        raw_profiles = raw.get("profiles")
        if not isinstance(raw_profiles, list) or not raw_profiles:
            fail(f"host '{name}' must select at least one profile")
        if not all(isinstance(profile, str) for profile in raw_profiles):
            fail(f"hosts.{name}.profiles must contain only strings")
        profiles = tuple(raw_profiles)
        if len(set(profiles)) != len(profiles):
            fail(f"host '{name}' contains duplicate profiles")
        for profile in profiles:
            if profile not in PROFILE_NAMES:
                fail(f"host '{name}' references unknown profile '{profile}'")
            if not compatible_profile(system, profile):
                fail(f"host '{name}' cannot use profile '{profile}' on '{system}'")

        raw_features = require_mapping(raw.get("features", {}), f"hosts.{name}.features")
        features = {
            field: raw_features.get(field, definition["default"]) for field, definition in FEATURE_SCHEMA.items()
        }
        for field in FEATURE_SCHEMA:
            features[field] = require_bool(features[field], f"hosts.{name}.features.{field}")
        unknown_features = set(raw_features) - set(FEATURE_SCHEMA)
        if unknown_features:
            fail(f"host '{name}' has unknown features: " + ", ".join(sorted(unknown_features)))

        raw_deploy = require_mapping(raw.get("deploy", {}), f"hosts.{name}.deploy")
        deploy = deploy_defaults(name, user)
        unknown_deploy = set(raw_deploy) - set(DEPLOY_SCHEMA)
        if unknown_deploy:
            fail(f"host '{name}' has unknown deploy fields: " + ", ".join(sorted(unknown_deploy)))
        deploy.update(raw_deploy)
        for field in ("enable", "remote_build", "auto_rollback", "magic_rollback"):
            deploy[field] = require_bool(deploy[field], f"hosts.{name}.deploy.{field}")
        for field in ("hostname", "ssh_user", "user_ssh_user", "repo_path"):
            deploy[field] = require_string(deploy[field], f"hosts.{name}.deploy.{field}")

        if not valid_remote_hostname(deploy["hostname"]):
            fail(f"host '{name}' has invalid deploy.hostname '{deploy['hostname']}'")
        if not valid_ssh_username(deploy["ssh_user"]):
            fail(f"host '{name}' has invalid deploy.ssh_user '{deploy['ssh_user']}'")
        if deploy["user_ssh_user"] != user.username:
            fail(f"host '{name}' deploy.user_ssh_user must match managed username '{user.username}'")
        if deploy["ssh_user"] == user.username:
            fail(f"host '{name}' deploy.ssh_user must not use managed username '{user.username}'")
        if deploy["enable"] and not system.endswith("-linux"):
            fail(f"host '{name}' enables deploy-rs on non-Linux system '{system}'")
        validate_repo_path(
            deploy["repo_path"],
            deploy["user_ssh_user"],
            f"hosts.{name}.deploy.repo_path",
        )

        hosts[name] = Host(
            name=name,
            system=system,
            user_key=user_key,
            profiles=profiles,
            features=features,
            deploy=deploy,
        )
    return hosts


def validate_overrides(repo_root: Path | None, hosts: dict[str, Host]) -> None:
    if repo_root is None:
        return
    host_root = repo_root / "hosts"
    if not host_root.is_dir():
        return
    for directory in sorted(path for path in host_root.iterdir() if path.is_dir()):
        if directory.name not in hosts:
            fail(f"override directory hosts/{directory.name} has no inventory entry")
        unexpected = sorted(path.name for path in directory.iterdir() if path.is_file() and path.name != "system.nix")
        if unexpected:
            fail(f"host override directory hosts/{directory.name} contains unexpected files: " + ", ".join(unexpected))


def validated(path: Path, repo_root: Path | None = None) -> tuple[dict[str, User], dict[str, Host]]:
    data = load_inventory(path)
    if data.get("schema") != 1:
        fail(f"unsupported schema {data.get('schema', 'missing')!r}; expected schema = 1")
    users = parse_users(data)
    hosts = parse_hosts(data, users)
    validate_overrides(repo_root, hosts)
    return users, hosts


def value_to_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return json.dumps(value, sort_keys=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--file",
        type=Path,
        default=Path(os.environ.get("MAISON_INVENTORY", "inventory.toml")),
    )
    result.add_argument("--repo-root", type=Path)
    commands = result.add_subparsers(dest="command", required=True)

    commands.add_parser("validate")
    commands.add_parser("list-hosts")
    commands.add_parser("list-users")

    has_host = commands.add_parser("has-host")
    has_host.add_argument("host")
    has_user = commands.add_parser("has-user")
    has_user.add_argument("user")

    host_field = commands.add_parser("host-field")
    host_field.add_argument("host")
    host_field.add_argument("field")

    user_field = commands.add_parser("user-field")
    user_field.add_argument("user")
    user_field.add_argument("field")

    rows = commands.add_parser("host-rows")
    rows.add_argument("--system", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        users, hosts = validated(args.file, args.repo_root)
        if args.command == "validate":
            print(f"{args.file} is valid")
        elif args.command == "list-hosts":
            print("\n".join(hosts))
        elif args.command == "list-users":
            print("\n".join(users))
        elif args.command == "has-host":
            return 0 if args.host in hosts else 1
        elif args.command == "has-user":
            return 0 if args.user in users else 1
        elif args.command == "user-field":
            user = users.get(args.user)
            if user is None:
                fail(f"unknown user '{args.user}'")
            fields = {
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "github": user.github,
                "allow_nonportable": user.allow_nonportable,
            }
            if args.field not in fields:
                fail(f"unknown user field '{args.field}'")
            print(value_to_text(fields[args.field]))
        elif args.command == "host-field":
            host = hosts.get(args.host)
            if host is None:
                fail(f"unknown host '{args.host}'")
            user = users[host.user_key]
            fields: dict[str, Any] = {
                "system": host.system,
                "user": host.user_key,
                "username": user.username,
                "platform": "darwin" if host.system.endswith("-darwin") else "linux",
                "profiles": host.profiles,
            }
            fields.update({f"feature.{key}": value for key, value in host.features.items()})
            fields.update({f"deploy.{key}": value for key, value in host.deploy.items()})
            if args.field not in fields:
                fail(f"unknown host field '{args.field}'")
            value = fields[args.field]
            if isinstance(value, tuple):
                print("\n".join(value))
            else:
                print(value_to_text(value))
        elif args.command == "host-rows":
            for host in hosts.values():
                if host.system != args.system:
                    continue
                user = users[host.user_key]
                print(f"{host.name}\t{user.username}\t{user.full_name}")
    except InventoryError as exc:
        print(f"error: inventory.toml: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
