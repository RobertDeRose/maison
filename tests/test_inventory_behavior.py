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


class OverlayContractTest(unittest.TestCase):
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

    def test_overlay_helper_uses_xdg_state_and_source_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(temp / "home"),
                    "XDG_STATE_HOME": str(temp / "state"),
                    "XDG_DATA_HOME": str(temp / "data"),
                }
            )
            helper = ROOT / "scripts/maison_overlay.py"
            missing = run(
                [str(helper), "--required", "resolve"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("overlay source is required", missing.stderr)

            env["MAISON_OVERLAY"] = "env-overlay"
            resolved = run(
                [str(helper), "resolve"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(resolved.stdout.strip(), "env-overlay")

            env["MAISON_OVERLAY_SOURCE"] = "legacy-overlay"
            legacy = run(
                [str(helper), "resolve"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(legacy.stdout.strip(), "env-overlay")
            env.pop("MAISON_OVERLAY")
            legacy = run(
                [str(helper), "resolve"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(legacy.stdout.strip(), "legacy-overlay")

            explicit = run(
                [str(helper), "--overlay", "explicit-overlay", "resolve"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(explicit.stdout.strip(), "explicit-overlay")

    def write_private_overlay_fixture(self, overlay: Path) -> None:
        overlay.mkdir()
        (overlay / "inventory.toml").write_text(
            "schema = 1\n"
            "[defaults]\n"
            'user = "site"\n'
            "[users.site]\n"
            'username = "site-user"\n'
            'full_name = "Site Operator"\n'
            'email = "site@example.invalid"\n'
            'github = "site-example"\n'
            "[hosts.private-linux]\n"
            'system = "aarch64-linux"\n'
            'profiles = ["base", "linux"]\n'
            "[hosts.private-linux.deploy]\n"
            "enable = true\n"
            'hostname = "private-linux.example.invalid"\n'
            'ssh_user = "maison-deploy"\n'
            'user_ssh_user = "site-user"\n'
            'repo_path = "/home/site-user/.maison"\n'
        )
        (overlay / "hosts/private-linux").mkdir(parents=True)
        (overlay / "hosts/private-linux/system.nix").write_text("{ ... }: {}\n")
        (overlay / "config/mise").mkdir(parents=True)
        (overlay / "config/mise/config.toml").write_text('[tools]\n"usage" = "latest"\n')
        (overlay / "dotfiles/git").mkdir(parents=True)
        (overlay / "dotfiles/git/identity").write_text(
            "[user]\n    name = Site Operator\n    email = site@example.invalid\n"
        )
        (overlay / "trusted").mkdir()
        (overlay / "trusted/allowed_signers").write_text(
            "site@example.invalid ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEexamplefixturekey\n"
        )

    def test_inventory_shell_loads_private_overlay_inventory_and_host_overrides(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            overlay = temp / "overlay"
            self.write_private_overlay_fixture(overlay)
            state_home = temp / "state"
            state = state_home / "maison/overlay.toml"
            state.parent.mkdir(parents=True)
            state.write_text(f'source = "local"\npath = "{overlay}"\n')
            env = os.environ.copy()
            env.update({"XDG_STATE_HOME": str(state_home), "XDG_DATA_HOME": str(temp / "data")})
            result = run(
                [
                    "bash",
                    "-c",
                    'source "$1/.mise/lib/inventory.sh"; inventory_hosts "$1"; inventory_host_username "$1" private-linux',
                    "_",
                    str(ROOT),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["private-linux", "site-user"])

    def test_nix_loader_uses_an_explicit_overlay_input(self) -> None:
        flake = read("flake.nix")
        nix = read(".mise/lib/nix.sh")
        self.assertIn('url = "path:."', flake)
        self.assertIn('inventoryFile = "${inputs.overlay}/inventory.toml"', flake)
        self.assertNotIn('builtins.getEnv "MAISON_INVENTORY"', flake)
        self.assertIn("--override-input", nix)
        self.assertNotIn("--impure", nix)
        self.assertIn("load_maison_overlay_environment", nix)

    def test_run_nh_passes_overlay_input_for_private_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "nh-log"
            overlay = temp / "overlay"
            overlay.mkdir()
            executable(fake_bin / "nh", '#!/bin/sh\nprintf \'%s\\n\' "$*" >"$NH_LOG"\n')
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MISE_PROJECT_ROOT": str(ROOT),
                    "MAISON_INVENTORY": str(overlay / "inventory.toml"),
                    "MAISON_OVERLAY_PATH": str(overlay),
                    "NH_LOG": str(log),
                }
            )
            result = run(
                [
                    "bash",
                    "-c",
                    'source "$1/.mise/lib/nix.sh"; run_nh darwin build "$1" -H fixture-host',
                    "_",
                    str(ROOT),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                log.read_text().strip(),
                f"darwin build {ROOT} -H fixture-host -- --override-input overlay path:{temp / 'overlay'}",
            )

    def test_nix_command_passes_overlay_input_to_flake_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            overlay = temp / "overlay"
            overlay.mkdir()
            log = temp / "nix-log"
            executable(fake_bin / "nix", '#!/bin/sh\nprintf \'%s\\n\' "$*" >"$NIX_LOG"\n')
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MISE_PROJECT_ROOT": str(ROOT),
                    "MAISON_OVERLAY_PATH": str(overlay),
                    "NIX_LOG": str(log),
                }
            )
            result = run(
                [
                    "bash",
                    "-c",
                    'source "$1/.mise/lib/common.sh"; source "$1/.mise/lib/nix.sh"; nix_command eval .#darwinConfigurations',
                    "_",
                    str(ROOT),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            command = log.read_text().strip()
            self.assertIn(f"eval --override-input overlay path:{overlay}", command)
            self.assertNotIn("--impure", command)

    def test_run_nh_keeps_public_inventory_pure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "nh-log"
            executable(fake_bin / "nh", '#!/bin/sh\nprintf \'%s\\n\' "$*" >"$NH_LOG"\n')
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MISE_PROJECT_ROOT": str(ROOT),
                    "MAISON_INVENTORY": str(ROOT / "inventory.toml"),
                    "NH_LOG": str(log),
                }
            )
            result = run(
                [
                    "bash",
                    "-c",
                    'source "$1/.mise/lib/nix.sh"; run_nh darwin build "$1" -H example-darwin',
                    "_",
                    str(ROOT),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                log.read_text().strip(),
                f"darwin build {ROOT} -H example-darwin -- --override-input overlay path:{ROOT}",
            )

    def test_nix_command_overrides_public_overlay_input_without_lock_updates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "nix-log"
            executable(fake_bin / "nix", '#!/bin/sh\nprintf \'%s\\n\' "$*" >"$NIX_LOG"\n')
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MISE_PROJECT_ROOT": str(ROOT),
                    "MAISON_INVENTORY": str(ROOT / "inventory.toml"),
                    "NIX_LOG": str(log),
                }
            )
            result = run(
                [
                    "bash",
                    "-c",
                    'source "$1/.mise/lib/common.sh"; source "$1/.mise/lib/nix.sh"; nix_command flake metadata --no-update-lock-file',
                    "_",
                    str(ROOT),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                log.read_text()
                .strip()
                .endswith(f"flake metadata --no-update-lock-file --override-input overlay path:{ROOT}")
            )

    def test_overlay_prepare_uses_existing_local_repository_directly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source = temp / 'source "overlay"'
            source.mkdir()
            (source / "inventory.toml").write_text("schema = 1\n")
            git_init(source)
            git_commit_all(source)
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(temp / "home"),
                    "XDG_STATE_HOME": str(temp / "state"),
                    "XDG_DATA_HOME": str(temp / "data"),
                }
            )
            helper = ROOT / "scripts/maison_overlay.py"
            result = run(
                [str(helper), "--overlay", str(source), "prepare"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            state = temp / "state/maison/overlay.toml"
            self.assertEqual(result.stdout.strip(), str(source.resolve()))
            with state.open("rb") as handle:
                state_data = tomllib.load(handle)
            self.assertEqual(state_data["source"], str(source.resolve()))
            self.assertEqual(state_data["path"], str(source.resolve()))
            self.assertFalse((temp / "data/maison/overlay").exists())
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o600)

    def test_overlay_prepare_rejects_existing_clone_with_different_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            original = temp / "original"
            original.mkdir()
            (original / "inventory.toml").write_text("schema = 1\n")
            git_init(original)
            git_commit_all(original)
            clone = temp / "clone"
            run(
                ["git", "clone", str(original), str(clone)],
                check=True,
                capture_output=True,
            )
            helper = ROOT / "scripts/maison_overlay.py"
            result = run(
                [
                    str(helper),
                    "--overlay",
                    "https://example.invalid/replacement.git",
                    "--clone-dir",
                    str(clone),
                    "prepare",
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("different source", result.stderr)

    def test_reader_docs_describe_overlay_contract(self) -> None:
        docs = "\n".join(
            read(path)
            for path in (
                "README.md",
                "docs/architecture.md",
                "docs/operations.md",
                "docs/task-reference.md",
                "docs/recovery.md",
            )
        )
        self.assertIn("${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml", docs)
        self.assertIn("${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay", docs)
        self.assertIn("--overlay", docs)
        self.assertIn("MAISON_OVERLAY_SOURCE", docs)
        self.assertIn("host:add", docs)
        self.assertIn("overlay inventory", docs)

    def test_bootstrap_passes_overlay_to_bootstrap_task(self) -> None:
        direct = run(
            [str(ROOT / "bootstrap.sh"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--overlay SOURCE", direct.stdout)

        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source = temp / "source"
            source.mkdir()
            copy_files(
                source,
                "mise.toml",
                "flake.nix",
                "bin/maison",
                ".mise/lib/common.sh",
                ".mise/lib/platform.sh",
                ".mise/lib/bootstrap.sh",
            )
            git_init(source)
            git_commit_all(source)
            home = temp / "home"
            home.mkdir()
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "mise-log"
            executable(
                fake_bin / "nix",
                "#!/bin/sh\n[ \"$1\" = --version ] && echo 'nix 2.0'\n",
            )
            executable(fake_bin / "mise", '#!/bin/sh\nprintf \'%s\\n\' "$*" >>"$MISE_LOG"\n')
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "MAISON_HOME": str(home / ".maison"),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MISE_LOG": str(log),
                }
            )
            result = run(
                [
                    str(ROOT / "bootstrap.sh"),
                    "--repo",
                    str(source),
                    "--ref",
                    "main",
                    "--host",
                    "fixture-host",
                    "--overlay",
                    "git@example.invalid:site/overlay.git",
                ],
                cwd=temp,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "run --skip-tools bootstrap -- --host fixture-host --overlay git@example.invalid:site/overlay.git",
                log.read_text(),
            )

    def test_bootstrap_without_overlay_installs_cli_and_skips_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source = temp / "source"
            source.mkdir()
            copy_files(
                source,
                "mise.toml",
                "flake.nix",
                "bin/maison",
                ".mise/lib/common.sh",
                ".mise/lib/platform.sh",
                ".mise/lib/bootstrap.sh",
            )
            git_init(source)
            git_commit_all(source)
            home = temp / "home"
            home.mkdir()
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "mise-log"
            executable(
                fake_bin / "nix",
                "#!/bin/sh\nprintf 'nix should not run\\n' >&2\nexit 99\n",
            )
            executable(fake_bin / "mise", '#!/bin/sh\nprintf \'%s\\n\' "$*" >>"$MISE_LOG"\n')
            env = os.environ.copy()
            env.pop("MAISON_OVERLAY", None)
            env.pop("MAISON_OVERLAY_SOURCE", None)
            env.update(
                {
                    "HOME": str(home),
                    "MAISON_HOME": str(home / ".maison"),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MISE_LOG": str(log),
                }
            )
            result = run(
                [
                    str(ROOT / "bootstrap.sh"),
                    "--repo",
                    str(source),
                    "--ref",
                    "main",
                    "--host",
                    "fixture-host",
                ],
                cwd=temp,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("No private overlay was selected", result.stdout)
            self.assertTrue((home / ".local/bin/maison").is_symlink())
            self.assertNotIn("run --skip-tools bootstrap", log.read_text())
