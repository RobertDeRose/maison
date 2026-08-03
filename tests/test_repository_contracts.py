from __future__ import annotations

from itertools import pairwise

from tests.support.topology import *


class DataFilesTest(unittest.TestCase):
    def test_git_fixtures_ignore_global_commit_signing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hostile_config = root / "hostile-gitconfig"
            hostile_config.write_text(
                textwrap.dedent(
                    """\
                    [commit]
                        gpgSign = true
                    [gpg]
                        format = ssh
                    [user]
                        signingKey = /definitely/missing/test-signing-key.pub
                    """
                )
            )
            previous = os.environ.get("GIT_CONFIG_GLOBAL")
            os.environ["GIT_CONFIG_GLOBAL"] = str(hostile_config)
            try:
                repo = root / "repo"
                repo.mkdir()
                git_init(repo)
                (repo / "first").write_text("first\n")
                first = git_commit_all(repo, "first")
                (repo / "second").write_text("second\n")
                second = git_commit_all(repo, "second")
            finally:
                if previous is None:
                    os.environ.pop("GIT_CONFIG_GLOBAL", None)
                else:
                    os.environ["GIT_CONFIG_GLOBAL"] = previous

            self.assertNotEqual(first, second)

    def test_toml_files_and_lockfiles_parse(self) -> None:
        paths = sorted(ROOT.glob("*.toml")) + sorted((ROOT / "config/mise").glob("*.toml"))
        paths += [path for path in (ROOT / "mise.lock",) if path.exists()]
        paths += sorted((ROOT / "config/mise").glob("*.lock"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)), path.open("rb") as handle:
                tomllib.load(handle)

    def test_lockfiles_exactly_cover_their_tool_configs(self) -> None:
        pairs = (
            ("config/mise/config.toml", "config/mise/mise.lock"),
            ("config/mise/config.macos.toml", "config/mise/config.macos.lock"),
            ("mise.toml", "mise.lock"),
        )
        for config_name, lock_name in pairs:
            with self.subTest(config=config_name, lock=lock_name):
                config = tomllib.loads(read(config_name)).get("tools", {})
                lock = tomllib.loads(read(lock_name)).get("tools", {})
                self.assertEqual(set(lock), set(config))

    def test_repository_toolchain_pins_bootstrap_python(self) -> None:
        config = tomllib.loads(read("mise.toml"))
        lock = tomllib.loads(read("mise.lock"))
        self.assertEqual(config["tools"]["python"], "3.13.14")
        self.assertEqual(lock["tools"]["python"][0]["version"], "3.13.14")

    def test_json_files_parse(self) -> None:
        for path in sorted((ROOT / "dotfiles").rglob("*.json")):
            with self.subTest(path=path.relative_to(ROOT)):
                json.loads(path.read_text())

    def test_flake_lock_has_only_live_top_level_inputs(self) -> None:
        lock = json.loads(read("flake.lock"))
        root_inputs = set(lock["nodes"]["root"]["inputs"])
        self.assertEqual(
            root_inputs,
            {
                "darwin",
                "flake-parts",
                "nix-hex-box",
                "nix-homebrew",
                "nixpkgs",
                "overlay",
                "system-manager",
            },
        )
        serialized = json.dumps(lock)
        self.assertNotIn("home-manager", serialized)
        self.assertNotIn('"deploy-rs"', serialized)

    def test_nix_formatter_uses_the_repository_lock(self) -> None:
        lock = tomllib.loads(read("mise.lock"))
        entries = lock["tools"]["aqua:Mic92/nixfmt-rs"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        version = entry["version"]
        platform_keys = {
            "aarch64-darwin": "platforms.macos-arm64",
            "aarch64-linux": "platforms.linux-arm64",
            "x86_64-linux": "platforms.linux-x64",
        }
        for system, platform_key in platform_keys.items():
            with self.subTest(system=system):
                artifact = entry[platform_key]
                self.assertIn(f"/{version}/", artifact["url"])
                self.assertRegex(artifact["checksum"], r"^sha256:[0-9a-f]{64}$")

        package = read("nix/lib/nixfmt-rs.nix")
        outputs = read("nix/outputs.nix")
        self.assertIn("builtins.readFile ../../mise.lock", package)
        for system, platform_key in platform_keys.items():
            self.assertIn(f'{system} = "{platform_key}";', package)
        self.assertIn("pkgs.nixfmt-tree.override { inherit nixfmtPackage; }", outputs)
        self.assertIn("nixfmt = nixfmtPackage;", outputs)
        self.assertNotIn("formatter = pkgs.nixfmt-tree;", outputs)


class ReviewGatedDependencyUpdateTest(unittest.TestCase):
    WORKFLOW = ".github/workflows/cache-refresh.yml"

    def test_dependency_refresh_workflow_cannot_merge_or_bypass_review(self) -> None:
        workflow = read(self.WORKFLOW)
        forbidden_patterns = {
            "gh pr merge": r"\bgh\s+pr\s+merge\b",
            "admin merge flag": r"\s--admin(?:\s|$)",
            "auto-merge enablement": r"\bgh\s+pr\s+merge\b[^\n]*\s--auto(?:\s|$)|\bgh\s+pr\s+edit\b[^\n]*\s--enable-auto-merge(?:\s|$)",
        }
        offenders = [name for name, pattern in forbidden_patterns.items() if re.search(pattern, workflow)]
        self.assertEqual(offenders, [])

    def test_cache_warming_and_update_pr_are_separate_from_approval(self) -> None:
        workflow = read(self.WORKFLOW)
        self.assertIn("  build-platforms:", workflow)
        self.assertIn("  commit-lock:", workflow)
        self.assertRegex(workflow, r"commit-lock:\n(?:.|\n)*?needs:\n(?:.|\n)*?- build-platforms")
        self.assertNotIn("  merge-lock-pr:", workflow)
        self.assertNotRegex(workflow, r"needs\.commit-lock\.outputs\.pr_number[^\n]*gh pr merge")


class RepositoryContractTest(unittest.TestCase):
    def test_task_and_script_entrypoints_are_executable(self) -> None:
        paths = [ROOT / "bootstrap.sh", ROOT / "bin/maison", ROOT / ".mise/lib/inventory.py"]
        paths.extend(sorted((ROOT / ".mise/tasks").rglob("*")))
        paths.extend(sorted((ROOT / "scripts").glob("*.sh")))
        for path in paths:
            if not path.is_file():
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.read_text().startswith("#!"))
                self.assertTrue(path.stat().st_mode & stat.S_IXUSR)

    def test_maison_exposes_layered_commands(self) -> None:
        cli = read("bin/maison")
        for command in ('cmd "check"', 'cmd "system"', 'cmd "user"', 'cmd "deploy"', 'cmd "sync"'):
            self.assertIn(command, cli)
        self.assertIn('export MISE_PROJECT_ROOT="$maison_home"', cli)

    def test_bootstrap_uses_the_locked_project_python(self) -> None:
        bootstrap = read("bootstrap.sh")
        cli = read("bin/maison")
        self.assertIn(
            "mise exec --locked python -- mise run --skip-tools bootstrap --",
            bootstrap,
        )
        self.assertIn(
            'saved="$(mise exec --locked python -- python "$repo_root/scripts/maison_overlay.py" resolve',
            bootstrap,
        )
        self.assertNotIn(
            'saved="$(python3 "$repo_root/scripts/maison_overlay.py" resolve',
            bootstrap,
        )
        self.assertIn(
            'exec "$mise_bin" exec --locked python -- "$mise_bin" run --skip-tools "$requested_task" --help',
            cli,
        )
        self.assertIn(
            'command=("$mise_bin" exec --locked python -- "$mise_bin" run --skip-tools)',
            cli,
        )

    def test_sync_pulls_maison_and_overlay_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            overlay = temp / "overlay"
            overlay.mkdir()
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "sync.log"
            executable(
                fake_bin / "git",
                '#!/bin/sh\nprintf \'git %s\\n\' "$*" >>"$SYNC_LOG"\nstatus=0\n[ "${3:-}" != pull ] || status="${SYNC_GIT_STATUS:-0}"\nexit "$status"\n',
            )
            executable(
                fake_bin / "mise",
                '#!/bin/sh\nprintf \'mise %s\\n\' "$*" >>"$SYNC_LOG"\n',
            )
            env = os.environ.copy()
            env.update(
                {
                    "MISE_PROJECT_ROOT": str(ROOT),
                    "MAISON_OVERLAY_PATH": str(overlay),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "SYNC_LOG": str(log),
                }
            )
            result = run(
                ["bash", str(ROOT / ".mise/tasks/sync")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [line for line in log.read_text().splitlines() if "pull" in line or line.startswith("mise ")],
                [
                    f"git -C {ROOT} pull --ff-only --autostash",
                    f"git -C {overlay} pull --ff-only --autostash",
                    "mise run apply --",
                ],
            )

    def test_sync_does_not_apply_when_a_pull_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            overlay = temp / "overlay"
            overlay.mkdir()
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "sync.log"
            executable(
                fake_bin / "git",
                '#!/bin/sh\nprintf \'git %s\\n\' "$*" >>"$SYNC_LOG"\nstatus=0\n[ "${3:-}" != pull ] || status="${SYNC_GIT_STATUS:-0}"\nexit "$status"\n',
            )
            executable(
                fake_bin / "mise",
                '#!/bin/sh\nprintf \'mise %s\\n\' "$*" >>"$SYNC_LOG"\n',
            )
            env = os.environ.copy()
            env.update(
                {
                    "MISE_PROJECT_ROOT": str(ROOT),
                    "MAISON_OVERLAY_PATH": str(overlay),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "SYNC_LOG": str(log),
                    "SYNC_GIT_STATUS": "7",
                }
            )
            result = run(
                ["bash", str(ROOT / ".mise/tasks/sync")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("mise", log.read_text())

    def test_inventory_flake_app_is_built_on_every_supported_system(self) -> None:
        outputs = read("nix/outputs.nix")
        build = read(".github/scripts/build-platform-targets.sh")
        self.assertIn('name = "maison-inventory"', outputs)
        self.assertIn("runtimeInputs = [ pkgs.python3 ]", outputs)
        self.assertIn("MAISON_INVENTORY_SCHEMA", outputs)
        self.assertIn("maison-inventory = inventoryPackage", outputs)
        self.assertIn(r'build_target ".#packages.\"$SYSTEM\".\"$package\""', build)

    def test_build_matrix_has_no_home_manager_or_intel_target(self) -> None:
        build = read(".github/scripts/build-platform-targets.sh")
        self.assertNotIn("homeConfigurations", build)
        self.assertNotIn("x86_64-darwin", build)
        self.assertIn("systemConfigs", build)
        self.assertIn("darwinConfigurations", build)

    def test_ci_bootstrap_check_uses_current_test_module(self) -> None:
        workflow = read(".github/workflows/ci.yml")
        self.assertIn(
            "tests.test_migration_behavior.MigrationBehaviorTest.test_bootstrap_help_pipe_and_clone_handoff",
            workflow,
        )
        self.assertNotIn("test_topology.MigrationBehaviorTest", workflow)
        self.assertIn("mise exec --locked python -- python -m unittest", workflow)
        self.assertNotIn("          python3 -m unittest", workflow)

    def test_bootstrap_uses_template_and_current_user_for_copier(self) -> None:
        bootstrap = read("bootstrap.sh")
        self.assertIn('copier_user="$(id -un)"', bootstrap)
        self.assertIn('--data "username=$copier_user"', bootstrap)
        self.assertIn(
            "MAISON_OVERLAY_HOME     Copier destination; defaults to "
            "${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay.",
            bootstrap,
        )
        self.assertIn(
            "MAISON_OVERLAY_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay",
            bootstrap,
        )
        self.assertIn("overlay_template", bootstrap)
        self.assertNotIn("examples/", bootstrap)

    def test_cli_help_discovers_mise_tasks_and_forwards_command_help(self) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "MAISON_HOME": str(ROOT),
                "MISE_PROJECT_ROOT": str(ROOT),
            }
        )
        cli = ROOT / "bin/maison"
        overview = run(
            [str(cli)],
            cwd=Path(tempfile.gettempdir()),
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(overview.returncode, 0, overview.stderr)
        groups = (
            "workflow",
            "github",
            "app",
            "package",
            "tool",
            "host",
            "system",
            "user",
            "docs",
            "check",
        )
        for group in groups:
            with self.subTest(group=group):
                self.assertIn(f"{group}:\n", overview.stdout)
        for before, after in pairwise(groups):
            with self.subTest(group_order=f"{before} before {after}"):
                self.assertLess(overview.stdout.index(f"{before}:"), overview.stdout.index(f"{after}:"))
                self.assertIn(f"\n\n{after}:\n", overview.stdout)
        self.assertIn("package:\n  add             Install a package", overview.stdout)
        self.assertIn("host:\n  add             Add a host", overview.stdout)
        self.assertNotIn("package:add", overview.stdout)
        self.assertIn("  apply", overview.stdout)
        generated = run(
            [str(cli), "--help"],
            cwd=Path(tempfile.gettempdir()),
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("docs:\n", generated.stdout)
        for task in ("  fix", "  check", "  deployment:enable", "  update"):
            with self.subTest(task=task):
                self.assertIn(task, overview.stdout)

        for command, expected in (
            (("package", "search"), "Usage: package:search <query>"),
            (("package", "search", "--help"), "Usage: package:search <query>"),
            (("docs", "check"), "Task: docs:check"),
            (("docs", "deployment", "enable"), "Task: docs:deployment:enable"),
        ):
            with self.subTest(command=command):
                result = run(
                    [str(cli), "help", *command],
                    cwd=Path(tempfile.gettempdir()),
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout + result.stderr)

    def test_readme_quickstart_covers_supported_installation_paths_in_order(self) -> None:
        readme = read("README.md")
        sections = (
            "## Quickstart",
            "## Supported systems",
            "## Private overlay",
            "## Bootstrap behavior",
            "## Common commands",
            "## Deployment and recovery",
            "## Ownership boundary",
            "## Repository layout",
            "## Development",
        )
        positions = [readme.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(readme.count("curl -fsSL"), 2)
        self.assertIn("### 1. Install with curl and create an overlay during setup", readme)
        self.assertIn("### 2. Install with curl and use an existing overlay", readme)
        self.assertIn("### 3. Clone Maison and run Copier manually", readme)
        self.assertIn("git clone https://github.com/RobertDeRose/maison.git", readme)
        self.assertIn("copier copy --trust", readme)
        self.assertIn("overlay_template", readme)

    def test_template_documents_mise_dotfile_mapping(self) -> None:
        config = read("overlay_template/config/mise/config.toml")
        guide = read("overlay_template/dotfiles/README.md")
        self.assertIn("[dotfiles]", config)
        self.assertIn("mise.jdx.dev/dotfiles.html", guide)
        self.assertIn("mise bootstrap dotfiles", guide)

    def test_linux_user_creation_reuses_existing_primary_group(self) -> None:
        build = read(".github/scripts/build-platform-targets.sh")
        self.assertIn('if getent group "$username" > /dev/null 2>&1; then', build)
        self.assertIn(
            'sudo useradd --create-home --gid "$username" --comment "$fullname" --shell /bin/bash "$username"',
            build,
        )
        self.assertIn(
            'sudo useradd --create-home --user-group --comment "$fullname" --shell /bin/bash "$username"',
            build,
        )

    def test_all_task_root_discovery_supports_gitless_deployments(self) -> None:
        for path in sorted((ROOT / ".mise/tasks").rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text()
            if "rev-parse --show-toplevel" not in text:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIn("MISE_PROJECT_ROOT", text)


if __name__ == "__main__":
    unittest.main()
