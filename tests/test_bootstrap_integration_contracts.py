from __future__ import annotations

import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

from tests.support.topology import *

LUME_TASK = ROOT / ".mise/tasks/test/lume/install"
LUME_VERSION = "0.5.1"
LUME_SHA256 = "7f10cfbe66a800f98a5db88129f7dc024600fcdc139e0be124845bc7a3dc1359"


class HiddenBootstrapTaskSurfaceTest(unittest.TestCase):
    def command_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "MAISON_HOME": str(ROOT),
                "MISE_PROJECT_ROOT": str(ROOT),
                "MAISON_CLI_STATE_ACTIVE": "true",
            }
        )
        return environment

    def run_cli(self, *arguments: str):
        return run(
            [str(ROOT / "bin/maison"), *arguments],
            cwd=Path(tempfile.gettempdir()),
            env=self.command_environment(),
            capture_output=True,
            text=True,
        )

    def test_lume_task_is_hidden_but_directly_discoverable_by_mise(self) -> None:
        task = LUME_TASK.read_text()
        self.assertIn("#MISE hide=true", task)
        lume_contract = (ROOT / ".mise/lib/lume.sh").read_text()
        self.assertIn("lume-v0.5.1", lume_contract)
        self.assertIn("lume-0.5.1-darwin-arm64.tar.gz", lume_contract)
        self.assertIn("https://github.com/trycua/cua/releases/download/lume-v0.5.1/", lume_contract)
        self.assertIn(LUME_SHA256, lume_contract)
        self.assertIn("XDG_DATA_HOME", lume_contract)
        hidden = run(
            ["mise", "-C", str(ROOT), "tasks", "--name-only", "--hidden"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(hidden.returncode, 0, hidden.stderr)
        self.assertIn("test:lume:install", hidden.stdout.splitlines())
        public = run(
            ["mise", "-C", str(ROOT), "tasks", "--name-only"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(public.returncode, 0, public.stderr)
        self.assertNotIn("test:lume:install", public.stdout.splitlines())

    def test_maison_surface_hides_test_tasks_everywhere(self) -> None:
        for arguments in ((), ("--help",), ("help",)):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("test:", result.stdout)
                self.assertNotIn("test:lume:install", result.stdout)

        for arguments in (("__task-names",), ("__command-paths",), ("completion", "bash")):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("test:", result.stdout)
                self.assertNotIn("test:lume:install", result.stdout)

        unknown = self.run_cli("test", "lume", "install")
        self.assertNotEqual(unknown.returncode, 0)
        self.assertIn("unknown command", unknown.stderr)

    def test_maison_tasks_rejects_flags_and_lists_only_public_names(self) -> None:
        listing = self.run_cli("tasks")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn("bootstrap", listing.stdout)
        self.assertNotIn("test:", listing.stdout)
        self.assertNotIn("test:lume:install", listing.stdout)

        for arguments in (("--hidden",), ("--all",), ("--name-only",)):
            with self.subTest(arguments=arguments):
                result = self.run_cli("tasks", *arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("usage: maison tasks", result.stderr)


class LumeInstallerContractTest(unittest.TestCase):
    def write_fake_tools(self, root: Path) -> Path:
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        executable(
            fake_bin / "uname",
            """#!/bin/sh
set -eu
case "${1:-}" in
  -s) printf '%s\\n' "${FAKE_UNAME_S:-Darwin}" ;;
  -m) printf '%s\\n' "${FAKE_UNAME_M:-arm64}" ;;
  *) printf '%s\\n' "${FAKE_UNAME_S:-Darwin}" ;;
esac
""",
        )
        executable(
            fake_bin / "sw_vers",
            """#!/bin/sh
set -eu
if [ "${1:-}" = "-productVersion" ]; then
  printf '%s\\n' "${FAKE_MACOS_VERSION:-13.0}"
else
  exit 1
fi
""",
        )
        executable(
            fake_bin / "curl",
            """#!/bin/sh
set -eu
output=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output|-o) output="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[ -n "$output" ]
printf '%s\\n' "$output" >>"$LUME_CURL_LOG"
[ "${LUME_CURL_SLEEP:-0}" = 0 ] || sleep "$LUME_CURL_SLEEP"
cp "$LUME_FIXTURE_ARCHIVE" "$output"
""",
        )
        executable(
            fake_bin / "shasum",
            """#!/bin/sh
set -eu
case "${LUME_CHECKSUM_RESULT:-match}" in
  match) digest="7f10cfbe66a800f98a5db88129f7dc024600fcdc139e0be124845bc7a3dc1359" ;;
  *) digest="0000000000000000000000000000000000000000000000000000000000000000" ;;
esac
printf '%s  %s\\n' "$digest" "${2:-${1:-}}"
""",
        )
        return fake_bin

    def make_archive(self, root: Path) -> Path:
        payload = root / "lume"
        executable(
            payload,
            """#!/bin/sh
exec "$(dirname "$0")/lume.app/Contents/MacOS/lume" "$@"
""",
        )
        app_binary = root / "lume.app/Contents/MacOS/lume"
        executable(
            app_binary,
            """#!/bin/sh
if [ "${1:-}" = "--version" ]; then
  printf 'lume 0.5.1\\n'
else
  printf 'fake lume\\n'
fi
""",
        )
        archive = root / "lume.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            handle.add(payload, arcname="lume")
            handle.add(root / "lume.app", arcname="lume.app")
        return archive

    def installer_environment(self, root: Path, archive: Path, fake_bin: Path) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(root / "home"),
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_STATE_HOME": str(root / "state"),
                "TMPDIR": str(root / "tmp"),
                "MISE_PROJECT_ROOT": str(ROOT),
                "LUME_FIXTURE_ARCHIVE": str(archive),
                "LUME_CURL_LOG": str(root / "curl.log"),
                "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
            }
        )
        (root / "tmp").mkdir()
        return environment

    def run_installer(self, environment: dict[str, str]):
        return run(
            ["bash", str(LUME_TASK)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def install_path(self, environment: dict[str, str]) -> Path:
        return Path(environment["XDG_DATA_HOME"]) / "maison/lume/0.5.1/lume"

    def test_installs_pinned_archive_atomically_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_archive(root)
            fake_bin = self.write_fake_tools(root)
            environment = self.installer_environment(root, archive, fake_bin)

            first = self.run_installer(environment)
            self.assertEqual(first.returncode, 0, first.stderr)
            installed = self.install_path(environment)
            self.assertTrue(installed.is_file())
            self.assertTrue(installed.stat().st_mode & 0o777 == 0o700)
            self.assertTrue((installed.parent / "lume.app/Contents/MacOS/lume").is_file())
            self.assertEqual(
                subprocess.run(
                    [str(installed), "--version"], capture_output=True, text=True, check=False
                ).stdout.strip(),
                "lume 0.5.1",
            )
            self.assertIn(str(installed), first.stdout)
            self.assertEqual(len((root / "curl.log").read_text().splitlines()), 1)

            second = self.run_installer(environment)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(len((root / "curl.log").read_text().splitlines()), 1)
            self.assertEqual(list((root / "tmp").iterdir()), [])

    def test_rejects_bad_checksum_without_installing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_archive(root)
            fake_bin = self.write_fake_tools(root)
            environment = self.installer_environment(root, archive, fake_bin)
            environment["LUME_CHECKSUM_RESULT"] = "mismatch"

            result = self.run_installer(environment)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checksum", result.stderr.lower())
            self.assertFalse(self.install_path(environment).exists())

    def test_rejects_incompatible_existing_install_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_archive(root)
            fake_bin = self.write_fake_tools(root)
            environment = self.installer_environment(root, archive, fake_bin)
            installed = self.install_path(environment)
            installed.parent.mkdir(parents=True, mode=0o700)
            executable(
                installed,
                """#!/bin/sh
printf 'lume 0.4.0\\n'
""",
            )

            result = self.run_installer(environment)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("incompatible", result.stderr.lower())
            self.assertFalse((root / "curl.log").exists())

    def test_serializes_concurrent_installers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_archive(root)
            fake_bin = self.write_fake_tools(root)
            environment = self.installer_environment(root, archive, fake_bin)
            environment["LUME_CURL_SLEEP"] = "0.3"
            processes = [
                start_process(
                    ["bash", str(LUME_TASK)],
                    cwd=ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(2)
            ]
            results = [process.communicate(timeout=30) for process in processes]
            self.assertEqual([process.returncode for process in processes], [0, 0], results)
            self.assertEqual(len((root / "curl.log").read_text().splitlines()), 1)

    def test_rejects_non_apple_silicon_hosts_before_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_archive(root)
            fake_bin = self.write_fake_tools(root)
            environment = self.installer_environment(root, archive, fake_bin)
            environment["FAKE_UNAME_S"] = "Linux"

            result = self.run_installer(environment)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Apple Silicon macOS", result.stderr)
            self.assertFalse((root / "curl.log").exists())


if __name__ == "__main__":
    unittest.main()
