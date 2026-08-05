#!/usr/bin/env python3
"""Validate a Maison consumer repository without activating or resolving secrets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import unquote

import tomllib

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_MODULE_PATH = ROOT / ".mise/lib/inventory.py"
CONFIG_DIRECTORY = Path("config/mise")
SUPPORTED_DOTFILE_MODES = frozenset({"copy", "symlink", "symlink-each", "template"})
EXCLUDED_PARTS = frozenset({".git", ".build", ".direnv", ".rumdl_cache", "node_modules", "result"})
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----")
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?im)^\s*(?:export\s+)?[\"']?(?:[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PRIVATE_KEY|API_KEY)|"
    r"password|token|secret|private[_-]?key|api[_-]?key)[\"']?\s*[:=]\s*(?P<value>[^#\n]+)"
)
FNOX_REFERENCE_PATTERN = re.compile(r"\bfnox\b", re.IGNORECASE)
FNOX_LITERAL_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:password|token|secret|private[_-]?key|api[_-]?key)\b\s*[:=]\s*(?P<value>['\"][^'\"]+['\"])?"
)
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


@dataclass(frozen=True)
class CheckResult:
    name: str
    detail: str


class ConsumerValidationError(RuntimeError):
    """A consumer contract check failed."""

    def __init__(self, check: str, message: str) -> None:
        self.check = check
        self.message = message
        super().__init__(f"{check}: {message}")


def _fail(check: str, message: str) -> NoReturn:
    raise ConsumerValidationError(check, message)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _regular_file(path: Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        _fail("repository", f"{label} must be a regular file")


def _load_inventory_module() -> Any:
    module_name = "maison_consumer_inventory"
    specification = importlib.util.spec_from_file_location(module_name, INVENTORY_MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"unable to load inventory validator from {INVENTORY_MODULE_PATH}")
    module = importlib.util.module_from_spec(specification)
    previous_schema = os.environ.pop("MAISON_INVENTORY_SCHEMA", None)
    try:
        sys.modules[module_name] = module
        specification.loader.exec_module(module)
    finally:
        if previous_schema is not None:
            os.environ["MAISON_INVENTORY_SCHEMA"] = previous_schema
    return module


def _validate_repository(root: Path) -> None:
    if not root.is_dir():
        _fail("repository", f"consumer root is not a directory: {root}")
    for name in ("flake.nix", "flake.lock", "inventory.toml"):
        _regular_file(root / name, name)
    _regular_file(root / "README.md", "README.md")


def _validate_inventory(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        module = _load_inventory_module()
        users, hosts = module.validated(root / "inventory.toml", root)
    except Exception as error:  # noqa: BLE001 - normalize the validator's typed and import errors
        message = str(error)
        _fail("inventory", message.removeprefix("error: inventory.toml: "))
    return users, hosts


def _load_toml(path: Path, root: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        _fail("packages", f"{path.relative_to(root)}: {error}")
    if not isinstance(value, dict):
        _fail("packages", f"{path.relative_to(root)} must contain a TOML table")
    return value


def _configuration_files(root: Path) -> list[Path]:
    configuration_root = root / CONFIG_DIRECTORY
    if not configuration_root.exists():
        return []
    if configuration_root.is_symlink() or not configuration_root.is_dir():
        _fail("packages", f"{CONFIG_DIRECTORY} must be a directory")
    files: list[Path] = []
    for path in sorted(configuration_root.rglob("*")):
        if path.suffix not in {".toml", ".lock"}:
            continue
        if path.is_symlink():
            _fail("packages", f"{path.relative_to(root)} must be a regular file")
        if path.is_file():
            files.append(path)
    return files


def _validate_package_table(path: Path, root: Path, data: dict[str, Any]) -> None:
    relative = path.relative_to(root)
    tools = data.get("tools")
    if tools is not None and not isinstance(tools, dict):
        _fail("packages", f"{relative}: [tools] must be a table")

    bootstrap = data.get("bootstrap", {})
    if not isinstance(bootstrap, dict):
        _fail("packages", f"{relative}: [bootstrap] must be a table")
    packages = bootstrap.get("packages", {})
    if not isinstance(packages, dict):
        _fail("packages", f"{relative}: [bootstrap.packages] must be a table")
    for name, version in packages.items():
        if (
            not isinstance(name, str)
            or not name
            or name.count(":") != 1
            or any(not part for part in name.split(":", 1))
        ):
            _fail("packages", f"{path}: package names must use manager:package syntax")
        if not isinstance(version, str) or not version:
            _fail("packages", f"{path}: package {name!r} must have a non-empty version")


def _validate_dotfiles(root: Path, path: Path, data: dict[str, Any]) -> int:
    dotfiles = data.get("dotfiles", {})
    if not isinstance(dotfiles, dict):
        _fail("dotfiles", f"{path}: [dotfiles] must be a table")
    count = 0
    configuration_root = root / CONFIG_DIRECTORY
    for target, entry in dotfiles.items():
        if not isinstance(target, str) or not (target == "~" or target.startswith("~/")):
            _fail("dotfiles", f"{path}: dotfile target {target!r} must be home-relative")
        if ".." in Path(target[2:] if target.startswith("~/") else "").parts:
            _fail("dotfiles", f"{path}: dotfile target {target!r} may not contain '..'")
        if not isinstance(entry, dict):
            _fail("dotfiles", f"{path}: dotfile {target!r} must be a table")
        source = entry.get("source")
        if not isinstance(source, str) or not source:
            _fail("dotfiles", f"{path}: dotfile {target!r} needs a source")
        mode = entry.get("mode", "symlink")
        if not isinstance(mode, str) or mode not in SUPPORTED_DOTFILE_MODES:
            _fail("dotfiles", f"{path}: dotfile {target!r} has unsupported mode {mode!r}")
        source_path = (configuration_root / source).resolve()
        if not _is_within(source_path, root):
            _fail("dotfiles", f"{path}: source for {target!r} escapes the consumer root")
        if not source_path.exists():
            _fail("dotfiles", f"{path}: source for {target!r} does not exist")
        if not source_path.is_file() and not source_path.is_dir():
            _fail("dotfiles", f"{path}: source for {target!r} is not a regular file or directory")
        count += 1
    return count


def _validate_declarations(root: Path) -> tuple[int, int]:
    packages = 0
    dotfiles = 0
    for path in _configuration_files(root):
        data = _load_toml(path, root)
        _validate_package_table(path, root, data)
        bootstrap = data.get("bootstrap", {})
        if isinstance(bootstrap, dict):
            package_table = bootstrap.get("packages", {})
            if isinstance(package_table, dict):
                packages += len(package_table)
        dotfiles += _validate_dotfiles(root, path, data)
    return packages, dotfiles


def _iter_text_files(root: Path) -> Iterable[tuple[Path, str]]:
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.is_symlink()
            or any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)
        ):
            continue
        try:
            if path.stat().st_size > 2 * 1024 * 1024:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        yield path, text


def _validate_fnox_references(root: Path) -> int:
    references = 0
    for path, text in _iter_text_files(root):
        for line in text.splitlines():
            if not FNOX_REFERENCE_PATTERN.search(line):
                continue
            references += 1
            literal = FNOX_LITERAL_ASSIGNMENT_PATTERN.search(line)
            if literal is not None and not _is_placeholder(literal.group("value") or ""):
                _fail(
                    "fnox",
                    f"{path.relative_to(root)} embeds a credential next to a fnox reference; use a logical reference",
                )
    return references


def _validate_documentation(root: Path) -> int:
    readme = root / "README.md"
    try:
        readme_text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        _fail("documentation", f"unable to read README.md: {error}")
    if "maison" not in readme_text.casefold():
        _fail("documentation", "README.md must identify the Maison framework")

    markdown_files = [readme]
    docs_root = root / "docs"
    if docs_root.is_dir():
        markdown_files.extend(
            path for path in sorted(docs_root.rglob("*.md")) if "book" not in path.relative_to(docs_root).parts
        )
    links = 0
    for markdown in markdown_files:
        try:
            text = markdown.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            _fail("documentation", f"unable to read {markdown.relative_to(root)}: {error}")
        for raw_target in MARKDOWN_LINK_PATTERN.findall(text):
            raw_target = raw_target.strip()
            if raw_target.startswith("<") and ">" in raw_target:
                target = raw_target[1 : raw_target.index(">")]
            else:
                target = raw_target.split(maxsplit=1)[0] if raw_target else ""
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target or "://" in target or target.startswith(("#", "mailto:")):
                continue
            target_path = (markdown.parent / unquote(target)).resolve()
            if not _is_within(target_path, root) or not target_path.exists():
                _fail("documentation", f"{markdown.relative_to(root)} links to missing {raw_target.strip()!r}")
            links += 1
    return links


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("\"'").strip()
    if not normalized or normalized.startswith(("$", "${", "<", "{{")):
        return True
    return normalized.casefold().startswith(("fnox:", "fnox://", "secret:", "secret://")) or normalized.casefold() in {
        "example",
        "placeholder",
        "change-me",
        "changeme",
        "not-a-secret",
    }


def _validate_privacy(root: Path) -> int:
    for path in sorted(root.rglob("*")):
        if not path.is_symlink() or any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts):
            continue
        if not _is_within(path.resolve(), root):
            _fail("privacy", f"{path.relative_to(root)} points outside the consumer root")

    findings = 0
    for path, text in _iter_text_files(root):
        relative = path.relative_to(root)
        name = path.name.casefold()
        if PRIVATE_KEY_PATTERN.search(text):
            _fail("privacy", f"{relative} contains private-key material")
        if (
            name in {".env", ".env.local", "credentials.json", "secrets.json"}
            or (name.startswith(".env.") and name not in {".env.example", ".env.sample"})
            or path.suffix.casefold() in {".pem", ".p12", ".pfx"}
            or name in {"id_rsa", "id_ed25519", "id_ecdsa"}
        ):
            _fail("privacy", f"{relative} looks like a credential or private-key file")
        for match in SECRET_ASSIGNMENT_PATTERN.finditer(text):
            if not _is_placeholder(match.group("value")):
                _fail("privacy", f"{relative} contains a raw credential assignment")
        findings += 1
    return findings


def _clean_command_failure(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode < 0:
        return f"terminated by signal {-result.returncode}"
    return f"exited with status {result.returncode}"


def _nix_expression(root: Path) -> str:
    root_literal = json.dumps(str(root))
    return f"""
let
  flake = builtins.getFlake (toString {root_literal});
  attrs = name: if builtins.hasAttr name flake && builtins.isAttrs flake.${{name}} then flake.${{name}} else {{}};
  deploy = if builtins.hasAttr \"deploy\" flake && builtins.isAttrs flake.deploy && builtins.hasAttr \"nodes\" flake.deploy
    then flake.deploy.nodes
    else {{}};
in {{
  inputs = builtins.attrNames (attrs \"inputs\");
  darwinConfigurations = builtins.attrNames (attrs \"darwinConfigurations\");
  systemConfigs = builtins.attrNames (attrs \"systemConfigs\");
  deploy = builtins.attrNames deploy;
}}
"""


def _safe_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in tuple(environment):
        upper = key.upper()
        if upper.startswith("FNOX_") or upper in {
            "BW_SESSION",
            "BITWARDEN_SESSION",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
        }:
            environment.pop(key, None)
    return environment


def _run_command(
    command: list[str],
    *,
    root: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(
            command,
            cwd=root,
            env=_safe_environment(),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        _fail("flake", "Nix/Lix is required to validate consumer flake composition")
    except subprocess.TimeoutExpired:
        _fail("flake", f"{' '.join(command[:2])} timed out after 300 seconds")
    raise AssertionError("unreachable")


def _validate_flake(
    root: Path, hosts: dict[str, Any], *, runner: Callable[..., subprocess.CompletedProcess[str]]
) -> None:
    nix = shutil.which("nix") or shutil.which("lix")
    if nix is None:
        _fail("flake", "Nix/Lix is required to validate consumer flake composition")

    check = _run_command([nix, "flake", "check", "--no-update-lock-file"], root=root, runner=runner)
    if check.returncode != 0:
        _fail("flake", f"nix flake check {_clean_command_failure(check)}")

    evaluation = _run_command(
        [
            nix,
            "eval",
            "--impure",
            "--no-update-lock-file",
            "--json",
            "--expr",
            _nix_expression(root),
        ],
        root=root,
        runner=runner,
    )
    if evaluation.returncode != 0:
        _fail("flake", f"nix output evaluation {_clean_command_failure(evaluation)}")
    try:
        outputs = json.loads(evaluation.stdout)
    except json.JSONDecodeError:
        _fail("flake", "Nix output evaluation did not return JSON")
    if not isinstance(outputs, dict):
        _fail("flake", "Nix output evaluation did not return an attribute set")

    inputs = outputs.get("inputs", [])
    darwin = outputs.get("darwinConfigurations", [])
    linux = outputs.get("systemConfigs", [])
    deploy = outputs.get("deploy", [])
    if not all(
        isinstance(value, list) and all(isinstance(item, str) for item in value)
        for value in (inputs, darwin, linux, deploy)
    ):
        _fail("flake", "Nix output evaluation returned malformed output names")
    if "maison" not in inputs:
        _fail("flake", "consumer flake does not expose its Maison input")

    expected_deploy: set[str] = set()
    for host_name, host in hosts.items():
        system = host.system
        if system.endswith("-darwin"):
            if host_name not in darwin:
                _fail("flake", f"inventory host {host_name!r} is missing darwinConfigurations.{host_name}")
        elif system.endswith("-linux"):
            if host_name not in linux:
                _fail("flake", f"inventory host {host_name!r} is missing systemConfigs.{host_name}")
            if host.deploy.get("enable"):
                expected_deploy.add(host_name)
    unexpected_deploy = set(deploy) - expected_deploy
    missing_deploy = expected_deploy - set(deploy)
    if unexpected_deploy:
        _fail("flake", "deploy output contains hosts absent from enabled inventory")
    if missing_deploy:
        _fail("flake", "deploy output is missing enabled inventory hosts")


def validate_consumer(
    root: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[CheckResult]:
    """Run the read-only Maison consumer contract and return successful checks."""

    root = root.expanduser().resolve()
    _validate_repository(root)
    results = [CheckResult("repository", "required consumer files are regular and present")]

    _, hosts = _validate_inventory(root)
    results.append(CheckResult("inventory", f"validated {len(hosts)} host(s) on supported systems"))

    try:
        with (root / "flake.lock").open(encoding="utf-8") as handle:
            lock = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        _fail("flake", f"unable to parse flake.lock: {error}")
    nodes = lock.get("nodes") if isinstance(lock, dict) else None
    root_node_name = lock.get("root", "root") if isinstance(lock, dict) else "root"
    if (
        not isinstance(nodes, dict)
        or not isinstance(root_node_name, str)
        or not isinstance(nodes.get(root_node_name), dict)
    ):
        _fail("flake", "flake.lock does not contain a valid root node")
    root_inputs = nodes[root_node_name].get("inputs", {})
    if not isinstance(root_inputs, dict) or "maison" not in root_inputs:
        _fail("flake", "flake.lock root does not pin a Maison input")
    maison_node = root_inputs["maison"]
    if not isinstance(maison_node, str) or maison_node not in nodes:
        _fail("flake", "flake.lock Maison input does not resolve to a node")
    results.append(CheckResult("flake", "flake.lock pins Maison from the consumer root"))

    package_count, dotfile_count = _validate_declarations(root)
    results.append(CheckResult("packages", f"validated {package_count} package declaration(s)"))
    results.append(CheckResult("dotfiles", f"validated {dotfile_count} dotfile declaration(s)"))

    fnox_count = _validate_fnox_references(root)
    results.append(
        CheckResult("fnox", f"validated {fnox_count} provider-neutral reference line(s) without resolving credentials")
    )

    link_count = _validate_documentation(root)
    results.append(CheckResult("documentation", f"validated README integration and {link_count} local link(s)"))

    file_count = _validate_privacy(root)
    results.append(
        CheckResult("privacy", f"scanned {file_count} consumer file(s) for raw credentials and private keys")
    )

    _validate_flake(root, hosts, runner=runner)
    results.append(CheckResult("flake", "checked consumer outputs without activation or lock updates"))
    return results


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--consumer",
        type=Path,
        default=Path(os.environ["MAISON_CONSUMER_ROOT"]) if os.environ.get("MAISON_CONSUMER_ROOT") else Path.cwd(),
        help="consumer repository to validate (defaults to MAISON_CONSUMER_ROOT or the current directory)",
    )
    return result


def main() -> int:
    arguments = parser().parse_args()
    try:
        results = validate_consumer(arguments.consumer)
    except ConsumerValidationError as error:
        print(f"error: {error.check}: {error.message}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"error: repository: {error}", file=sys.stderr)
        return 1

    for result in results:
        print(f"[ok] {result.name}: {result.detail}")
    print(f"consumer validation passed: {arguments.consumer.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
