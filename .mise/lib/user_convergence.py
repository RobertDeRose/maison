from __future__ import annotations

import argparse
import filecmp
import json
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import tomllib

Mode = Literal["plan", "apply", "recovery"]
PACKAGE_PHASES = frozenset({"not-started", "started", "completed", "failed", "unknown"})
RECOVERY_STATUSES = frozenset({"succeeded", "failed", "skipped"})


@dataclass(frozen=True)
class Command:
    name: str
    argv: tuple[str, ...]
    cwd: Path
    env: dict[str, str]
    dry_run: bool
    semantic_action: str
    semantic_arguments: tuple[str, ...] = ()
    documented_substitution: bool = False
    quiet: bool = False


@dataclass(frozen=True)
class CommandPlan:
    mode: Mode
    force_dotfiles: bool
    convergence_commands: tuple[Command, ...]
    apply_only_commands: tuple[Command, ...] = ()

    def command(self, name: str) -> Command:
        for command in (*self.convergence_commands, *self.apply_only_commands):
            if command.name == name:
                return command
        raise KeyError(name)


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            os.chmod(temporary.name, 0o600)
            json.dump(payload, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        assert temporary_name is not None
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _read_events(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(value, list):
        return []
    return [event for event in value if isinstance(event, dict)]


def _record_event(
    path: Path | None,
    *,
    mode: Mode,
    phase: str,
    status: str,
    exit_code: int | None = None,
) -> None:
    if path is None:
        return
    event: dict[str, Any] = {"mode": mode, "phase": phase, "status": status}
    if exit_code is not None:
        event["exit_code"] = exit_code
    _atomic_write_json(path, [*_read_events(path), event])


def _package_phase(events: list[dict[str, Any]], event_file: Path | None = None) -> str:
    initial_events = [event for event in events if event.get("mode") == "apply"]
    package_events = [event for event in initial_events if event.get("phase") == "packages"]
    if not package_events:
        return "unknown" if event_file is not None and event_file.is_file() and not initial_events else "not-started"
    status = package_events[-1].get("status")
    if status == "completed":
        return "completed"
    if status == "failed":
        return "failed"
    if status == "started":
        return "started"
    return "unknown"


def _recovery_steps(events: list[dict[str, Any]]) -> list[str]:
    steps: list[str] = []
    for event in events:
        if event.get("mode") == "recovery" and event.get("status") == "started":
            phase = event.get("phase")
            if isinstance(phase, str) and phase not in steps:
                steps.append(phase)
    return steps


def build_recovery_report(
    *,
    failed_revision: str,
    restored_revision: str,
    initial_exit_code: int,
    package_phase: str,
    recovery_status: str,
    recovery_exit_code: int | None,
    recovery_steps: tuple[str, ...] | list[str],
    force_dotfiles: bool,
) -> dict[str, Any]:
    if package_phase not in PACKAGE_PHASES:
        raise ValueError(f"unsupported package phase: {package_phase}")
    if recovery_status not in RECOVERY_STATUSES:
        raise ValueError(f"unsupported recovery status: {recovery_status}")
    return {
        "schema_version": 1,
        "kind": "remote-convergence-recovery",
        "failed_revision": failed_revision,
        "restored_revision": restored_revision,
        "initial_convergence": {
            "status": "failed",
            "exit_code": initial_exit_code,
            "package_phase": package_phase,
        },
        "recovery": {
            "status": recovery_status,
            "exit_code": recovery_exit_code,
            "steps": list(recovery_steps),
            "force_dotfiles": force_dotfiles,
        },
        "external_side_effects": {
            "package_app": {
                "status": package_phase,
                "rollback": "not-attempted",
                "follow_up": package_phase != "not-started",
            }
        },
    }


def write_recovery_report(path: Path, report: dict[str, Any]) -> None:
    _atomic_write_json(path, report)


def aggregate_user_arguments(*, force_dotfiles: bool) -> tuple[str, ...]:
    return ("--force-dotfiles",) if force_dotfiles else ()


def _configuration_path(root: Path) -> Path:
    return root / "config/mise/config.toml"


def build_command_plan(
    *,
    mode: Mode,
    force_dotfiles: bool,
    root: Path,
    home: Path,
) -> CommandPlan:
    root = root.resolve()
    home = home.resolve()
    dry_run = mode == "plan"
    recovery = mode == "recovery"
    force_arguments = aggregate_user_arguments(force_dotfiles=force_dotfiles)
    execution_argument = "--dry-run" if dry_run else "--yes"
    prepare_arguments = (
        ("--recovery", *force_arguments)
        if recovery
        else ((execution_argument, *force_arguments) if dry_run else force_arguments)
    )
    mise_environment = {
        "MISE_AUTO_ENV": "true",
        "MISE_GLOBAL_CONFIG_FILE": str(_configuration_path(root)),
        "MAISON_CONSUMER_ROOT": str(root),
    }
    framework_root = Path(os.environ.get("MAISON_HOME", root)).expanduser().resolve()
    prepare_script = framework_root / "scripts/user-prepare.sh"
    prepare_environment = dict(mise_environment)
    if framework_root != root:
        prepare_environment["MAISON_USER_PREPARE_ROOT"] = str(root)
    if recovery:
        if override := os.environ.get("MAISON_RECOVERY_PREPARE_SCRIPT"):
            prepare_script = Path(override)
        prepare_environment["MAISON_USER_PREPARE_ROOT"] = str(root)
    prepare = Command(
        name="prepare",
        argv=(str(prepare_script), *prepare_arguments),
        cwd=root,
        env=prepare_environment,
        dry_run=dry_run,
        semantic_action="prepare-dotfiles",
        semantic_arguments=force_arguments,
    )
    dotfiles = Command(
        name="dotfiles",
        argv=("mise", "bootstrap", "--only", "dotfiles", execution_argument, *force_arguments),
        cwd=root,
        env=mise_environment,
        dry_run=dry_run,
        semantic_action="converge-dotfiles",
        semantic_arguments=force_arguments,
    )
    lockfiles = Command(
        name="lockfiles",
        argv=(
            str(framework_root / "scripts/user-link-mise-lock.sh"),
            *(("--dry-run",) if dry_run else ()),
        ),
        cwd=root,
        env=mise_environment,
        dry_run=dry_run,
        semantic_action="link-mise-lockfiles",
    )
    mise = Command(
        name="mise",
        argv=(
            "mise",
            "bootstrap",
            "--skip",
            "task",
            "--skip",
            "packages",
            "--skip",
            "dotfiles",
            execution_argument,
            *force_arguments,
        ),
        cwd=home,
        env=mise_environment,
        dry_run=dry_run,
        semantic_action="converge-mise-user-state",
        semantic_arguments=force_arguments,
    )
    if recovery:
        commands = (prepare, dotfiles, lockfiles, mise)
    else:
        commands = (
            prepare,
            dotfiles,
            lockfiles,
            Command(
                name="packages",
                argv=(
                    ("mise", "bootstrap", "packages", "apply", "--dry-run")
                    if dry_run
                    else (str(framework_root / "scripts/user-apply-packages.sh"),)
                ),
                cwd=home,
                env=mise_environment,
                dry_run=dry_run,
                semantic_action="converge-packages",
                documented_substitution=True,
            ),
            mise,
        )
    apply_only = ()
    if mode in {"apply", "recovery"}:
        apply_only = (
            Command(
                name="trust",
                argv=("mise", "trust", str(framework_root / "mise.toml")),
                cwd=framework_root,
                env={},
                dry_run=False,
                semantic_action="trust-repository-config",
                documented_substitution=True,
                quiet=True,
            ),
            Command(
                name="finalize",
                argv=(str(framework_root / "scripts/user-finalize.sh"),),
                cwd=root,
                env={},
                dry_run=False,
                semantic_action="finalize-user-convergence",
                documented_substitution=True,
            ),
        )
    return CommandPlan(mode, force_dotfiles, commands, apply_only)


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


FileSignature = tuple[int, int, int, int, int]


@dataclass
class _ComparisonCache:
    file_entries: dict[Path, tuple[FileSignature, frozenset[Path]]]
    file_comparisons: dict[tuple[Path, Path], tuple[FileSignature, FileSignature, bool]]

    def __init__(self) -> None:
        self.file_entries = {}
        self.file_comparisons = {}


def _expand_user_path(value: str, home: Path) -> Path:
    if value == "~":
        return home
    if value.startswith("~/"):
        return home / value[2:]
    return Path(value).expanduser()


def _file_signature(path: Path) -> FileSignature:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _file_entries(directory: Path, cache: _ComparisonCache) -> frozenset[Path]:
    signature = _file_signature(directory)
    cached = cache.file_entries.get(directory)
    if cached is not None and cached[0] == signature:
        return cached[1]
    entries = frozenset(path.relative_to(directory) for path in directory.rglob("*") if path.is_file())
    cache.file_entries[directory] = (signature, entries)
    return entries


def _files_equal(left: Path, right: Path, cache: _ComparisonCache) -> bool:
    left_signature = _file_signature(left)
    right_signature = _file_signature(right)
    if left_signature[:2] == right_signature[:2]:
        return True
    key = (left, right)
    cached = cache.file_comparisons.get(key)
    if cached is not None and cached[:2] == (left_signature, right_signature):
        return cached[2]
    equal = filecmp.cmp(left, right, shallow=False)
    cache.file_comparisons[key] = (left_signature, right_signature, equal)
    return equal


def _paths_equal(left: Path, right: Path, cache: _ComparisonCache | None = None) -> bool:
    comparison_cache = cache if cache is not None else _ComparisonCache()
    if left.is_dir() or right.is_dir():
        if not left.is_dir() or not right.is_dir():
            return False
        left_entries = _file_entries(left, comparison_cache)
        right_entries = _file_entries(right, comparison_cache)
        if left_entries != right_entries:
            return False
        return all(_files_equal(left / path, right / path, comparison_cache) for path in left_entries)
    return left.is_file() and right.is_file() and _files_equal(left, right, comparison_cache)


def _dotfile_status(
    target: Path,
    source: Path,
    mode: str,
    comparison_cache: _ComparisonCache | None = None,
) -> str:
    if not source.exists():
        return "source missing"
    if mode == "symlink":
        if target.is_symlink() and target.resolve() == source:
            return "applied"
        return "missing" if not _path_exists(target) else "differs"
    if mode == "symlink-each":
        if not target.is_dir():
            return "missing" if not _path_exists(target) else "differs"
        source_entries = {path.name for path in source.iterdir()}
        if all(
            (target / name).is_symlink() and (target / name).resolve() == (source / name).resolve()
            for name in source_entries
        ):
            return "applied"
        return "differs"
    if not _path_exists(target):
        return "missing"
    if mode == "template":
        return "present"
    return "applied" if _paths_equal(target, source, comparison_cache) else "differs"


def _iter_dotfile_mappings(configuration_root: Path, home: Path) -> list[tuple[str, Path, Path, str]]:
    mappings: list[tuple[str, Path, Path, str]] = []
    config_root = configuration_root / "config/mise"
    for config in sorted(config_root.glob("*.toml")):
        data = tomllib.loads(config.read_text(encoding="utf-8"))
        dotfiles = data.get("dotfiles", {})
        if not isinstance(dotfiles, dict):
            continue
        for target, entry in dotfiles.items():
            if not isinstance(target, str) or not isinstance(entry, dict):
                continue
            source_value = entry.get("source")
            mode = entry.get("mode", "symlink")
            if isinstance(source_value, str) and isinstance(mode, str):
                mappings.append((target, config.parent / source_value, _expand_user_path(target, home), mode))
    return mappings


def run_user_status(
    *,
    root: Path,
    home: Path,
    runner: Any = subprocess.run,
) -> None:
    plan = build_command_plan(mode="plan", force_dotfiles=False, root=root, home=home)
    environment = os.environ.copy()
    environment.update(plan.command("mise").env)
    configuration_root = root.resolve()
    status = runner(
        ("mise", "bootstrap", "status"),
        cwd=root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    aggregate_output = getattr(status, "stdout", "")
    if aggregate_output:
        print("\n".join(line for line in aggregate_output.splitlines() if not line.startswith("dotfiles ")))
    comparison_cache = _ComparisonCache()
    for target_name, source, target, mode in _iter_dotfile_mappings(configuration_root, home):
        print(
            f"dotfiles {target_name:<55} {mode:<12} "
            f"{source.resolve()} {_dotfile_status(target, source.resolve(), mode, comparison_cache)}"
        )


def _commands_for_execution(plan: CommandPlan) -> tuple[Command, ...]:
    if plan.mode in {"apply", "recovery"}:
        return (*plan.apply_only_commands[:1], *plan.convergence_commands, *plan.apply_only_commands[1:])
    return plan.convergence_commands


def _print_command_plan(plan: CommandPlan) -> None:
    for command in _commands_for_execution(plan):
        print(f"[plan] {command.name}: {shlex.join(command.argv)}")


def run_command_plan(plan: CommandPlan, *, event_file: Path | None = None) -> None:
    if plan.mode == "plan":
        _print_command_plan(plan)
        return

    for command in _commands_for_execution(plan):
        environment = os.environ.copy()
        environment.update(command.env)
        stdout = subprocess.DEVNULL if command.quiet else None
        _record_event(event_file, mode=plan.mode, phase=command.name, status="started")
        try:
            subprocess.run(command.argv, cwd=command.cwd, env=environment, check=True, stdout=stdout)
        except subprocess.CalledProcessError as error:
            _record_event(
                event_file,
                mode=plan.mode,
                phase=command.name,
                status="failed",
                exit_code=error.returncode,
            )
            raise
        except OSError:
            _record_event(event_file, mode=plan.mode, phase=command.name, status="failed", exit_code=127)
            raise
        _record_event(event_file, mode=plan.mode, phase=command.name, status="completed")


def _write_recovery_result(
    *,
    report_path: Path,
    event_file: Path | None,
    failed_revision: str,
    restored_revision: str,
    initial_exit_code: int,
    recovery_status: str,
    recovery_exit_code: int | None,
    force_dotfiles: bool,
) -> None:
    events = _read_events(event_file)
    report = build_recovery_report(
        failed_revision=failed_revision,
        restored_revision=restored_revision,
        initial_exit_code=initial_exit_code,
        package_phase=(
            _package_phase(events, event_file) if event_file is not None and event_file.is_file() else "unknown"
        ),
        recovery_status=recovery_status,
        recovery_exit_code=recovery_exit_code,
        recovery_steps=_recovery_steps(events),
        force_dotfiles=force_dotfiles,
    )
    write_recovery_report(report_path, report)
    if event_file is not None:
        try:
            event_file.unlink(missing_ok=True)
        except OSError:
            pass
    print(f"Recovery report: {report_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Maison user convergence")
    parser.add_argument("mode", choices=("plan", "apply", "recovery", "status"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--force-dotfiles", action="store_true")
    parser.add_argument("--event-file", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--failed-revision")
    parser.add_argument("--restored-revision")
    parser.add_argument("--initial-exit-code", type=int)
    arguments = parser.parse_args()
    event_file = arguments.event_file or (
        Path(os.environ["MAISON_CONVERGENCE_EVENT_FILE"]) if os.environ.get("MAISON_CONVERGENCE_EVENT_FILE") else None
    )
    if arguments.mode == "status":
        run_user_status(root=arguments.root, home=Path.home())
        return 0

    plan = build_command_plan(
        mode=arguments.mode,
        force_dotfiles=arguments.force_dotfiles,
        root=arguments.root,
        home=Path.home(),
    )
    if arguments.mode != "recovery":
        run_command_plan(plan, event_file=event_file)
        return 0

    required = {
        "--report": arguments.report,
        "--failed-revision": arguments.failed_revision,
        "--restored-revision": arguments.restored_revision,
        "--initial-exit-code": arguments.initial_exit_code,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error(f"recovery requires {', '.join(missing)}")
    assert arguments.report is not None
    assert arguments.failed_revision is not None
    assert arguments.restored_revision is not None
    assert arguments.initial_exit_code is not None
    try:
        run_command_plan(plan, event_file=event_file)
    except subprocess.CalledProcessError as error:
        _write_recovery_result(
            report_path=arguments.report,
            event_file=event_file,
            failed_revision=arguments.failed_revision,
            restored_revision=arguments.restored_revision,
            initial_exit_code=arguments.initial_exit_code,
            recovery_status="failed",
            recovery_exit_code=error.returncode,
            force_dotfiles=arguments.force_dotfiles,
        )
        return error.returncode
    except OSError as error:
        print(f"recovery command failed: {error}", file=sys.stderr)
        _write_recovery_result(
            report_path=arguments.report,
            event_file=event_file,
            failed_revision=arguments.failed_revision,
            restored_revision=arguments.restored_revision,
            initial_exit_code=arguments.initial_exit_code,
            recovery_status="failed",
            recovery_exit_code=127,
            force_dotfiles=arguments.force_dotfiles,
        )
        return 127
    _write_recovery_result(
        report_path=arguments.report,
        event_file=event_file,
        failed_revision=arguments.failed_revision,
        restored_revision=arguments.restored_revision,
        initial_exit_code=arguments.initial_exit_code,
        recovery_status="succeeded",
        recovery_exit_code=0,
        force_dotfiles=arguments.force_dotfiles,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
