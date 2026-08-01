#!/usr/bin/env python3
"""Parser-backed deterministic editor for Maison TOML declarations."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import sys
from pathlib import Path
from typing import Any

import tomllib


class ConfigError(RuntimeError):
    pass


TOMLKIT_VERSION = "0.13.3"
TOMLKIT_WHEEL = Path(__file__).resolve().parents[1] / "vendor" / f"tomlkit-{TOMLKIT_VERSION}-py3-none-any.whl"
TOMLKIT_WHEEL_SHA256 = "c89c649d79ee40629a9fda55f8ace8c6a1b42deb912b2a8fd8d942ddadb606b0"
_TOMLKIT: Any | None = None


def ensure_tomlkit() -> Any:
    """Import the reviewed repository-controlled tomlkit wheel."""
    global _TOMLKIT  # cached import keeps CLI startup deterministic
    if _TOMLKIT is not None:
        return _TOMLKIT
    try:
        digest = hashlib.sha256(TOMLKIT_WHEEL.read_bytes()).hexdigest()
    except OSError as exc:
        raise ConfigError(f"missing pinned tomlkit runtime at {TOMLKIT_WHEEL}") from exc
    if digest != TOMLKIT_WHEEL_SHA256:
        raise ConfigError(f"{TOMLKIT_WHEEL}: sha256 mismatch; expected {TOMLKIT_WHEEL_SHA256}, got {digest}")
    wheel = str(TOMLKIT_WHEEL)
    if wheel not in sys.path:
        sys.path.insert(0, wheel)
    try:
        tomlkit: Any = importlib.import_module("tomlkit")
    except ImportError as exc:
        raise ConfigError(f"unable to import pinned tomlkit runtime from {TOMLKIT_WHEEL}") from exc
    if getattr(tomlkit, "__version__", None) != TOMLKIT_VERSION:
        raise ConfigError(
            f"unexpected tomlkit version {getattr(tomlkit, '__version__', None)!r}; expected {TOMLKIT_VERSION}"
        )
    _TOMLKIT = tomlkit
    return _TOMLKIT


def load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def read_toml_text(path: Path) -> tuple[str, bool]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    uses_crlf = b"\r\n" in content and b"\n" not in content.replace(b"\r\n", b"")
    return text, uses_crlf


def parse_document(path: Path) -> tuple[Any, dict[str, Any], bool]:
    text, uses_crlf = read_toml_text(path)
    kit = ensure_tomlkit()
    try:
        document = kit.parse(text)
    except kit.exceptions.ParseError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    try:
        typed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    return document, typed, uses_crlf


def dump_document(document: Any, uses_crlf: bool) -> str:
    text = ensure_tomlkit().dumps(document)
    if uses_crlf:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    return text


def replace_with_valid_toml(path: Path, document: Any, uses_crlf: bool) -> None:
    text = dump_document(document, uses_crlf)
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: edited TOML would be invalid: {exc}") from exc
    try:
        path.write_text(text, newline="")
    except OSError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def split_tool_version(tool: str) -> tuple[str, str | None]:
    # Scoped package names such as npm:@scope/package contain @ as part of the
    # identifier. Treat @ as a version separator only when it appears after the
    # final path separator (or for unqualified names such as node@24).
    separator_index = tool.rfind("@")
    if separator_index <= tool.rfind("/") or separator_index <= tool.find(":"):
        return tool, None
    name = tool[:separator_index]
    version = tool[separator_index + 1 :]
    if name and version:
        return name, version
    return tool, None


def ensure_table(document: Any, name: str) -> Any:
    value = document.get(name)
    if value is None:
        value = ensure_tomlkit().table()
        document[name] = value
    if not hasattr(value, "__setitem__"):
        raise ConfigError(f"[{name}] must be a TOML table")
    return value


def ensure_child_table(parent: Any, parent_name: str, child_name: str) -> Any:
    value = parent.get(child_name)
    if value is None:
        value = ensure_tomlkit().table()
        parent[child_name] = value
    if not hasattr(value, "__setitem__"):
        raise ConfigError(f"[{parent_name}.{child_name}] must be a TOML table")
    return value


def validate_tool_table(path: Path, tools: Any) -> None:
    if not isinstance(tools, dict):
        raise ConfigError(f"{path}: [tools] must be a table")
    for configured_name, configured in tools.items():
        valid = isinstance(configured, str) or (
            isinstance(configured, list) and configured and all(isinstance(item, str) for item in configured)
        )
        if not valid:
            raise ConfigError(
                f"{path}: [tools].{configured_name} uses a structured value; edit it manually to preserve its options"
            )


def edit_tool(path: Path, tool: str, version: str, remove: bool) -> None:
    document, typed, uses_crlf = parse_document(path)
    typed_tools = typed.get("tools", {})
    validate_tool_table(path, typed_tools)
    tools = ensure_table(document, "tools")
    name, embedded_version = split_tool_version(tool)
    selected = embedded_version or version

    if remove:
        if name not in typed_tools:
            raise ConfigError(f"tool {name!r} is not present in {path}")
        if embedded_version is None:
            del tools[name]
        else:
            configured = typed_tools[name]
            versions = [configured] if isinstance(configured, str) else list(configured)
            if embedded_version not in versions:
                raise ConfigError(f"version {embedded_version!r} is not configured for tool {name!r}")
            versions.remove(embedded_version)
            if not versions:
                del tools[name]
            else:
                tools[name] = versions[0] if len(versions) == 1 else versions
    else:
        configured = typed_tools.get(name)
        if configured is None:
            tools[name] = selected
        else:
            versions = [configured] if isinstance(configured, str) else list(configured)
            if selected in versions:
                raise ConfigError(f"version {selected!r} is already configured for {name!r}")
            tools[name] = [*versions, selected]

    replace_with_valid_toml(path, document, uses_crlf)


def edit_package(path: Path, package: str, version: str, remove: bool) -> None:
    if ":" not in package:
        raise ConfigError("package must use manager:package syntax")
    document, typed, uses_crlf = parse_document(path)
    bootstrap = typed.get("bootstrap", {})
    if not isinstance(bootstrap, dict):
        raise ConfigError(f"{path}: [bootstrap] must be a table")
    packages = bootstrap.get("packages", {})
    if not isinstance(packages, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in packages.items()
    ):
        raise ConfigError(f"{path}: [bootstrap.packages] must map names to version strings")

    bootstrap_table = ensure_table(document, "bootstrap")
    package_table = ensure_child_table(bootstrap_table, "bootstrap", "packages")

    if remove:
        if package not in packages:
            raise ConfigError(f"package {package!r} is not present in {path}")
        del package_table[package]
    else:
        if package in packages:
            raise ConfigError(f"package {package!r} is already present in {path}")
        package_table[package] = version

    replace_with_valid_toml(path, document, uses_crlf)


def lock_entries_for(tools: dict[str, Any], name: str) -> list[dict[str, Any]]:
    entries = tools.get(name, [])
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        raise ConfigError(f"lockfile entry for {name!r} has an unexpected shape")
    if not all(isinstance(entry, dict) for entry in entries):
        raise ConfigError(f"lockfile entry for {name!r} has an unexpected shape")
    return entries


def lock_entry_version(entry: dict[str, Any], name: str) -> str:
    version = entry.get("version")
    if not isinstance(version, str):
        raise ConfigError(f"lockfile block for {name!r} has no string version")
    return version


def has_tool(path: Path, tool: str) -> bool:
    name, _ = split_tool_version(tool)
    return name in load_toml(path).get("tools", {})


def remove_locked_tool(path: Path, tool: str, config: Path | None = None) -> None:
    # Lockfiles use one [[tools.NAME]] block per resolved version. Remove all
    # blocks when the tool disappeared from the candidate config. For a
    # version-specific removal that leaves other selectors configured, remove
    # only an exactly matching resolved version; fuzzy selectors may share a
    # resolved lock entry and are intentionally left for mise to reconcile.
    document, typed, uses_crlf = parse_document(path)
    name, selected_version = split_tool_version(tool)
    if config is not None and name not in load_toml(config).get("tools", {}):
        selected_version = None

    typed_tools = typed.get("tools", {})
    if not isinstance(typed_tools, dict):
        raise ConfigError(f"{path}: [tools] must be a table")
    if name not in typed_tools:
        return

    tools = document.get("tools")
    if tools is None:
        return
    entries = lock_entries_for(typed_tools, name)
    if selected_version is None:
        del tools[name]
    else:
        matching_indexes = [
            index for index, entry in enumerate(entries) if lock_entry_version(entry, name) == selected_version
        ]
        if not matching_indexes:
            return
        document_entries = tools[name]
        if isinstance(document_entries, dict):
            if 0 in matching_indexes:
                del tools[name]
        else:
            for index in reversed(matching_indexes):
                del document_entries[index]
            if len(document_entries) == 0:
                del tools[name]

    replace_with_valid_toml(path, document, uses_crlf)


def add_host(path: Path, name: str, *, system: str, user: str, profiles: list[str]) -> None:
    document, typed, uses_crlf = parse_document(path)
    hosts = typed.get("hosts", {})
    if not isinstance(hosts, dict):
        raise ConfigError(f"{path}: [hosts] must be a table")
    if name in hosts:
        raise ConfigError(f"host {name!r} is already present in {path}")
    if not profiles:
        raise ConfigError("at least one profile is required")

    hosts_table = ensure_table(document, "hosts")
    host_table = ensure_tomlkit().table()
    host_table.add("system", system)
    host_table.add("user", user)
    host_table.add("profiles", profiles)
    hosts_table[name] = host_table
    replace_with_valid_toml(path, document, uses_crlf)


def parse_profiles(value: str) -> list[str]:
    profiles = [profile.strip() for profile in value.split(",")]
    return [profile for profile in profiles if profile]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)

    tool = sub.add_parser("tool")
    tool.add_argument("--file", required=True, type=Path)
    tool.add_argument("--name", required=True)
    tool.add_argument("--version", default="latest")
    tool.add_argument("--remove", action="store_true")

    package = sub.add_parser("package")
    package.add_argument("--file", required=True, type=Path)
    package.add_argument("--name", required=True)
    package.add_argument("--version", default="latest")
    package.add_argument("--remove", action="store_true")

    host = sub.add_parser("host")
    host.add_argument("--file", required=True, type=Path)
    host.add_argument("--name", required=True)
    host.add_argument("--system", required=True)
    host.add_argument("--user", required=True)
    host.add_argument("--profiles", required=True)

    contains = sub.add_parser("has-tool")
    contains.add_argument("--file", required=True, type=Path)
    contains.add_argument("--name", required=True)

    lock_remove = sub.add_parser("lock-remove")
    lock_remove.add_argument("--file", required=True, type=Path)
    lock_remove.add_argument("--name", required=True)
    lock_remove.add_argument("--config", type=Path)

    validate = sub.add_parser("validate")
    validate.add_argument("files", nargs="+", type=Path)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        if args.command == "tool":
            edit_tool(args.file, args.name, args.version, args.remove)
        elif args.command == "package":
            edit_package(args.file, args.name, args.version, args.remove)
        elif args.command == "host":
            add_host(
                args.file,
                args.name,
                system=args.system,
                user=args.user,
                profiles=parse_profiles(args.profiles),
            )
        elif args.command == "has-tool":
            return 0 if has_tool(args.file, args.name) else 1
        elif args.command == "lock-remove":
            remove_locked_tool(args.file, args.name, args.config)
        else:
            for path in args.files:
                load_toml(path)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
