from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tests.support.topology import *

HELPER = ROOT / ".mise/lib/consumer-integration.sh"
LINUX_TASKS = {
    "bootstrap": ROOT / ".mise/tasks/test/bootstrap/linux",
    "deploy": ROOT / ".mise/tasks/test/deploy",
    "image": ROOT / ".mise/tasks/test/image",
}


class LinuxIntegrationContractTest(unittest.TestCase):
    def test_linux_tasks_are_hidden_and_platform_explicit(self) -> None:
        hidden = run(
            ["mise", "-C", str(ROOT), "tasks", "--name-only", "--hidden"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(hidden.returncode, 0, hidden.stderr)
        for task_name in ("test:bootstrap:linux", "test:deploy", "test:image"):
            with self.subTest(task=task_name):
                self.assertIn(task_name, hidden.stdout.splitlines())

        public = run(
            ["mise", "-C", str(ROOT), "tasks", "--name-only"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(public.returncode, 0, public.stderr)
        self.assertFalse(any(name.startswith("test:") for name in public.stdout.splitlines()))
        self.assertNotIn("test:bootstrap", hidden.stdout.splitlines())

    def test_linux_tasks_use_the_framework_and_external_consumer(self) -> None:
        for name, path in LINUX_TASKS.items():
            with self.subTest(task=name):
                text = path.read_text()
                self.assertIn("# [MISE] quiet=true", "\n".join(text.splitlines()[:4]))
                self.assertIn("#MISE hide=true", text)
                self.assertIn("consumer-integration.sh", text)
                self.assertNotIn("terroir", text.lower())
                if name != "image":
                    self.assertIn("MAISON_CONSUMER_ROOT", text)

        bootstrap = LINUX_TASKS["bootstrap"].read_text()
        deploy = LINUX_TASKS["deploy"].read_text()
        image = LINUX_TASKS["image"].read_text()
        self.assertEqual(LINUX_TASKS["bootstrap"].name, "linux")
        self.assertIn("archive --format=tar", HELPER.read_text())
        self.assertIn("RobertDeRose/maison", HELPER.read_text())
        self.assertIn("bootstrap.sh", HELPER.read_text())
        self.assertIn("consumer_integration_build_image", image)
        self.assertIn("system-manager.target", bootstrap + deploy)
        self.assertIn("maison-runtime-verification.service", deploy)
        self.assertIn('bin/maison" deploy', deploy)

    def test_linux_deploy_does_not_copy_private_host_ssh_state_or_pipe_installers(self) -> None:
        deploy = LINUX_TASKS["deploy"].read_text()
        forbidden = (
            '"$HOME/.ssh/id_',
            '-v "$HOME/.ssh',
            "curl -sSfL https://mise.run |",
            "curl -fsSL https://raw.githubusercontent.com/Homebrew/install",
            "install.sh) |",
            "curl -sSfL https://install.lix.systems/lix |",
        )
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, deploy)
        self.assertIn("ssh-keygen", deploy)
        self.assertIn("authorized_key", deploy)
        self.assertIn("consumer_integration_fetch_framework_artifact", deploy)

    def test_locked_maison_ref_requires_public_github_node(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = "a" * 40
            (root / "flake.lock").write_text(
                json.dumps(
                    {
                        "nodes": {
                            "maison": {
                                "locked": {
                                    "type": "github",
                                    "owner": "RobertDeRose",
                                    "repo": "maison",
                                    "rev": valid,
                                }
                            }
                        }
                    }
                )
            )
            result = run(
                [
                    "bash",
                    "-c",
                    'source "$1"; consumer_integration_maison_ref "$2"',
                    "_",
                    str(HELPER),
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), valid)

            resolved = run(
                [
                    "bash",
                    "-c",
                    'source "$1"; consumer_integration_resolve_github_ref "$2"',
                    "_",
                    str(HELPER),
                    valid,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(resolved.returncode, 0, resolved.stderr)
            self.assertEqual(resolved.stdout.strip(), valid)

            invalid = run(
                [
                    "bash",
                    "-c",
                    'source "$1"; consumer_integration_resolve_github_ref "$2" token',
                    "_",
                    str(HELPER),
                    "feat/bad?ref",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("invalid Maison branch reference", invalid.stderr)

            locked = json.loads((root / "flake.lock").read_text())
            locked["nodes"]["maison"]["locked"]["owner"] = "untrusted"
            (root / "flake.lock").write_text(json.dumps(locked))
            rejected = run(
                [
                    "bash",
                    "-c",
                    'source "$1"; consumer_integration_maison_ref "$2"',
                    "_",
                    str(HELPER),
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("RobertDeRose", rejected.stderr)

    def test_stage_uses_committed_content_and_discards_private_source_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            consumer = root / "consumer"
            consumer.mkdir()
            (consumer / "flake.nix").write_text("{ outputs = _: {}; }\n")
            (consumer / "flake.lock").write_text('{"nodes": {}}\n')
            (consumer / "inventory.toml").write_text(
                'schema = 1\n\n[hosts.example]\nsystem = "aarch64-linux"\n'
                '\n[hosts.example.deploy]\nenable = true\nhostname = "private.example.internal"\n'
            )
            private_metadata = consumer / ".beads/secret"
            private_metadata.parent.mkdir()
            private_metadata.write_text("private beads material\n")
            git_init(consumer)
            git_commit_all(consumer)
            stage = root / "stage"

            result = run(
                [
                    "bash",
                    "-c",
                    'source "$1"; consumer_integration_stage "$2" "$3" "ci-stage" \'["base", "linux"]\'',
                    "_",
                    str(HELPER),
                    str(consumer),
                    str(stage),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((stage / ".git").is_dir())
            self.assertFalse((stage / ".beads").exists())
            staged_inventory = (stage / "inventory.toml").read_text()
            self.assertIn('username = "tester"', staged_inventory)
            self.assertIn("[hosts.ci-stage]", staged_inventory)
            self.assertNotIn("private.example.internal", staged_inventory)
            self.assertNotIn("[hosts.example]", staged_inventory)
            self.assertNotIn(
                "private beads material",
                "\n".join(path.read_text() for path in stage.rglob("*") if path.is_file() and ".git" not in path.parts),
            )


if __name__ == "__main__":
    unittest.main()
