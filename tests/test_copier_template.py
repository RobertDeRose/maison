from __future__ import annotations

from tests.support.topology import *


class CopierTemplateTest(unittest.TestCase):
    TEMPLATE = ROOT / "overlay_template"

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

    def test_template_renders_a_consumer_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "consumer"
            self.render(destination)
            with (destination / "inventory.toml").open("rb") as handle:
                inventory = tomllib.load(handle)
            self.assertEqual(inventory["defaults"]["user"], "operator")
            self.assertEqual(inventory["users"]["operator"]["email"], "operator@example.invalid")
            for name in ("flake.nix", "README.md", "config/mise/config.toml", "hosts/.gitkeep"):
                self.assertTrue((destination / name).is_file(), name)
            self.assertFalse((destination / "copier.yml").exists())
            self.assertTrue((destination / ".copier-answers.yml").is_file())
            self.assertTrue((destination / "scripts/add-current-host.sh").stat().st_mode & stat.S_IXUSR)
            self.assertFalse((destination / "inventory.toml.jinja").exists())
            flake = (destination / "flake.nix").read_text()
            self.assertIn("maison.lib.mkDarwinSystem", flake)
            self.assertIn("maison.lib.mkSystemManagerSystem", flake)
            self.assertNotIn("MAISON_OVERLAY", flake)

    def test_first_copy_host_task_delegates_to_consumer_host_add(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            destination = temp / "consumer"
            self.render(destination)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            task_log = temp / "task.log"
            executable(
                fake_bin / "mise",
                '#!/bin/sh\nprintf \'%s\\n\' "$*" >"$MAISON_TASK_LOG"\n',
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                    "MAISON_HOME": str(ROOT),
                    "MAISON_CONSUMER_ROOT": str(destination),
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
            self.assertFalse((destination / "flake.lock").exists())
            self.assertEqual(
                task_log.read_text().strip(),
                f"-C {ROOT} run host:add -- fixture-host --user operator",
            )

    def test_bootstrap_documents_fresh_consumer_setup(self) -> None:
        bootstrap = read("bootstrap.sh")
        self.assertIn("--setup PATH", bootstrap)
        self.assertIn("overlay_template", bootstrap)
        self.assertIn("nix flake lock", bootstrap)
        self.assertIn("MAISON_CONSUMER_ROOT", bootstrap)
        self.assertNotIn("MAISON_OVERLAY_PATH", bootstrap)

    def test_bootstrap_pins_a_rendered_consumer_before_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source = temp / "source"
            source.mkdir()
            copy_files(source, "mise.toml", "flake.nix", "bootstrap.sh")
            shutil.copytree(ROOT / ".mise", source / ".mise")
            shutil.copytree(ROOT / "overlay_template", source / "overlay_template")
            git_init(source)
            git_commit_all(source)
            home = temp / "home"
            home.mkdir()
            destination = temp / "consumer"
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "bootstrap.log"
            executable(
                fake_bin / "mise",
                """#!/bin/sh
printf 'mise %s\\n' "$*" >>"$BOOTSTRAP_LOG"
case "$*" in
  *'exec --locked uv -- uvx'*)
    mkdir -p "$MAISON_CONSUMER_ROOT/.git" "$MAISON_CONSUMER_ROOT/hosts"
    : >"$MAISON_CONSUMER_ROOT/flake.nix"
    : >"$MAISON_CONSUMER_ROOT/inventory.toml"
    ;;
esac
""",
            )
            executable(
                fake_bin / "nix",
                """#!/bin/sh
printf 'nix %s\\n' "$*" >>"$BOOTSTRAP_LOG"
if [ "$1" = --version ]; then echo 'nix 2.0'; exit 0; fi
if [ "$1" = flake ] && [ "$2" = lock ]; then
  target="${3#path:}"
  : >"$target/flake.lock"
fi
""",
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": str(home),
                    "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                    "BOOTSTRAP_LOG": str(log),
                }
            )
            result = run(
                [
                    str(ROOT / "bootstrap.sh"),
                    "--repo",
                    str(source),
                    "--ref",
                    "main",
                    "--setup",
                    str(destination),
                    "--host",
                    "fixture-host",
                ],
                cwd=temp,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((destination / "flake.lock").is_file())
            calls = log.read_text()
            self.assertIn("exec --locked uv -- uvx", calls)
            self.assertIn("flake lock ", calls)
            self.assertNotIn("run --skip-tools bootstrap", calls)
            self.assertIn("Fresh consumer created", result.stdout)
            self.assertIn("No Nix system or user activation", result.stdout)


if __name__ == "__main__":
    unittest.main()
