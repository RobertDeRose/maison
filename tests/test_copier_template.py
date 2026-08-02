from __future__ import annotations

import platform

from tests.support.topology import *


class CopierTemplateTest(unittest.TestCase):
    TEMPLATE = ROOT / "examples/terroir"

    @classmethod
    def render(cls, destination: Path) -> None:
        if shutil.which("uvx") is None:
            raise unittest.SkipTest("uvx is required to render the Copier template")
        result = run(
            [
                "uvx",
                "--from",
                "copier",
                "copier",
                "copy",
                "--trust",
                "--quiet",
                "--defaults",
                "--skip-tasks",
                "--data",
                "username=operator",
                "--data",
                "full_name=Example Operator",
                "--data",
                "email=operator@example.invalid",
                "--data",
                "github=example-user",
                str(cls.TEMPLATE),
                str(destination),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(f"Copier rendering failed:\nstdout={result.stdout}\nstderr={result.stderr}")

    def test_template_renders_valid_private_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "overlay"
            self.render(destination)
            with (destination / "inventory.toml").open("rb") as handle:
                inventory = tomllib.load(handle)
            self.assertEqual(inventory["defaults"]["user"], "operator")
            self.assertEqual(inventory["users"]["operator"]["email"], "operator@example.invalid")
            self.assertFalse((destination / "copier.yml").exists())
            self.assertTrue((destination / ".copier-answers.yml").is_file())
            self.assertTrue((destination / "scripts/add-current-host.sh").stat().st_mode & stat.S_IXUSR)
            self.assertFalse((destination / "inventory.toml.jinja").exists())

    def test_first_copy_host_task_delegates_to_maison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            destination = temp / "overlay"
            self.render(destination)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            task_log = temp / "task.log"
            executable(
                fake_bin / "mise",
                '#!/bin/sh\nprintf \'%s\\n\' "$*" >"$MAISON_TASK_LOG"\n',
            )
            expected_system = {
                ("Darwin", "arm64"): "aarch64-darwin",
                ("Darwin", "aarch64"): "aarch64-darwin",
                ("Linux", "arm64"): "aarch64-linux",
                ("Linux", "aarch64"): "aarch64-linux",
                ("Linux", "x86_64"): "x86_64-linux",
                ("Linux", "amd64"): "x86_64-linux",
            }.get((platform.system(), platform.machine()))
            if expected_system is None:
                self.skipTest("test host is outside Maison's supported platform matrix")
            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                    "MAISON_HOME": str(ROOT),
                    "MAISON_OVERLAY_PATH": str(destination),
                    "MAISON_HOST": "fixture-host",
                    "MAISON_TASK_LOG": str(task_log),
                    "USERNAME": "operator",
                }
            )
            result = run(
                ["bash", str(destination / "scripts/add-current-host.sh")],
                cwd=destination,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((destination / ".git").is_dir())
            self.assertEqual(
                task_log.read_text().strip(),
                f"-C {ROOT} run host:add -- fixture-host --system {expected_system} --user operator",
            )

    def test_host_task_rejects_unsupported_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            destination = temp / "overlay"
            self.render(destination)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            executable(fake_bin / "mise", "#!/bin/sh\nexit 0\n")
            executable(fake_bin / "uname", "#!/bin/sh\nprintf 'FreeBSD\\n'")
            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                    "MAISON_HOME": str(ROOT),
                    "USERNAME": "operator",
                }
            )
            result = run(
                ["bash", str(destination / "scripts/add-current-host.sh")],
                cwd=destination,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported platform", result.stderr)


if __name__ == "__main__":
    unittest.main()
