from __future__ import annotations

import json
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

    def test_python_and_nix_validators_agree_on_shared_fixture_corpus(self) -> None:
        for kind in ("valid", "invalid"):
            expected_valid = kind == "valid"
            for fixture in fixture_dirs(kind):
                with self.subTest(fixture=fixture.relative_to(FIXTURES)):
                    python_result = self.run_python_inventory(fixture)
                    nix_result = self.run_nix_inventory(fixture)
                    self.assertEqual(python_result.returncode == 0, expected_valid, python_result.stderr)
                    self.assertEqual(nix_result.returncode == 0, expected_valid, nix_result.stderr)
                    self.assertEqual(
                        python_result.returncode == 0,
                        nix_result.returncode == 0,
                        f"Python/Nix acceptance mismatch for {fixture}: {python_result.stderr} {nix_result.stderr}",
                    )
                    if not expected_valid:
                        self.assertIn(expected_error(fixture), python_result.stderr)

    def test_python_and_nix_normalize_deployment_defaults_equivalently(self) -> None:
        fixture = FIXTURES / "valid/minimal"
        host = "example-darwin"
        fields = {
            "enable": False,
            "hostname": host,
            "ssh_user": "maison-deploy",
            "user_ssh_user": "operator",
            "repo_path": "/home/operator/.maison",
            "remote_build": False,
            "auto_rollback": True,
            "magic_rollback": True,
        }
        python_values: dict[str, object] = {}
        for field, expected in fields.items():
            result = run(
                [
                    sys.executable,
                    str(INVENTORY),
                    "--file",
                    str(inventory_file(fixture)),
                    "host-field",
                    host,
                    f"deploy.{field}",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            python_values[field] = json.loads(result.stdout) if isinstance(expected, bool) else result.stdout.strip()

        if shutil.which("nix") is None:
            self.skipTest("nix is required for shared inventory default parity")
        expr = f"""
          let
            flake = builtins.getFlake "path:{ROOT}";
            lib = flake.inputs.nixpkgs.lib;
            inventory = builtins.fromTOML (builtins.readFile {inventory_file(fixture)});
            validated = import {ROOT / "nix/lib/inventory.nix"} {{ inherit lib inventory; }};
            deploy = validated.hosts.{host}.deploy;
          in {{
            enable = deploy.enable;
            hostname = deploy.hostname;
            ssh_user = deploy.sshUser;
            user_ssh_user = deploy.userSshUser;
            repo_path = deploy.repoPath;
            remote_build = deploy.remoteBuild;
            auto_rollback = deploy.autoRollback;
            magic_rollback = deploy.magicRollback;
          }}
        """
        nix_result = run(
            [
                "nix",
                "--extra-experimental-features",
                "nix-command flakes",
                "eval",
                "--json",
                "--impure",
                "--expr",
                expr,
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=120,
        )
        self.assertEqual(nix_result.returncode, 0, nix_result.stderr)
        self.assertEqual(json.loads(nix_result.stdout), python_values)


if __name__ == "__main__":
    unittest.main()
