from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from tests.support.topology import *


class ConsumerRepositoryContractTest(unittest.TestCase):
    def make_consumer(self, root: Path, host: str = "example-linux") -> Path:
        consumer = root / "consumer"
        consumer.mkdir()
        (consumer / "flake.nix").write_text("{ outputs = _: {}; }\n")
        (consumer / "flake.lock").write_text('{"nodes": {}}\n')
        (consumer / "inventory.toml").write_text(
            f"""schema = 1

[users.operator]
username = "operator"
full_name = "Example Operator"
email = "operator@example.invalid"
github = "example-operator"

[hosts.{host}]
system = "aarch64-linux"
user = "operator"
profiles = ["base", "dev", "linux"]
"""
        )
        git_init(consumer)
        return consumer

    def task_environment(self, consumer: Path, fake_bin: Path | None = None) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "MAISON_HOME": str(ROOT),
                "MAISON_CONSUMER_ROOT": str(consumer),
                "MISE_PROJECT_ROOT": str(ROOT),
            }
        )
        if fake_bin is not None:
            environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
        return environment

    def test_maison_and_consumer_roots_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            consumer = self.make_consumer(Path(directory))
            result = run(
                [
                    "bash",
                    "-c",
                    (
                        f"source {ROOT}/.mise/lib/common.sh; "
                        "printf '%s\\n' \"$(maison_install_root)\"; "
                        "printf '%s\\n' \"$(maison_consumer_root)\""
                    ),
                ],
                cwd=ROOT,
                env=self.task_environment(consumer),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [str(ROOT), str(consumer.resolve())])

    def test_host_listing_reads_the_consumer_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            consumer = self.make_consumer(Path(directory))
            result = run(
                ["bash", str(ROOT / ".mise/tasks/host/list")],
                cwd=ROOT,
                env=self.task_environment(consumer),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("example-linux", result.stdout)
            self.assertNotIn("example-darwin", result.stdout)

    def test_system_plan_uses_the_consumer_flake_directly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "nix.log"
            executable(
                fake_bin / "nix",
                """#!/bin/sh
printf '%s|%s\\n' "$PWD" "$*" >>"$NIX_LOG"
output=""
previous=""
for argument in "$@"; do
  if [ "$previous" = --out-link ]; then output="$argument"; fi
  previous="$argument"
done
if [ -n "$output" ]; then mkdir -p "$(dirname "$output")"; : >"$output"; fi
""",
            )
            environment = self.task_environment(consumer, fake_bin)
            environment.update({"NIX_LOG": str(log), "usage_host": "example-linux"})
            result = run(
                ["bash", str(ROOT / ".mise/tasks/system/plan")],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = log.read_text().splitlines()
            self.assertTrue(lines)
            self.assertTrue(lines[-1].startswith(f"{consumer.resolve()}|"))
            self.assertIn(f'{consumer.resolve()}#systemConfigs."example-linux"', lines[-1])
            self.assertNotIn("--override-input", lines[-1])
            self.assertNotIn("path:", lines[-1])
            self.assertTrue((consumer / ".build/system-example-linux").exists())

    def test_update_replaces_only_the_consumer_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            maison_lock = (ROOT / "flake.lock").read_text()
            consumer_lock = consumer / "flake.lock"
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "nix.log"
            executable(
                fake_bin / "nix",
                """#!/bin/sh
printf '%s|%s\\n' "$PWD" "$*" >>"$NIX_LOG"
output=""
previous=""
for argument in "$@"; do
  if [ "$previous" = --output-lock-file ]; then output="$argument"; fi
  previous="$argument"
done
printf '%s\\n' '{"nodes": {"updated": true}}' >"$output"
""",
            )
            environment = self.task_environment(consumer, fake_bin)
            environment.update(
                {
                    "NIX_LOG": str(log),
                    "XDG_STATE_HOME": str(temp / "state"),
                    "MAISON_NIX_UPDATE_ATTEMPTS": "1",
                }
            )
            result = run(
                ["bash", str(ROOT / ".mise/tasks/update")],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((ROOT / "flake.lock").read_text(), maison_lock)
            self.assertEqual(json.loads(consumer_lock.read_text()), {"nodes": {"updated": True}})
            self.assertTrue(log.read_text().startswith(f"{consumer.resolve()}|"))

    def test_consumer_required_files_cannot_be_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            consumer = self.make_consumer(Path(directory))
            (consumer / "flake.lock").unlink()
            (consumer / "flake.lock").symlink_to(ROOT / "flake.lock")
            result = run(
                [
                    "bash",
                    "-c",
                    (f"source {ROOT}/.mise/lib/common.sh; maison_consumer_root >/dev/null"),
                ],
                cwd=ROOT,
                env=self.task_environment(consumer),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("regular consumer file", result.stderr)


if __name__ == "__main__":
    unittest.main()
