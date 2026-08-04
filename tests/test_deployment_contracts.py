from __future__ import annotations

from tests.support.topology import *


class VerifiedBootstrapContractTest(unittest.TestCase):
    BOOTSTRAP_SOURCES = (
        "bootstrap.sh",
        ".mise/lib/bootstrap.sh",
        ".mise/tasks/deploy",
        "README.md",
    )

    def test_bootstrap_sources_do_not_pipe_downloads_to_shells(self) -> None:
        pattern = re.compile(r"(?:curl|wget)[^\n|;]*(?:\||>\s*\([^)]*)(?:[^\n]*(?:sh|bash))")
        offenders = []
        for name in self.BOOTSTRAP_SOURCES:
            text = read(name)
            if pattern.search(text):
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_remote_deploy_bootstrap_fallback_uses_bash_helpers(self) -> None:
        deploy_task = read(".mise/tasks/deploy")
        self.assertIn('"bash -s -- $quoted_repo$quoted_args"', deploy_task)
        self.assertNotIn('"sh -s -- $quoted_repo$quoted_args"', deploy_task)

    def test_operational_docs_do_not_recommend_pipe_to_shell(self) -> None:
        pattern = re.compile(r"curl[^\n]*\|\s*(?:bash|sh)\b")
        offenders = []
        for name in ("docs/operations.md", "docs/deployment.md", "docs/task-reference.md"):
            text = read(name)
            if pattern.search(text):
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_bootstrap_artifact_manifest_has_required_verification_metadata(self) -> None:
        manifest_path = ROOT / "bootstrap/artifacts.toml"
        self.assertTrue(manifest_path.exists(), "missing bootstrap/artifacts.toml")
        with manifest_path.open("rb") as handle:
            manifest = tomllib.load(handle)
        artifacts = manifest.get("artifacts")
        self.assertIsInstance(artifacts, dict)
        for name in ("mise", "lix"):
            with self.subTest(artifact=name):
                artifact = artifacts.get(name) if isinstance(artifacts, dict) else None
                self.assertIsInstance(artifact, dict)
                assert isinstance(artifact, dict)
                for field in ("version", "systems", "recovery_hint"):
                    self.assertIsInstance(artifact.get(field), str if field != "systems" else list)
                    self.assertTrue(artifact.get(field))
                platforms = artifact.get("platforms")
                self.assertIsInstance(platforms, dict)
                assert isinstance(platforms, dict)
                for system in ("aarch64-darwin", "aarch64-linux", "x86_64-linux"):
                    with self.subTest(artifact=name, system=system):
                        platform_data = platforms.get(system)
                        self.assertIsInstance(platform_data, dict)
                        assert isinstance(platform_data, dict)
                        self.assertIsInstance(platform_data.get("url"), str)
                        verification = platform_data.get("sha256") or platform_data.get("signature")
                        self.assertRegex(verification, r"^sha256:[0-9a-f]{64}$")

    def test_bootstrap_verifier_accepts_match_and_rejects_mismatch(self) -> None:
        helper = ROOT / "scripts/verify_bootstrap_artifact.py"
        self.assertTrue(helper.exists(), "missing scripts/verify_bootstrap_artifact.py")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            artifact = temp / "artifact.sh"
            artifact.write_text("#!/bin/sh\necho verified\n")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = temp / "artifacts.toml"
            manifest.write_text(
                "[artifacts.fixture]\n"
                'version = "1.0.0"\n'
                f'url = "file://{artifact}"\n'
                f'sha256 = "sha256:{digest}"\n'
                'systems = ["aarch64-darwin", "aarch64-linux", "x86_64-linux"]\n'
                'recovery_hint = "retry with a reviewed artifact"\n'
            )
            ok = run(
                [str(helper), "--manifest", str(manifest), "fixture", str(artifact)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(ok.returncode, 0, ok.stderr)

            artifact.write_text("tampered\n")
            refused = run(
                [str(helper), "--manifest", str(manifest), "fixture", str(artifact)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("checksum", refused.stderr.lower())

    def test_copier_bootstrap_uses_hashed_repository_lock(self) -> None:
        bootstrap = read("bootstrap.sh")
        readme = read("README.md")
        requirements = read("bootstrap/copier-requirements.txt")
        source = f"{bootstrap}\n{readme}"

        self.assertNotIn("uvx --from copier", source)
        self.assertIn(
            'uv pip install \\\n      --python "$copier_env/bin/python" \\\n      --require-hashes', bootstrap
        )
        self.assertIn("bootstrap/copier-requirements.txt", source)
        self.assertIn("copier==9.17.0", requirements)
        self.assertIn("copier==9.17.0 \\\n    --hash=sha256:", requirements)

    def test_bootstrap_runtime_plugins_and_tools_are_immutable(self) -> None:
        project_config = tomllib.loads(read("mise.toml"))
        runtime_tools = {"usage": project_config["tools"]["usage"]}
        for name, value in runtime_tools.items():
            with self.subTest(tool=name):
                self.assertNotEqual(value, "latest")
                self.assertNotRegex(str(value), r"^(main|master|dev|HEAD)$")

        mutable_plugins = []
        for config_name in ("config/mise/config.toml", "mise.toml"):
            plugins = tomllib.loads(read(config_name)).get("plugins", {})
            for name, source in plugins.items():
                if re.fullmatch(r"[0-9a-f]{40}", str(source).rsplit("#", 1)[-1]) is None:
                    mutable_plugins.append(f"{config_name}:{name}")
        self.assertEqual(mutable_plugins, [])

    def test_non_bootstrap_latest_tools_remain_allowed_when_locked(self) -> None:
        config = tomllib.loads(read("config/mise/config.toml")).get("tools", {})
        lock = tomllib.loads(read("config/mise/mise.lock")).get("tools", {})
        ordinary_latest_tools = {name for name, version in config.items() if version == "latest"}
        self.assertEqual(ordinary_latest_tools, set())
        self.assertEqual(set(lock), set())


class RootDeploymentEvaluationContractTest(unittest.TestCase):
    def test_root_deployment_evaluates_without_root_owned_policy(self) -> None:
        if shutil.which("nix") is None:
            self.skipTest("nix is required for root deployment evaluation")

        fixture = ROOT / "tests/fixtures/inventory/valid/root-deployment"
        result = run(
            [
                "nix",
                "--accept-flake-config",
                "--extra-experimental-features",
                "nix-command flakes",
                "eval",
                "--no-update-lock-file",
                "--override-input",
                "overlay",
                f"path:{fixture}",
                "--json",
                ".#systemConfigs.root-bootstrap",
                "--apply",
                (
                    "configuration: { "
                    "rootHome = configuration.config.users.users.root.home; "
                    "rootGroup = configuration.config.users.groups.root.name; "
                    "rootIsSystemUser = configuration.config.users.users.root.isSystemUser; "
                    "hasDeploymentSudoers = builtins.hasAttr "
                    '"sudoers.d/90-system-manager-wheel" configuration.config.environment.etc; '
                    "}"
                ),
            ],
            cwd=ROOT,
            timeout=180,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "hasDeploymentSudoers": False,
                "rootGroup": "root",
                "rootHome": "/root",
                "rootIsSystemUser": False,
            },
        )


class DeploymentContractTest(unittest.TestCase):
    def deployment_environment(self, temp: Path, home: Path) -> tuple[str, dict[str, str]]:
        """Provide a deterministic portable Linux deployment user."""

        user = "maison-test"
        real_mv = shutil.which("mv")
        real_tar = shutil.which("tar")
        if real_mv is None or real_tar is None:
            self.skipTest("mv and tar are required for deployment contract tests")
        fake_bin = temp / "deployment-bin"
        executable(
            fake_bin / "id",
            textwrap.dedent(
                f"""\
                #!/bin/sh
                case "${{1:-}}" in
                  -u) printf '%s\\n' 501 ;;
                  -un) printf '%s\\n' {user} ;;
                  {user}) exit 0 ;;
                  *) exit 1 ;;
                esac
                """
            ),
        )
        executable(
            fake_bin / "mv",
            textwrap.dedent(
                """\
                #!/bin/sh
                case "${1:-}" in
                  --version | -T) exit 64 ;;
                esac
                exec "$MAISON_TEST_REAL_MV" "$@"
                """
            ),
        )
        executable(
            fake_bin / "tar",
            textwrap.dedent(
                """\
                #!/bin/sh
                [ "${1:-}" != --no-same-owner ] || exit 64
                exec "$MAISON_TEST_REAL_TAR" "$@"
                """
            ),
        )
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                "MAISON_MANAGED_HOME": str(home),
                "MAISON_TEST_REAL_MV": real_mv,
                "MAISON_TEST_REAL_TAR": real_tar,
                "MAISON_TRANSACTION_EXPECTED_OWNER_UID": str(os.getuid()),
            }
        )
        return user, env

    def transaction_namespace(self, repo: Path, user: str, home: Path) -> Path:
        digest = hashlib.sha256(str(repo).encode()).hexdigest()[:16]
        return home.parent / ".maison-deploy" / "transactions" / user / digest

    def test_deploy_rs_activates_exact_system_manager_profile(self) -> None:
        deployment = read("nix/lib/deployments.nix")
        adapter = read("nix/lib/deploy-rs.nix")
        self.assertIn("/nix/var/nix/profiles/system-manager-profiles/system-manager", deployment)
        self.assertIn("deployRs.mkActivation", deployment)
        self.assertIn("base = systemConfigs.${name}", deployment)
        self.assertIn('"$PROFILE/bin/activate"', deployment)
        self.assertIn("boot = activateSystem", deployment)
        self.assertIn("DRY_ACTIVATE=1", adapter)
        self.assertIn("magicRollback", deployment)
        self.assertIn("autoRollback", deployment)

    def test_deploy_rs_uses_one_nixpkgs_package_revision(self) -> None:
        flake = read("flake.nix")
        outputs = read("nix/outputs.nix")
        adapter = read("nix/lib/deploy-rs.nix")
        self.assertNotIn("github:serokell/deploy-rs", flake)
        self.assertNotIn("inputs.deploy-rs", outputs)
        self.assertIn("deployPackage = pkgs.deploy-rs", adapter)
        self.assertIn("${deployPackage}/bin/activate", adapter)
        self.assertIn("pkgs.symlinkJoin", adapter)
        self.assertIn("${deploySource}/interface.json", adapter)

    def test_upstream_system_manager_tests_remain_enabled(self) -> None:
        self.assertFalse((ROOT / "nix/lib/system-manager-no-check-overlay.nix").exists())
        combined = "\n".join(path.read_text() for path in (ROOT / "nix").rglob("*.nix"))
        self.assertNotIn("doCheck = false", combined)
        self.assertIn("Keep upstream Rust checks enabled", read("nix/lib/mk-linux-host.nix"))

    def test_nix_checks_are_realized_in_ci(self) -> None:
        check = read(".mise/tasks/check/nix")
        matrix = read(".github/scripts/build-platform-targets.sh")
        self.assertIn("run_nix_checked build", check)
        self.assertIn(".#checks.", check)
        self.assertIn('attribute_names ".#checks.', matrix)
        self.assertIn('build_target ".#checks.', matrix)

    def test_rollbacks_do_not_double_advance_darwin_profile(self) -> None:
        script = read(".mise/tasks/system/rollback")
        darwin_block = script.split("Darwin)", 1)[1].split("Linux)", 1)[0]
        self.assertIn("darwin-rebuild switch --rollback", darwin_block)
        self.assertLess(
            darwin_block.index("darwin-rebuild switch --rollback"),
            darwin_block.index("nix-env --rollback"),
        )
        self.assertEqual(darwin_block.count("nix-env --rollback"), 1)

    def test_deploy_adapter_uses_command_scoped_privilege_boundaries(self) -> None:
        deploy_task = read(".mise/tasks/deploy")
        system_task = read(".mise/tasks/system/deploy")
        linux_module = read("nix/modules/linux/system.nix")

        self.assertIn('sudo_prefix=""', deploy_task)
        self.assertIn("${sudo_prefix}$quoted_helper recover", deploy_task)
        self.assertIn("${sudo_prefix}$quoted_helper stage", deploy_task)
        self.assertIn("${sudo_prefix}$quoted_helper finalize", deploy_task)
        self.assertIn('remote_helper="/etc/maison/maison-deploy-transaction"', deploy_task)
        self.assertIn('if [ "$ssh_user" != root ]; then', system_task)
        self.assertIn("/usr/bin/install -d -m 0755 /nix/var/nix/profiles/system-manager-profiles", system_task)

        self.assertIn(
            "Cmnd_Alias MAISON_DEPLOY_HELPER = /etc/maison/maison-deploy-transaction recover,",
            linux_module,
        )
        self.assertIn(
            "/etc/maison/maison-deploy-transaction stage /tmp/maison-deploy.??????.tar.gz,",
            linux_module,
        )
        self.assertNotIn("/usr/bin/python3 /tmp/maison-deploy-helper", linux_module)
        self.assertIn("transactionHelper", linux_module)
        self.assertIn("maison-deploy-transaction", linux_module)
        self.assertIn(
            "Cmnd_Alias MAISON_DEPLOY_PREPARE = /usr/bin/install -d -m 0755 /nix/var/nix/profiles/system-manager-profiles",
            linux_module,
        )
        self.assertIn("Cmnd_Alias MAISON_DEPLOY_ACTIVATE = /nix/store/*/activate-rs *", linux_module)
        trusted_users = re.search(r"extra-trusted-users = ([^\n]+)", linux_module)
        self.assertIsNotNone(trusted_users)
        assert trusted_users is not None
        self.assertEqual(trusted_users.group(1), "root")
        self.assertIn(
            'extra-substituters = ${builtins.concatStringsSep " " cache.substituters}',
            linux_module,
        )
        self.assertIn(
            'extra-trusted-public-keys = ${builtins.concatStringsSep " " cache.trustedPublicKeys}',
            linux_module,
        )
        self.assertIn("${deployUser} ALL=(root) NOPASSWD:", linux_module)
        self.assertNotIn("NOPASSWD: ALL", linux_module)

    def test_root_deployment_does_not_define_or_grant_root(self) -> None:
        linux_module = read("nix/modules/linux/system.nix")
        self.assertIn('users.users."${deployUser}" = lib.mkIf (deployUser != "root")', linux_module)
        self.assertIn('users.groups."${deployUser}" = lib.mkIf (deployUser != "root")', linux_module)
        self.assertIn(
            'environment.etc."sudoers.d/90-system-manager-wheel" = lib.mkIf (deployUser != "root")',
            linux_module,
        )

    def test_deploy_is_two_explicit_transactions(self) -> None:
        script = read(".mise/tasks/deploy")
        self.assertIn("scripts/create-deploy-archive.sh", script)
        self.assertNotIn("scripts/maison_deploy_transaction.py", script)
        self.assertIn("mktemp /tmp/maison-deploy.XXXXXX.tar.gz", script)
        self.assertIn("/etc/maison/maison-deploy-transaction", script)
        self.assertNotIn("maison-deploy-helper.", script)
        self.assertNotIn("maison-deploy-${host}-$$", script)
        self.assertIn("mise run system:deploy", script)
        self.assertIn("mise run user:apply", script)
        self.assertLess(script.index("mise run system:deploy"), script.index("mise run user:apply"))

    def test_deploy_archive_contains_committed_content_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = temp / "repo"
            repo.mkdir()
            (repo / "mise.toml").write_text("[settings]\n")
            (repo / "flake.nix").write_text("{}\n")
            (repo / "tracked.txt").write_text("tracked\n")
            (repo / ".gitignore").write_text("ignored-secret\n")
            git_init(repo)
            revision = git_commit_all(repo)
            (repo / "ignored-secret").write_text("must not deploy\n")

            archive = temp / "deploy.tar.gz"
            run(
                [str(ROOT / "scripts/create-deploy-archive.sh"), str(repo), str(archive)],
                check=True,
            )
            with tarfile.open(archive, "r:gz") as bundle:
                names = {name.removeprefix("./") for name in bundle.getnames()}
                self.assertIn("tracked.txt", names)
                self.assertIn(".maison-revision", names)
                self.assertNotIn(".git", names)
                self.assertNotIn("ignored-secret", names)
                revision_file = bundle.extractfile("./.maison-revision") or bundle.extractfile(".maison-revision")
                assert revision_file is not None
                self.assertEqual(revision_file.read().decode().strip(), revision)

            (repo / "untracked-secret").write_text("must fail\n")
            refused = run(
                [str(ROOT / "scripts/create-deploy-archive.sh"), str(repo), str(temp / "refused.tar.gz")],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("clean working tree", refused.stderr)

    def test_repository_stage_rolls_back_and_commits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            user, env = self.deployment_environment(temp, home)
            repo = home / ".maison"
            repo.mkdir()
            (repo / "old-marker").write_text("old\n")

            def make_archive(path: Path, revision: str) -> None:
                source = temp / f"source-{revision}"
                source.mkdir()
                (source / "mise.toml").write_text("[settings]\n")
                (source / "flake.nix").write_text("{}\n")
                (source / ".maison-revision").write_text(f"{revision}\n")
                with tarfile.open(path, "w:gz") as bundle:
                    for child in source.iterdir():
                        bundle.add(child, arcname=child.name)

            archive = temp / "one.tar.gz"
            revision_one = "1" * 40
            make_archive(archive, revision_one)
            run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(repo), user, str(archive)],
                env=env,
                check=True,
            )
            namespace = self.transaction_namespace(repo, user, home)
            self.assertEqual((repo / ".maison-revision").read_text().strip(), revision_one)
            active = namespace / "active.json"
            record = json.loads(active.read_text())
            self.assertTrue((Path(record["rollback_dir"]) / "old-marker").exists())
            self.assertTrue(Path(record["journal_path"]).exists())
            self.assertTrue((namespace / "transaction.lock").exists())
            run(
                [str(ROOT / "scripts/finalize-deploy-repository.sh"), str(repo), user, "rollback"],
                env=env,
                check=True,
            )
            self.assertTrue((repo / "old-marker").exists())
            self.assertFalse(active.exists())

            archive = temp / "two.tar.gz"
            revision_two = "2" * 40
            make_archive(archive, revision_two)
            run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(repo), user, str(archive)],
                env=env,
                check=True,
            )
            run(
                [str(ROOT / "scripts/finalize-deploy-repository.sh"), str(repo), user, "commit"],
                env=env,
                check=True,
            )
            self.assertEqual((repo / ".maison-revision").read_text().strip(), revision_two)
            self.assertFalse((namespace / "active.json").exists())

            unsafe = run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(temp / "outside"), user, str(temp / "missing")],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(unsafe.returncode, 0)
            self.assertIn("must be below", unsafe.stderr)

            dot_segment = run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(home / "nested/.."), user, str(archive)],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(dot_segment.returncode, 0)
            self.assertIn("dot segments", dot_segment.stderr)

            archive_link = temp / "archive-link.tar.gz"
            archive_link.symlink_to(archive)
            symlink_archive = run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(home / "other"), user, str(archive_link)],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(symlink_archive.returncode, 0)
            self.assertIn("regular non-symlink", symlink_archive.stderr)

    def test_repository_stage_restores_active_repo_when_archive_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            user, env = self.deployment_environment(temp, home)
            repo = home / ".maison"
            repo.mkdir()
            (repo / "old-marker").write_text("old\n")
            source = temp / "invalid-source"
            source.mkdir()
            (source / "mise.toml").write_text("[settings]\n")
            (source / ".maison-revision").write_text(f"{'4' * 40}\n")
            archive = temp / "invalid.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for child in source.iterdir():
                    bundle.add(child, arcname=child.name)

            failed = run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(repo), user, str(archive)],
                env=env,
                capture_output=True,
                text=True,
            )

            namespace = self.transaction_namespace(repo, user, home)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("missing regular file flake.nix", failed.stderr)
            self.assertTrue((repo / "old-marker").exists())
            self.assertFalse((namespace / "active.json").exists())

    def test_repository_stage_rejects_symlink_archive_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            user, env = self.deployment_environment(temp, home)
            repo = home / ".maison"
            source = temp / "source"
            source.mkdir()
            (source / "mise.toml").write_text("[settings]\n")
            (source / "flake.nix").write_text("{}\n")
            (source / ".maison-revision").write_text(f"{'5' * 40}\n")
            (source / "link").symlink_to("mise.toml")
            archive = temp / "symlink-member.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for child in source.iterdir():
                    bundle.add(child, arcname=child.name)

            failed = run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(repo), user, str(archive)],
                env=env,
                capture_output=True,
                text=True,
            )

            namespace = self.transaction_namespace(repo, user, home)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("unsupported type: link", failed.stderr)
            self.assertFalse(repo.exists())
            self.assertFalse((namespace / "active.json").exists())

    def test_finalize_never_deletes_active_repo_when_previous_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            user, env = self.deployment_environment(temp, home)

            repo = home / ".maison"
            repo.mkdir()
            (repo / "old-marker").write_text("old\n")
            source = temp / "source"
            source.mkdir()
            (source / "mise.toml").write_text("[settings]\n")
            (source / "flake.nix").write_text("{}\n")
            revision = "3" * 40
            (source / ".maison-revision").write_text(f"{revision}\n")
            archive = temp / "deploy.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for child in source.iterdir():
                    bundle.add(child, arcname=child.name)

            run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(repo), user, str(archive)],
                env=env,
                check=True,
            )
            namespace = self.transaction_namespace(repo, user, home)
            active = namespace / "active.json"
            record = json.loads(active.read_text())
            shutil.rmtree(Path(record["rollback_dir"]))
            failed = run(
                [str(ROOT / "scripts/finalize-deploy-repository.sh"), str(repo), user, "rollback"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("previous repository is missing or unsafe", failed.stderr)
            self.assertEqual((repo / ".maison-revision").read_text().strip(), revision)
            self.assertTrue(active.exists())

    def test_repository_stage_records_revision_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            user, env = self.deployment_environment(temp, home)

            repo = home / ".maison"
            repo.mkdir()
            old_revision = "1" * 40
            (repo / "mise.toml").write_text("[settings]\n")
            (repo / "flake.nix").write_text("{}\n")
            (repo / ".maison-revision").write_text(f"{old_revision}\n")

            source = temp / "source"
            source.mkdir()
            new_revision = "2" * 40
            (source / "mise.toml").write_text("[settings]\n")
            (source / "flake.nix").write_text("{}\n")
            (source / ".maison-revision").write_text(f"{new_revision}\n")
            archive = temp / "deploy.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for child in source.iterdir():
                    bundle.add(child, arcname=child.name)

            run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(repo), user, str(archive)],
                env=env,
                check=True,
            )
            namespace = self.transaction_namespace(repo, user, home)
            active = namespace / "active.json"
            record = json.loads(active.read_text())
            self.assertEqual(record["revision"], new_revision)
            self.assertEqual(record["expected_new_revision"], new_revision)
            self.assertEqual(record["expected_old_revision"], old_revision)
            self.assertEqual(record["state"], "previous")

            journal = [json.loads(line) for line in Path(record["journal_path"]).read_text().splitlines()]
            self.assertTrue(any(line["event"] == "archive-extracted" for line in journal))
            self.assertTrue(any(line["event"] == "staged" for line in journal))
            self.assertEqual(Path(record["journal_path"]).exists(), True)

            run(
                [str(ROOT / "scripts/finalize-deploy-repository.sh"), str(repo), user, "rollback"],
                env=env,
                check=True,
            )

    def test_finalize_rejects_previous_revision_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            user, env = self.deployment_environment(temp, home)

            repo = home / ".maison"
            repo.mkdir()
            old_revision = "1" * 40
            (repo / "mise.toml").write_text("[settings]\n")
            (repo / "flake.nix").write_text("{}\n")
            (repo / ".maison-revision").write_text(f"{old_revision}\n")

            source = temp / "source"
            source.mkdir()
            new_revision = "2" * 40
            (source / "mise.toml").write_text("[settings]\n")
            (source / "flake.nix").write_text("{}\n")
            (source / ".maison-revision").write_text(f"{new_revision}\n")
            archive = temp / "deploy.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for child in source.iterdir():
                    bundle.add(child, arcname=child.name)

            run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(repo), user, str(archive)],
                env=env,
                check=True,
            )
            namespace = self.transaction_namespace(repo, user, home)
            record = json.loads((namespace / "active.json").read_text())
            rollback_repo = Path(record["rollback_dir"])
            (rollback_repo / ".maison-revision").write_text("b" * 40 + "\n")

            failed = run(
                [str(ROOT / "scripts/finalize-deploy-repository.sh"), str(repo), user, "commit"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("previous repository revision mismatch", failed.stderr)

            run(
                [str(ROOT / "scripts/finalize-deploy-repository.sh"), str(repo), user, "rollback"],
                env=env,
                check=True,
            )

    def test_finalize_rejects_active_revision_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            user, env = self.deployment_environment(temp, home)

            repo = home / ".maison"
            repo.mkdir()
            old_revision = "1" * 40
            (repo / "mise.toml").write_text("[settings]\n")
            (repo / "flake.nix").write_text("{}\n")
            (repo / ".maison-revision").write_text(f"{old_revision}\n")

            source = temp / "source"
            source.mkdir()
            new_revision = "2" * 40
            (source / "mise.toml").write_text("[settings]\n")
            (source / "flake.nix").write_text("{}\n")
            (source / ".maison-revision").write_text(f"{new_revision}\n")
            archive = temp / "deploy.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for child in source.iterdir():
                    bundle.add(child, arcname=child.name)

            run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(repo), user, str(archive)],
                env=env,
                check=True,
            )
            (repo / ".maison-revision").write_text("9" * 40 + "\n")

            failed = run(
                [str(ROOT / "scripts/finalize-deploy-repository.sh"), str(repo), user, "commit"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("active repository revision mismatch", failed.stderr)

    def test_recover_rolls_back_incomplete_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            user, env = self.deployment_environment(temp, home)

            repo = home / ".maison"
            repo.mkdir()
            old_revision = "1" * 40
            (repo / "mise.toml").write_text("[settings]\n")
            (repo / "flake.nix").write_text("{}\n")
            (repo / ".maison-revision").write_text(f"{old_revision}\n")

            source = temp / "source"
            source.mkdir()
            new_revision = "2" * 40
            (source / "mise.toml").write_text("[settings]\n")
            (source / "flake.nix").write_text("{}\n")
            (source / ".maison-revision").write_text(f"{new_revision}\n")
            archive = temp / "deploy.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for child in source.iterdir():
                    bundle.add(child, arcname=child.name)

            run(
                [str(ROOT / "scripts/deploy-repository.sh"), str(repo), user, str(archive)],
                env=env,
                check=True,
            )
            namespace = self.transaction_namespace(repo, user, home)
            self.assertTrue((namespace / "active.json").exists())
            self.assertEqual((repo / ".maison-revision").read_text().strip(), new_revision)

            recovered = run(
                [str(ROOT / "scripts/maison_deploy_transaction.py"), "recover", str(repo), user],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(recovered.returncode, 0)
            self.assertIn(f"Recovered incomplete Maison repository transaction at {repo}", recovered.stdout)
            self.assertEqual((repo / ".maison-revision").read_text().strip(), old_revision)
            self.assertFalse((namespace / "active.json").exists())
