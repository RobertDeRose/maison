from __future__ import annotations

import json

from tests.support.topology import *


class PublicFlakeExportsTest(unittest.TestCase):
    def eval_outputs(self) -> dict[str, list[str]]:
        expression = f"""
let
  flake = builtins.getFlake (toString {ROOT});
  system = builtins.currentSystem;
in
{{
  packages = builtins.attrNames flake.packages.${{system}};
  apps = builtins.attrNames flake.apps.${{system}};
  darwinModules = builtins.attrNames flake.darwinModules;
  systemManagerModules = builtins.attrNames flake.systemManagerModules;
  lib = builtins.attrNames flake.lib.maison;
  schemas = builtins.attrNames flake.schemas;
  fixtures = builtins.attrNames flake.fixtures;
  fnox = builtins.attrNames flake.fnox;
}}
"""
        result = run(
            [
                "nix",
                "eval",
                "--impure",
                "--no-update-lock-file",
                "--json",
                "--expr",
                expression,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_public_flake_exposes_consumable_contract(self) -> None:
        outputs = self.eval_outputs()

        for output, name in (
            ("packages", "maison"),
            ("apps", "maison"),
            ("darwinModules", "default"),
            ("systemManagerModules", "default"),
            ("schemas", "inventory"),
            ("fixtures", "inventory"),
            ("schemas", "fnox"),
            ("fixtures", "fnox"),
        ):
            with self.subTest(output=output, name=name):
                self.assertIn(name, outputs[output])

        for name in (
            "mkDarwinSystem",
            "mkSystemManagerSystem",
            "validateInventory",
            "profiles",
            "validateFnox",
            "fnox",
        ):
            with self.subTest(lib=name):
                self.assertIn(name, outputs["lib"])

    def test_flake_metadata_is_provider_neutral(self) -> None:
        flake = read("flake.nix")
        self.assertIn('description = "Maison', flake)
        self.assertNotIn("Rob's system configuration", flake)

        outputs = read("nix/outputs.nix")
        self.assertNotIn("age-plugin", outputs)
        self.assertNotIn("bitwarden", outputs)
        self.assertNotIn("personal", outputs.lower())

    def test_neutral_fnox_contract_is_public(self) -> None:
        outputs = self.eval_outputs()
        self.assertIn("validate", outputs["fnox"])
        self.assertIn("secrets", outputs["fnox"])

    def test_nix_fnox_validation_returns_only_logical_metadata(self) -> None:
        expression = f"""
let
  flake = builtins.getFlake (toString {ROOT});
  config = builtins.fromTOML (builtins.readFile {ROOT}/tests/fixtures/fnox/valid/minimal/fnox.toml);
in
flake.lib.validateFnox config
"""
        result = run(
            [
                "nix",
                "eval",
                "--impure",
                "--no-update-lock-file",
                "--json",
                "--expr",
                expression,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["runtime"], {"credentials": "provider-or-runtime", "env": "exec", "ifMissing": "error"}
        )
        self.assertEqual(payload["secrets"], [])

    def test_neutral_resources_are_public_paths(self) -> None:
        outputs = read("nix/outputs.nix")
        self.assertIn("schemas =", outputs)
        self.assertIn("fixtures =", outputs)
        self.assertIn("inventory.toml", outputs)
        self.assertIn("schemas/fnox.toml", outputs)
        self.assertIn("tests/fixtures/inventory", outputs)
        self.assertIn("tests/fixtures/fnox", outputs)


if __name__ == "__main__":
    unittest.main()
