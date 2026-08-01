from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path

import tomllib

from tests.support.processes import CompletedProcess, run

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/inventory"
SCHEMA = ROOT / "schemas/inventory.toml"
INVENTORY = ROOT / ".mise/lib/inventory.py"


def fixture_dirs(kind: str) -> list[Path]:
    return sorted(path for path in (FIXTURES / kind).iterdir() if path.is_dir())


def inventory_file(fixture: Path) -> Path:
    return fixture / "inventory.toml"


def expected_error(fixture: Path) -> str:
    return (fixture / "expected-error.txt").read_text().strip()


class InventorySchemaFixtureContractTest(unittest.TestCase):
    def test_schema_contract_declares_shared_inventory_policy(self) -> None:
        with SCHEMA.open("rb") as handle:
            schema = tomllib.load(handle)

        self.assertEqual(schema["schema_version"], 1)
        self.assertEqual(
            schema["supported_systems"],
            ["aarch64-darwin", "aarch64-linux", "x86_64-linux"],
        )
        self.assertEqual(schema["profiles"], ["base", "dev", "mac", "linux"])
        self.assertEqual(set(schema["features"]), {"personal_cache"})
        self.assertEqual(
            set(schema["deploy"]),
            {
                "enable",
                "hostname",
                "ssh_user",
                "user_ssh_user",
                "repo_path",
                "remote_build",
                "auto_rollback",
                "magic_rollback",
            },
        )
        self.assertEqual(schema["deploy"]["ssh_user"]["default"], "maison-deploy")
        self.assertEqual(
            schema["constraints"]["deploy_repo_path_scope"],
            "/home/<managed-user>/*",
        )

    def run_python_inventory(self, fixture: Path) -> CompletedProcess[str]:
        return run(
            [
                sys.executable,
                str(INVENTORY),
                "--file",
                str(inventory_file(fixture)),
                "--repo-root",
                str(fixture),
                "validate",
            ],
            capture_output=True,
            text=True,
        )

    def run_nix_inventory(self, fixture: Path) -> CompletedProcess[str]:
        if shutil.which("nix") is None:
            self.skipTest("nix is required for shared inventory fixture parity")
        expr = f"""
          let
            flake = builtins.getFlake "path:{ROOT}";
            lib = flake.inputs.nixpkgs.lib;
            inventory = builtins.fromTOML (builtins.readFile {inventory_file(fixture)});
            validated = import {ROOT / "nix/lib/inventory.nix"} {{ inherit lib inventory; }};
          in builtins.deepSeq validated true
        """
        return run(
            [
                "nix",
                "--extra-experimental-features",
                "nix-command flakes",
                "eval",
                "--impure",
                "--expr",
                expr,
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

    def test_python_validator_consumes_shared_fixture_corpus(self) -> None:
        for fixture in fixture_dirs("valid"):
            with self.subTest(fixture=fixture.relative_to(FIXTURES)):
                result = self.run_python_inventory(fixture)
                self.assertEqual(result.returncode, 0, result.stderr)
        for fixture in fixture_dirs("invalid"):
            with self.subTest(fixture=fixture.relative_to(FIXTURES)):
                result = self.run_python_inventory(fixture)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(expected_error(fixture), result.stderr)

    def test_nix_validator_consumes_shared_fixture_corpus(self) -> None:
        for fixture in fixture_dirs("valid"):
            with self.subTest(fixture=fixture.relative_to(FIXTURES)):
                result = self.run_nix_inventory(fixture)
                self.assertEqual(result.returncode, 0, result.stderr)
        for fixture in fixture_dirs("invalid"):
            with self.subTest(fixture=fixture.relative_to(FIXTURES)):
                result = self.run_nix_inventory(fixture)
                self.assertNotEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
