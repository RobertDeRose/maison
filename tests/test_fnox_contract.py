from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from tests.support.topology import *


class FnoxContractTest(unittest.TestCase):
    VALID_FIXTURE = ROOT / "tests/fixtures/fnox/valid/minimal/fnox.toml"

    def run_validator(self, path: Path, *args: str, env: dict[str, str] | None = None) -> CompletedProcess[str]:
        return run(
            [str(ROOT / ".mise/lib/fnox.py"), "--file", str(path), *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_neutral_fixture_validates_without_owner_credentials(self) -> None:
        result = self.run_validator(self.VALID_FIXTURE, "validate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("valid", result.stdout)

    def test_provider_type_is_opaque_and_secret_references_are_logical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fnox.toml"
            path.write_text(
                """\
root = true
if_missing = "error"
env = "exec"

[providers.consumer_secret_store]
type = "consumer-selected-provider"
endpoint = "https://secrets.example.invalid"

[secrets.API_TOKEN]
provider = "consumer_secret_store"
key = "services/example/api-token"
env = "exec"
if_missing = "error"
"""
            )
            result = self.run_validator(path, "validate")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_validator_rejects_unsafe_runtime_contracts_with_actionable_errors(self) -> None:
        cases = {
            "root": ("root = false", "root = true", "root"),
            "missing-policy": ('if_missing = "warn"', 'if_missing = "error"', "if_missing"),
            "ambient-env": ("env = true", 'env = "exec"', "env"),
        }
        original = self.VALID_FIXTURE.read_text()
        with tempfile.TemporaryDirectory() as directory:
            for name, (bad, good, expected) in cases.items():
                with self.subTest(case=name):
                    path = Path(directory) / f"{name}.toml"
                    path.write_text(original.replace(good, bad))
                    result = self.run_validator(path, "validate")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected, result.stderr.lower())

    def test_validator_rejects_inline_credentials_without_echoing_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fnox.toml"
            path.write_text(
                """\
root = true
if_missing = "error"
env = "exec"

[providers.consumer_secret_store]
type = "consumer-selected-provider"
token = "do-not-print-this-token"
private_key = "do-not-print-this-key"
"""
            )
            result = self.run_validator(path, "validate")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("credential", result.stderr.lower())
            self.assertNotIn("do-not-print-this", result.stdout + result.stderr)

    def test_owner_only_local_override_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "fnox.toml"
            config.write_text(self.VALID_FIXTURE.read_text())
            local = root / "fnox.local.toml"
            local.write_text("[secrets]\n")
            local.chmod(0o644)
            result = self.run_validator(config, "validate")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("owner-only", result.stderr.lower())
            local.chmod(stat.S_IRUSR | stat.S_IWUSR)
            result = self.run_validator(config, "validate")
            self.assertEqual(result.returncode, 0, result.stderr)


class FnoxOrchestrationTest(unittest.TestCase):
    def make_config(self, root: Path) -> Path:
        config = root / "fnox.toml"
        config.write_text(
            """\
root = true
if_missing = "error"
env = "exec"

[secrets.API_TOKEN]
if_missing = "error"
env = "exec"
"""
        )
        return config

    def shell(self, root: Path, script: str, *, env: dict[str, str]) -> CompletedProcess[str]:
        return run(
            ["bash", "-c", script, "_", str(root)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_preflight_checks_missing_values_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            config_root = temp / "consumer"
            config_root.mkdir()
            self.make_config(config_root)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "fnox.log"
            executable(
                fake_bin / "fnox",
                "#!/bin/sh\n"
                'printf "args=%s env=%s\\n" "$*" "${FNOX_IF_MISSING:-}" >>"$FNOX_LOG"\n'
                'printf "missing required fnox secret API_TOKEN\\n" >&2\n'
                "exit 17\n",
            )
            marker = temp / "mutation-marker"
            environment = os.environ.copy()
            environment.update(
                {
                    "MAISON_HOME": str(ROOT),
                    "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                    "FNOX_LOG": str(log),
                }
            )
            result = self.shell(
                config_root,
                'set -e; source "$MAISON_HOME/.mise/lib/fnox.sh"; maison_fnox_preflight "$1"; touch "$FNOX_MUTATION_MARKER"',
                env={**environment, "FNOX_MUTATION_MARKER": str(marker)},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())
            self.assertIn("before mutation", result.stderr.lower())
            self.assertIn("API_TOKEN", result.stderr)
            self.assertIn("env=error", log.read_text())

    def test_preflight_and_get_keep_secret_values_out_of_fnox_arguments_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            config_root = temp / "consumer"
            config_root.mkdir()
            self.make_config(config_root)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "fnox.log"
            executable(
                fake_bin / "fnox",
                "#!/bin/sh\n"
                'printf "args=%s\\n" "$*" >>"$FNOX_LOG"\n'
                'case " $* " in *" get API_TOKEN "*) printf "runtime-secret\\n";; esac\n',
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "MAISON_HOME": str(ROOT),
                    "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                    "FNOX_LOG": str(log),
                }
            )
            result = self.shell(
                config_root,
                'source "$MAISON_HOME/.mise/lib/fnox.sh"; maison_fnox_preflight "$1"; value="$(maison_fnox_get "$1" API_TOKEN)"; test "$value" = runtime-secret',
                env={**environment, "_": "_"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            diagnostics = result.stdout + result.stderr + log.read_text()
            self.assertNotIn("runtime-secret", diagnostics)
            self.assertIn("get API_TOKEN", log.read_text())
            self.assertNotIn("--provider", log.read_text())

    def test_preflight_is_noop_for_consumers_without_fnox_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "consumer"
            root.mkdir()
            environment = {**os.environ, "MAISON_HOME": str(ROOT)}
            result = self.shell(
                root,
                'source "$MAISON_HOME/.mise/lib/fnox.sh"; maison_fnox_preflight "$1"; printf ready',
                env={**environment, "_": "_"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ready")


if __name__ == "__main__":
    unittest.main()
