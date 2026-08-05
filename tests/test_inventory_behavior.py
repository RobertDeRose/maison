from __future__ import annotations

import sys

from tests.support.topology import *


class InventoryBehaviorTest(unittest.TestCase):
    def run_inventory(self, path: Path, *args: str) -> CompletedProcess[str]:
        return run(
            [str(ROOT / ".mise/lib/inventory.py"), "--file", str(path), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_repository_inventory_validates_with_typed_reader(self) -> None:
        result = self.run_inventory(ROOT / "inventory.toml", "--repo-root", str(ROOT), "validate")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.run_inventory(ROOT / "inventory.toml", "host-rows", "--system", "aarch64-linux")
        self.assertEqual(rows.returncode, 0, rows.stderr)
        self.assertIn("example-linux\toperator\tMaison Operator", rows.stdout)

    def test_host_table_returns_all_host_list_columns_in_one_query(self) -> None:
        result = self.run_inventory(ROOT / "inventory.toml", "host-table")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "example-darwin\taarch64-darwin\toperator\tbase,dev,mac",
                "example-linux\taarch64-linux\toperator\tbase,dev,linux",
            ],
        )

    def test_shell_inventory_batch_query_falls_back_to_flake_app_without_tomllib(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "nix-log"
            executable(fake_bin / "python3", "#!/bin/sh\nexit 1\n")
            executable(
                fake_bin / "nix",
                "#!/bin/sh\n"
                'printf "%s\\n" "$*" >"$NIX_LOG"\n'
                'while [ "$#" -gt 0 ]; do [ "$1" = -- ] && { shift; break; }; shift; done\n'
                'exec "$REAL_PYTHON" "$INVENTORY_SCRIPT" "$@"\n',
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "NIX_LOG": str(log),
                    "REAL_PYTHON": os.fspath(Path(sys.executable)),
                    "INVENTORY_SCRIPT": str(ROOT / ".mise/lib/inventory.py"),
                }
            )
            result = run(
                [
                    "bash",
                    "-c",
                    'source "$1/.mise/lib/inventory.sh"; inventory_host_rows "$1"',
                    "_",
                    str(ROOT),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("example-darwin\taarch64-darwin\toperator\tbase,dev,mac", result.stdout)
            self.assertIn("#maison-inventory -- --file", log.read_text())

    def test_host_list_uses_one_consumer_inventory_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            calls = temp / "python-calls"
            executable(
                fake_bin / "python3",
                '#!/bin/sh\nprintf "%s\\n" "$*" >>"$PYTHON_CALLS"\nexec "$REAL_PYTHON" "$@"\n',
            )
            env = os.environ.copy()
            for key in (
                "MAISON_INVENTORY",
                "MAISON_USER_CONFIG_ROOT",
                "MISE_GLOBAL_CONFIG_FILE",
            ):
                env.pop(key, None)
            env.update(
                {
                    "HOME": str(temp / "home"),
                    "XDG_STATE_HOME": str(temp / "state"),
                    "XDG_DATA_HOME": str(temp / "data"),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "PYTHON_CALLS": str(calls),
                    "REAL_PYTHON": os.fspath(Path(sys.executable)),
                    "MISE_PROJECT_ROOT": str(ROOT),
                }
            )
            result = run(
                [str(ROOT / ".mise/tasks/host/list")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            python_calls = calls.read_text().splitlines()
            inventory_calls = [call for call in python_calls if ".mise/lib/inventory.py" in call]
            self.assertEqual(len(inventory_calls), 1)
            self.assertNotIn("maison_overlay", "\n".join(python_calls))
            self.assertIn("example-linux", result.stdout)

    def test_shell_inventory_falls_back_to_flake_app_without_tomllib(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "nix-log"
            executable(fake_bin / "python3", "#!/bin/sh\nexit 1\n")
            executable(
                fake_bin / "nix",
                "#!/bin/sh\n"
                'printf "%s\n" "$*" >"$NIX_LOG"\n'
                'while [ "$#" -gt 0 ]; do [ "$1" = -- ] && { shift; break; }; shift; done\n'
                'exec "$REAL_PYTHON" "$INVENTORY_SCRIPT" "$@"\n',
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "NIX_LOG": str(log),
                    "REAL_PYTHON": os.fspath(Path(sys.executable)),
                    "INVENTORY_SCRIPT": str(ROOT / ".mise/lib/inventory.py"),
                }
            )
            result = run(
                [
                    "bash",
                    "-c",
                    'source "$1/.mise/lib/inventory.sh"; inventory_hosts "$1"',
                    "_",
                    str(ROOT),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("example-darwin", result.stdout)
            self.assertIn("#maison-inventory -- --file", log.read_text())

    def test_inventory_rejects_intel_and_unsafe_deploy_paths(self) -> None:
        original = read("inventory.toml")
        cases = {
            "intel": original.replace('system = "aarch64-darwin"', 'system = "x86_64-darwin"', 1),
            "home": original.replace('repo_path = "/home/operator/.maison"', 'repo_path = "/home/operator"'),
            "escape": original.replace(
                'repo_path = "/home/operator/.maison"',
                'repo_path = "/home/operator/../root"',
            ),
            "root": original.replace('repo_path = "/home/operator/.maison"', 'repo_path = "/"'),
            "unsafe-character": original.replace(
                'repo_path = "/home/operator/.maison"',
                'repo_path = "/home/operator/Maison Config"',
            ),
            "trailing-host-dot": original.replace(
                'hostname = "example-linux.example.invalid"',
                'hostname = "example-linux.example.invalid."',
            ),
            "wrong-user": original.replace(
                'user_ssh_user = "operator"',
                'user_ssh_user = "somebody-else"',
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            for label, content in cases.items():
                with self.subTest(case=label):
                    path = Path(directory) / f"{label}.toml"
                    path.write_text(content)
                    result = self.run_inventory(path, "validate")
                    self.assertNotEqual(result.returncode, 0)

    def test_inventory_defaults_deployment_ssh_user_to_maison_deploy(self) -> None:
        original = read("inventory.toml")
        cases = {
            "implicit-default": original.replace('ssh_user = "maison-deploy"\n', "", 1),
            "explicit-maison-deploy": original,
        }
        with tempfile.TemporaryDirectory() as directory:
            for label, content in cases.items():
                with self.subTest(case=label):
                    path = Path(directory) / f"{label}.toml"
                    path.write_text(content)
                    result = self.run_inventory(path, "validate")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    default_user = self.run_inventory(
                        path,
                        "host-field",
                        "example-linux",
                        "deploy.ssh_user",
                    )
                    self.assertEqual(default_user.stdout.strip(), "maison-deploy")

    def test_inventory_accepts_root_deployment_ssh_user(self) -> None:
        original = read("inventory.toml")
        root_inventory = original.replace('ssh_user = "maison-deploy"', 'ssh_user = "root"', 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "root-bootstrap.toml"
            path.write_text(root_inventory)
            result = self.run_inventory(path, "validate")
            self.assertEqual(result.returncode, 0, result.stderr)
            deploy_user = self.run_inventory(path, "host-field", "example-linux", "deploy.ssh_user")
            self.assertEqual(deploy_user.returncode, 0, deploy_user.stderr)
            self.assertEqual(deploy_user.stdout.strip(), "root")

    def test_inventory_rejects_deploy_ssh_user_matching_managed_user(self) -> None:
        original = read("inventory.toml")
        cases = {
            "managed-user": original.replace('ssh_user = "maison-deploy"', 'ssh_user = "operator"', 1),
            "managed-user-explicit": original.replace(
                'ssh_user = "maison-deploy"\nuser_ssh_user = "operator"\n',
                'ssh_user = "operator"\nuser_ssh_user = "operator"\n',
                1,
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            for label, content in cases.items():
                with self.subTest(case=label):
                    path = Path(directory) / f"{label}.toml"
                    path.write_text(content)
                    result = self.run_inventory(path, "validate")
                    self.assertNotEqual(result.returncode, 0, result.stderr)

    def test_inventory_contracts_are_shared_by_python_and_nix_defaults(self) -> None:
        python_inventory = read(".mise/lib/inventory.py")
        nix_inventory = read("nix/lib/inventory.nix")
        schema = read("schemas/inventory.toml")

        self.assertIn("[deploy.ssh_user]", schema)
        self.assertIn('default = "maison-deploy"', schema)
        self.assertIn("SCHEMA = load_schema()", python_inventory)
        self.assertIn('DEPLOY_SCHEMA = SCHEMA["deploy"]', python_inventory)
        self.assertIn("builtins.fromTOML", nix_inventory)
        self.assertIn('deployDefault "ssh_user"', nix_inventory)
        self.assertIn("deploy.sshUser == selectedUser.username", nix_inventory)


class ConsumerFrameworkContractTest(unittest.TestCase):
    def test_public_starter_files_do_not_contain_private_identity(self) -> None:
        banned = (
            "private-user",
            "PrivateOperator",
            "private-darwin-host",
            "private-linux-host",
            "private-site.example.invalid",
            "private-email@example.invalid",
        )
        paths = [ROOT / "inventory.toml", ROOT / "README.md"]
        paths += [ROOT / name for name in ("docs/add-a-host.md", "docs/deployment.md")]
        paths += sorted((ROOT / "dotfiles").rglob("*"))
        for path in paths:
            if not path.is_file():
                continue
            text = path.read_text(errors="ignore")
            with self.subTest(path=path.relative_to(ROOT)):
                for token in banned:
                    self.assertNotIn(token, text)

    def test_startup_spinner_preserves_output_and_exit_status(self) -> None:
        result = run(
            [
                "bash",
                "-c",
                'source "$1/.mise/lib/common.sh"; run_with_startup_spinner "Planning system" sh -c \'sleep 0.05; printf ready; exit 7\'',
                "_",
                str(ROOT),
            ],
            cwd=ROOT,
            env={**os.environ, "MAISON_SPINNER": "always"},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 7)
        self.assertIn("ready", result.stdout)
        self.assertIn("Planning system", result.stderr)

    def test_startup_spinner_is_passthrough_without_tty(self) -> None:
        result = run(
            [
                "bash",
                "-c",
                'source "$1/.mise/lib/common.sh"; run_with_startup_spinner "Planning system" sh -c \'printf ready; printf warning >&2; exit 3\'',
                "_",
                str(ROOT),
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "ready")
        self.assertEqual(result.stderr, "warning")


if __name__ == "__main__":
    unittest.main()
