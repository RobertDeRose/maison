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
                "system-manager",
            },
        )
        serialized = json.dumps(lock)
        self.assertNotIn("home-manager", serialized)
        self.assertNotIn('"deploy-rs"', serialized)

    def test_flake_lock_keeps_builder_fix_pinned(self) -> None:
        lock = json.loads(read("flake.lock"))["nodes"]
        nix_hex_box = lock["nix-hex-box"]["locked"]
        self.assertNotEqual(
            nix_hex_box["rev"],
            "136290b4bb817b4440968f8a852fe5806db4c021",
        )
        self.assertGreaterEqual(nix_hex_box["lastModified"], 1785842561)

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
    def test_all_mise_tasks_suppress_command_banners(self) -> None:
        task_files = sorted(path for path in (ROOT / ".mise/tasks").rglob("*") if path.is_file())
        self.assertTrue(task_files)
        for path in task_files:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIn("# [MISE] quiet=true", path.read_text().splitlines()[:4])

        tasks = tomllib.loads(read("mise.toml")).get("tasks", {})
        self.assertTrue(tasks)
        for name, task in tasks.items():
            with self.subTest(task=name):
                self.assertIs(task.get("quiet"), True)

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
        for command in (
            'cmd "check"',
            'cmd "system"',
            'cmd "user"',
            'cmd "deploy"',
            'cmd "self"',
        ):
            self.assertIn(command, cli)
        self.assertIn('export MISE_PROJECT_ROOT="$maison_home"', cli)

    def test_bootstrap_uses_the_locked_project_python(self) -> None:
        bootstrap = read("bootstrap.sh")
        cli = read("bin/maison")
        self.assertIn(
            "mise exec --locked python -- mise run --skip-tools bootstrap --",
            bootstrap,
        )
        self.assertIn("MAISON_CONSUMER_ROOT", bootstrap)
        self.assertIn(
            'exec "$mise_bin" exec --locked python -- "$mise_bin" run --skip-tools "$requested_task" --help',
            cli,
        )
        self.assertIn(
            'command=("$mise_bin" exec --locked python -- "$mise_bin" run --skip-tools)',
            cli,
        )

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

    def test_bootstrap_release_publishes_separate_checksum_asset(self) -> None:
        workflow = read(".github/workflows/bootstrap-release.yml")
        self.assertIn('tags:\n      - "v*"', workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertIn("sha256sum bootstrap.sh > SHA256SUMS", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("bootstrap.sh SHA256SUMS", workflow)

    def test_retired_repository_architecture_is_absent(self) -> None:
        retired_paths = (
            ROOT / ".mise/tasks/publish",
            ROOT / ".mise/tasks/status",
            ROOT / ".mise/tasks/sync",
            ROOT / ".mise/lib/repository_git.sh",
            ROOT / "scripts/maison_overlay.py",
            ROOT / "scripts/maison_repository_git.py",
            ROOT / "overlay_template",
        )
        for path in retired_paths:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertFalse(path.exists())

    def test_bootstrap_supports_immutable_commit_refs(self) -> None:
        bootstrap = read("bootstrap.sh")
        self.assertIn('if [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then', bootstrap)
        self.assertIn('git clone --no-checkout "$repo_url" "$repo_root"', bootstrap)
        self.assertIn('git -C "$repo_root" checkout --detach "$ref"', bootstrap)
        self.assertIn('git clone --branch "$ref" --single-branch "$repo_url" "$repo_root"', bootstrap)

    def test_bootstrap_selects_an_explicit_consumer(self) -> None:
        bootstrap = read("bootstrap.sh")
        self.assertIn("--consumer PATH", bootstrap)
        self.assertIn("MAISON_CONSUMER_ROOT", bootstrap)
        self.assertIn("is_consumer_checkout", bootstrap)

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
        self.assertIn("Maison — Votre maison, parfaitement ordonnée (Your home, perfectly ordered)", overview.stdout)
        self.assertIn(
            "A frontend for mise and Nix with a unified interface for managing multiple systems and user state.",
            overview.stdout,
        )
        self.assertIn("Available commands and their subcommands:\n", overview.stdout)
        groups = ("github", "app", "package", "tool", "host", "consumer", "self", "system", "user", "docs")
        workflow_rows = (
            "  apply",
            "  bootstrap",
            "  deploy",
            "  doctor",
            "  plan",
            "  rollback",
            "  update",
        )
        self.assertNotIn("workflow:\n", overview.stdout)
        self.assertNotIn("  fix", overview.stdout)
        self.assertNotIn("Apply deterministic repository fixes", overview.stdout)
        for row in workflow_rows:
            with self.subTest(row=row):
                self.assertIn(row, overview.stdout)
                self.assertLess(overview.stdout.index(row), overview.stdout.index("github:\n"))
        for group in groups:
            with self.subTest(group=group):
                self.assertIn(f"{group}:\n", overview.stdout)
        for before, after in pairwise(groups):
            with self.subTest(group_order=f"{before} before {after}"):
                self.assertLess(overview.stdout.index(f"{before}:"), overview.stdout.index(f"{after}:"))
                self.assertIn(f"\n\n{after}:\n", overview.stdout)
        self.assertIn("package:\n  add             Install a package", overview.stdout)
        self.assertIn("host:\n  add             Add a host", overview.stdout)
        self.assertIn("user:\n  apply", overview.stdout)
        self.assertIn("  restore         Restore a manifest-backed dotfile handoff backup", overview.stdout)
        self.assertIn("docs:\n  serve", overview.stdout)
        self.assertIn("[tasks.fix]", read("mise.toml"))
        self.assertIn('run = "hk fix -a"', read("mise.toml"))
        self.assertNotIn("check:\n", overview.stdout)
        self.assertNotIn("package:add", overview.stdout)
        self.assertNotIn("docs:\n  build", overview.stdout)
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
        self.assertNotIn("  fix", generated.stdout)
        for task in ("  serve", "  restore", "  update"):
            with self.subTest(task=task):
                self.assertIn(task, overview.stdout)

        for command, expected in (
            (("package", "search"), "Usage: package:search <query>"),
            (("package", "search", "--help"), "Usage: package:search <query>"),
            (("docs", "check"), "Task: docs:check"),
            (("docs", "deployment", "enable"), "Task: docs:deployment:enable"),
            (("user", "restore"), "Usage: user:restore-dotfiles"),
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

    def test_split_delivery_record_is_reconciled(self) -> None:
        record = "features/maison-017-maison-terroir-repository-split/index.md"
        roadmap = read("docs/src/planned-features.md")
        summary = read("docs/src/SUMMARY.md")
        feature_index = read("docs/src/features/index.md")

        self.assertTrue((ROOT / "docs/src" / record).is_file())
        self.assertRegex(
            roadmap,
            r"maison-017-maison-terroir-repository-split[^\n]+Delivered[^\n]+\[record\]",
        )
        self.assertIn(f"./{record}", summary)
        self.assertIn("maison-017-maison-terroir-repository-split/index.md", feature_index)

    def test_consumer_authoring_reader_contracts(self) -> None:
        readme = read("README.md")
        operations = read("docs/operations.md")
        task_reference = read("docs/task-reference.md")
        tooling = read("docs/src/reference/tooling.md")
        package_policy = read("docs/package-policy.md")
        tool_guide = read("docs/add-a-tool.md")
        app_guide = read("docs/add-an-app.md")
        summary = read("docs/src/SUMMARY.md")
        consumer_reference = read("docs/src/reference/consumer.md")

        self.assertNotIn("maison status", readme)
        self.assertNotIn("maison publish", readme)
        self.assertIn("consumer repository", operations)
        self.assertNotIn("last-known", operations)
        self.assertIn("focused-commit", task_reference)
        self.assertIn("consumer", tooling)
        self.assertIn("consumer repository", package_policy)
        self.assertIn("focused commit", tool_guide)
        self.assertIn("consumer", app_guide)
        self.assertIn("Consumer Repository Reference", summary)
        self.assertIn("MAISON_CONSUMER_ROOT", consumer_reference)
        self.assertIn("maison self update", consumer_reference)

    def test_readme_quickstart_covers_consumer_installation(self) -> None:
        readme = read("README.md")
        sections = (
            "## Quickstart",
            "## Consumer repository",
            "## Bootstrap behavior",
            "## Common commands",
            "## Deployment and recovery",
            "## Ownership boundary",
            "## Repository layout",
            "## Development",
        )
        positions = [readme.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))
        self.assertNotRegex(readme, r"curl[^\n|]*\|\s*(?:bash|sh)\b")
        self.assertIn("git clone git@github.com:RobertDeRose/terroir.git", readme)
        self.assertIn("MAISON_CONSUMER_ROOT", readme)
        self.assertIn("MAISON_BOOTSTRAP_VERSION", readme)

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
