from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from tests.support.topology import *


class ConsumerValidationTest(unittest.TestCase):
    def make_consumer(self, root: Path) -> Path:
        consumer = root / "consumer"
        (consumer / "config/mise").mkdir(parents=True)
        (consumer / "dotfiles/shell").mkdir(parents=True)
        (consumer / "dotfiles/shell/config").write_text("neutral\n")
        (consumer / "README.md").write_text(
            "# Neutral consumer\n\nThis repository consumes Maison and uses provider-neutral references.\n"
        )
        (consumer / "flake.nix").write_text(
            """
{
  inputs.maison.url = "path:/neutral/maison";
  outputs = inputs: {
    systemConfigs.example-linux = {};
  };
}
""".lstrip()
        )
        (consumer / "flake.lock").write_text(
            json.dumps(
                {
                    "nodes": {
                        "root": {"inputs": {"maison": "maison"}},
                        "maison": {"locked": {"type": "path", "path": "../maison"}},
                    },
                    "root": "root",
                }
            )
            + "\n"
        )
        (consumer / "inventory.toml").write_text(
            """
schema = 1

[users.operator]
username = "operator"
full_name = "Example Operator"
email = "operator@example.invalid"
github = "example-operator"

[hosts.example-linux]
system = "aarch64-linux"
user = "operator"
profiles = ["base", "dev", "linux"]
""".lstrip()
        )
        (consumer / "config/mise/config.toml").write_text(
            """
[tools]
python = "3.13"

[bootstrap.packages]
"brew:git" = "latest"

[dotfiles."~/.config/example"]
source = "../../dotfiles/shell/config"
mode = "symlink"
""".lstrip()
        )
        git_init(consumer)
        return consumer

    def fake_tools(self, root: Path, *, nix_json: str) -> Path:
        fake_bin = root / "bin"
        fake_bin.mkdir()
        executable(
            fake_bin / "nix",
            """#!/bin/sh
[ -z "${FNOX_TOKEN:-}" ] || exit 42
printf '%s\n' "$*" >>"$NIX_LOG"
case "$1" in
  "flake") exit 0 ;;
  "eval") printf '%s\n' "$NIX_JSON"; exit 0 ;;
esac
printf 'unexpected nix invocation\n' >&2
exit 1
""",
        )
        executable(
            fake_bin / "fnox",
            """#!/bin/sh
: >"$FNOX_CALLED"
exit 99
""",
        )
        return fake_bin

    def run_validation(
        self,
        consumer: Path,
        fake_bin: Path,
        log: Path,
        fnox_called: Path,
    ) -> CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                "NIX_JSON": json.dumps(
                    {
                        "inputs": ["maison"],
                        "darwinConfigurations": [],
                        "systemConfigs": ["example-linux"],
                        "deploy": [],
                    }
                ),
                "NIX_LOG": str(log),
                "FNOX_CALLED": str(fnox_called),
                "FNOX_TOKEN": "credential-not-needed",
                "MAISON_HOME": str(ROOT),
                "MISE_PROJECT_ROOT": str(ROOT),
            }
        )
        return run(
            [
                str(ROOT / "bin/maison"),
                "consumer",
                "validate",
                "--consumer",
                str(consumer),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

    def test_valid_consumer_passes_without_invoking_fnox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            log = temp / "nix.log"
            fnox_called = temp / "fnox-called"
            fake_bin = self.fake_tools(temp, nix_json="unused")

            result = self.run_validation(consumer, fake_bin, log, fnox_called)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("consumer validation passed", result.stdout.lower())
            self.assertIn("flake", result.stdout)
            self.assertIn("inventory", result.stdout)
            self.assertIn("packages", result.stdout)
            self.assertIn("dotfiles", result.stdout)
            self.assertIn("fnox", result.stdout)
            self.assertIn("documentation", result.stdout)
            self.assertFalse(fnox_called.exists())
            self.assertIn("--no-update-lock-file", log.read_text())

    def test_invalid_inventory_fails_before_flake_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            (consumer / "inventory.toml").write_text(
                (consumer / "inventory.toml").read_text().replace("aarch64-linux", "x86_64-darwin")
            )
            log = temp / "nix.log"
            fake_bin = self.fake_tools(temp, nix_json="unused")

            result = self.run_validation(consumer, fake_bin, log, temp / "fnox-called")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("inventory", result.stderr.lower())
            self.assertFalse(log.exists())

    def test_missing_consumer_flake_input_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            lock = json.loads((consumer / "flake.lock").read_text())
            del lock["nodes"]["root"]["inputs"]["maison"]
            (consumer / "flake.lock").write_text(json.dumps(lock) + "\n")
            log = temp / "nix.log"
            fake_bin = self.fake_tools(temp, nix_json="unused")

            result = self.run_validation(consumer, fake_bin, log, temp / "fnox-called")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("flake", result.stderr.lower())
            self.assertFalse(log.exists())

    def test_package_and_fnox_declarations_reject_embedded_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            config = consumer / "config/mise/config.toml"
            config.write_text(config.read_text().replace('"brew:git"', "brew"))
            log = temp / "nix.log"
            fake_bin = self.fake_tools(temp, nix_json="unused")

            result = self.run_validation(consumer, fake_bin, log, temp / "fnox-called")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("packages", result.stderr.lower())
            self.assertFalse(log.exists())

            config.write_text(config.read_text().replace("brew =", '"brew:git" ='))
            (consumer / "config/mise/config.toml").write_text(
                config.read_text() + '\n[env]\nTOKEN = "raw-value" # fnox\n'
            )
            result = self.run_validation(consumer, fake_bin, log, temp / "fnox-called")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fnox", result.stderr.lower())
            self.assertFalse(log.exists())

    def test_dotfile_source_must_stay_inside_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            config = consumer / "config/mise/config.toml"
            config.write_text(config.read_text().replace("../../dotfiles/shell/config", "../../outside"))
            (temp / "outside").write_text("outside\n")
            log = temp / "nix.log"
            fake_bin = self.fake_tools(temp, nix_json="unused")

            result = self.run_validation(consumer, fake_bin, log, temp / "fnox-called")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("dotfile", result.stderr.lower())
            self.assertFalse(log.exists())

    def test_documentation_links_and_privacy_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            (consumer / "docs").mkdir()
            (consumer / "docs/guide.md").write_text("[missing](missing.md)\n")
            log = temp / "nix.log"
            fake_bin = self.fake_tools(temp, nix_json="unused")

            result = self.run_validation(consumer, fake_bin, log, temp / "fnox-called")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("documentation", result.stderr.lower())
            self.assertFalse(log.exists())

            (consumer / "docs/guide.md").write_text("safe\n")
            (consumer / "private.pem").write_text("-----BEGIN " + "PRIVATE KEY-----\n")
            result = self.run_validation(consumer, fake_bin, log, temp / "fnox-called")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("privacy", result.stderr.lower())
            self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()
