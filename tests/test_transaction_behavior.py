from __future__ import annotations

from tests.support.topology import *


class TransactionBehaviorTest(unittest.TestCase):
    def make_config_repo(self, temp: Path) -> Path:
        repo = temp / "repo"
        (repo / "config/mise").mkdir(parents=True)
        (repo / ".git").mkdir()
        copy_files(
            repo,
            ".mise/lib/config_edit.py",
            ".mise/vendor/tomlkit-0.13.3-py3-none-any.whl",
            ".mise/lib/repository_mutation.py",
            ".mise/lib/transaction.sh",
            ".mise/lib/overlay.sh",
            ".mise/lib/overlay_git.sh",
            "scripts/maison_overlay.py",
            "scripts/maison_overlay_git.py",
            "scripts/user-apply-packages.sh",
        )
        return repo

    def make_overlay_repository(self, directory: Path, files: dict[str, str]) -> Path:
        overlay = directory / "overlay"
        overlay.mkdir(parents=True)
        for name, content in files.items():
            path = overlay / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        git_init(overlay)
        git_commit_all(overlay, "initial overlay")
        remote = directory / "overlay.git"
        run(
            ["git", "init", "--bare", "-q", str(remote)],
            env=fixture_git_env(),
            check=True,
        )
        run(
            ["git", "-C", str(overlay), "remote", "add", "origin", str(remote)],
            env=fixture_git_env(),
            check=True,
        )
        run(
            ["git", "-C", str(overlay), "push", "-q", "-u", "origin", "main"],
            env=fixture_git_env(),
            check=True,
        )
        run(
            [
                "git",
                "--git-dir",
                str(remote),
                "symbolic-ref",
                "HEAD",
                "refs/heads/main",
            ],
            env=fixture_git_env(),
            check=True,
        )
        return overlay

    def overlay_environment(self, overlay: Path, state: Path) -> dict[str, str]:
        return {
            "MAISON_OVERLAY_PATH": str(overlay),
            "MAISON_REPOSITORY_MUTATION_STATE_DIR": str(state),
        }

    def git(self, repository: Path, *arguments: str):
        return run(
            ["git", "-C", str(repository), *arguments],
            env=fixture_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )

    def test_host_add_restores_inventory_when_override_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = temp / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            copy_files(
                repo,
                ".mise/tasks/host/add",
                ".mise/lib/common.sh",
                ".mise/lib/platform.sh",
                ".mise/lib/inventory.sh",
                ".mise/lib/inventory.py",
                "schemas/inventory.toml",
                ".mise/lib/config_edit.py",
                ".mise/vendor/tomlkit-0.13.3-py3-none-any.whl",
                ".mise/lib/repository_mutation.py",
                ".mise/lib/transaction.sh",
                "inventory.toml",
            )
            original = (repo / "inventory.toml").read_text()
            (repo / "hosts").write_text("blocks directory creation\n")
            env = os.environ.copy()
            env.update(
                {
                    "MISE_PROJECT_ROOT": str(repo),
                    "usage_hostname": "rollback-host",
                    "usage_system": "aarch64-linux",
                    "usage_user": "operator",
                    "usage_profiles": "base,linux",
                    "usage_overrides": "true",
                }
            )
            result = run(
                [str(repo / ".mise/tasks/host/add")],
                env=env,
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((repo / "inventory.toml").read_text(), original)
            self.assertFalse((repo / "hosts/rollback-host").exists())

    def test_package_and_app_add_do_not_record_failed_installs(self) -> None:
        cases = [
            (
                ".mise/tasks/package/add",
                "config.toml",
                {"usage_package": "brew:new-package"},
            ),
            (
                ".mise/tasks/app/add",
                "config.macos-arm64.toml",
                {"usage_cask": "new-app"},
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (task_name, config_name, extra_env) in enumerate(cases):
                with self.subTest(task=task_name):
                    temp = root / str(index)
                    repo = self.make_config_repo(temp)
                    copy_files(repo, task_name)
                    overlay = self.make_overlay_repository(
                        temp,
                        {f"config/mise/{config_name}": '[bootstrap.packages]\n"brew:existing" = "latest"\n'},
                    )
                    config = overlay / "config/mise" / config_name
                    original = config.read_text()
                    fake_bin = temp / "bin"
                    fake_bin.mkdir(parents=True)
                    executable(
                        fake_bin / "mise",
                        "#!/bin/sh\necho unrelated failure >&2\nexit 23\n",
                    )
                    env = os.environ.copy()
                    env.update(extra_env)
                    env.update(self.overlay_environment(overlay, temp / "state"))
                    env["MISE_PROJECT_ROOT"] = str(repo)
                    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
                    result = run(
                        [str(repo / task_name)],
                        env=env,
                        cwd=repo,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(config.read_text(), original)

    def test_user_mutators_edit_the_active_overlay_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = self.make_config_repo(temp / "repo")
            copy_files(repo, ".mise/tasks/package/remove")
            public_config = repo / "config/mise/config.toml"
            public_config.write_text('[bootstrap.packages]\n"brew:public" = "latest"\n')
            overlay = self.make_overlay_repository(
                temp,
                {"config/mise/config.toml": '[bootstrap.packages]\n"brew:private" = "latest"\n'},
            )
            overlay_config = overlay / "config/mise/config.toml"
            before_public = public_config.read_text()
            env = os.environ.copy()
            env.update(self.overlay_environment(overlay, temp / "state"))
            env.update({"MISE_PROJECT_ROOT": str(repo), "usage_package": "brew:private"})
            result = run(
                [str(repo / ".mise/tasks/package/remove")],
                env=env,
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("config/mise/config.toml", result.stdout)
            self.assertEqual(public_config.read_text(), before_public)
            self.assertNotIn("brew:private", overlay_config.read_text())

    def test_mutation_rejects_dirty_target_and_preserves_unrelated_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = self.make_config_repo(temp)
            copy_files(repo, ".mise/tasks/package/remove")
            overlay = self.make_overlay_repository(
                temp,
                {"config/mise/config.toml": '[bootstrap.packages]\n"brew:private" = "latest"\n'},
            )
            config = overlay / "config/mise/config.toml"
            config.write_text('[bootstrap.packages]\n"brew:private" = "latest"\n\n# local edit\n')
            unrelated = overlay / "notes.txt"
            unrelated.write_text("keep this work\n")
            env = os.environ.copy()
            env.update(self.overlay_environment(overlay, temp / "state"))
            env.update({"MISE_PROJECT_ROOT": str(repo), "usage_package": "brew:private"})

            result = run(
                [str(repo / ".mise/tasks/package/remove")],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("mutation target is not clean", result.stderr)
            self.assertIn("brew:private", config.read_text())
            self.assertEqual(unrelated.read_text(), "keep this work\n")
            self.assertEqual(self.git(overlay, "rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_commit_failure_preserves_successful_declaration_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = self.make_config_repo(temp)
            copy_files(repo, ".mise/tasks/package/remove")
            overlay = self.make_overlay_repository(
                temp,
                {"config/mise/config.toml": '[bootstrap.packages]\n"brew:private" = "latest"\n'},
            )
            hook = overlay / ".git/hooks/pre-commit"
            hook.write_text("#!/bin/sh\nexit 19\n")
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env.update(self.overlay_environment(overlay, temp / "state"))
            env.update({"MISE_PROJECT_ROOT": str(repo), "usage_package": "brew:private"})

            result = run(
                [str(repo / ".mise/tasks/package/remove")],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("brew:private", (overlay / "config/mise/config.toml").read_text())
            self.assertIn("Manual recovery", result.stderr)
            self.assertEqual(self.git(overlay, "rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_package_and_app_add_commit_after_successful_install(self) -> None:
        cases = (
            (
                "package",
                ".mise/tasks/package/add",
                "config.toml",
                "brew:new",
                "added(package): `brew:new`",
            ),
            (
                "app",
                ".mise/tasks/app/add",
                "config.macos-arm64.toml",
                "ghostty",
                "added(app): `ghostty`",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (_, task_name, config_name, identifier, subject) in enumerate(cases):
                with self.subTest(task=task_name):
                    temp = root / str(index)
                    repo = self.make_config_repo(temp)
                    copy_files(repo, task_name)
                    package_name = identifier if identifier.startswith("brew:") else f"brew-cask:{identifier}"
                    overlay = self.make_overlay_repository(
                        temp,
                        {f"config/mise/{config_name}": '[bootstrap.packages]\n"brew:existing" = "latest"\n'},
                    )
                    fake_bin = temp / "bin"
                    fake_bin.mkdir(parents=True)
                    executable(fake_bin / "mise", "#!/bin/sh\nexit 0\n")
                    env = os.environ.copy()
                    env.update(self.overlay_environment(overlay, temp / "state"))
                    env.update(
                        {
                            "MISE_PROJECT_ROOT": str(repo),
                            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                            "usage_package": identifier,
                            "usage_cask": identifier,
                        }
                    )
                    run([str(repo / task_name)], cwd=repo, env=env, check=True)
                    self.assertEqual(
                        self.git(overlay, "log", "-1", "--format=%s").stdout.strip(),
                        subject,
                    )
                    self.assertIn(
                        package_name,
                        (overlay / "config/mise" / config_name).read_text(),
                    )

    def test_package_and_app_remove_commit_effective_identifiers(self) -> None:
        cases = (
            (
                "package",
                ".mise/tasks/package/remove",
                "config.toml",
                "brew:private",
                "removed(package): `brew:private`",
            ),
            (
                "app",
                ".mise/tasks/app/remove",
                "config.macos-arm64.toml",
                "ghostty",
                "removed(app): `ghostty`",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (_, task_name, config_name, identifier, subject) in enumerate(cases):
                with self.subTest(task=task_name):
                    temp = root / str(index)
                    repo = self.make_config_repo(temp)
                    copy_files(repo, task_name)
                    package_name = identifier if identifier.startswith("brew:") else f"brew-cask:{identifier}"
                    overlay = self.make_overlay_repository(
                        temp,
                        {f"config/mise/{config_name}": f'[bootstrap.packages]\n"{package_name}" = "latest"\n'},
                    )
                    env = os.environ.copy()
                    env.update(self.overlay_environment(overlay, temp / "state"))
                    env.update(
                        {
                            "MISE_PROJECT_ROOT": str(repo),
                            "usage_package": identifier,
                            "usage_cask": identifier,
                        }
                    )
                    run([str(repo / task_name)], cwd=repo, env=env, check=True)
                    self.assertEqual(
                        self.git(overlay, "log", "-1", "--format=%s").stdout.strip(),
                        subject,
                    )

    def test_add_mutators_refuse_public_fallback_without_overlay(self) -> None:
        cases = (
            (".mise/tasks/package/add", "config.toml", {"usage_package": "brew:new"}),
            (
                ".mise/tasks/app/add",
                "config.macos-arm64.toml",
                {"usage_cask": "new-app"},
            ),
            (".mise/tasks/tool/add", "config.toml", {"usage_tool": "aqua:owner/tool"}),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (task_name, config_name, extra_env) in enumerate(cases):
                with self.subTest(task=task_name):
                    temp = root / str(index)
                    repo = self.make_config_repo(temp)
                    copy_files(repo, task_name)
                    config = repo / "config/mise" / config_name
                    config.write_text('[bootstrap.packages]\n"brew:public" = "latest"\n')
                    before = config.read_bytes()
                    env = os.environ.copy()
                    env.update(extra_env)
                    env["MISE_PROJECT_ROOT"] = str(repo)
                    env.pop("MAISON_OVERLAY_PATH", None)
                    result = run(
                        [str(repo / task_name)],
                        cwd=repo,
                        env=env,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(config.read_bytes(), before)

    def test_remove_mutators_leave_config_unchanged_when_target_is_absent(self) -> None:
        cases = [
            (
                ".mise/tasks/package/remove",
                "config.toml",
                {"usage_package": "brew:missing"},
            ),
            (
                ".mise/tasks/app/remove",
                "config.macos-arm64.toml",
                {"usage_cask": "missing"},
            ),
            (".mise/tasks/tool/remove", "config.toml", {"usage_tool": "missing"}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (task_name, config_name, extra_env) in enumerate(cases):
                with self.subTest(task=task_name):
                    temp = root / str(index)
                    repo = self.make_config_repo(temp)
                    copy_files(repo, task_name)
                    config = repo / "config/mise" / config_name
                    if "tool/remove" in task_name:
                        config.write_text('[tools]\nnode = "24"\n')
                    else:
                        config.write_text('[bootstrap.packages]\n"brew:existing" = "latest"\n')
                    original = config.read_text()
                    env = os.environ.copy()
                    env.update(extra_env)
                    env["MISE_PROJECT_ROOT"] = str(repo)
                    result = run(
                        [str(repo / task_name)],
                        env=env,
                        cwd=repo,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(config.read_text(), original)

    def test_tool_remove_cannot_remove_maison_runtime_by_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            root = self.make_config_repo(temp)
            copy_files(root, ".mise/tasks/tool/remove")
            overlay = self.make_overlay_repository(
                temp,
                {
                    "config/mise/config.toml": '[tools]\nusage = "latest"\n',
                    "config/mise/mise.lock": '[[tools.usage]]\nversion = "1.0.0"\n',
                },
            )
            config = overlay / "config/mise/config.toml"
            lock = overlay / "config/mise/mise.lock"
            before_config = config.read_bytes()
            before_lock = lock.read_bytes()
            env = os.environ.copy()
            env.update(self.overlay_environment(overlay, temp / "state"))
            env.update({"MISE_PROJECT_ROOT": str(root), "usage_tool": "usage@latest"})
            result = run([str(root / ".mise/tasks/tool/remove")], env=env)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(config.read_bytes(), before_config)
            self.assertEqual(lock.read_bytes(), before_lock)

    def test_tool_remove_updates_config_and_lock_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = self.make_config_repo(temp)
            copy_files(repo, ".mise/tasks/tool/remove")
            original_lock = (
                '[[tools.node]]\nversion = "24.1.0"\nbackend = "core:node"\n\n'
                '[[tools.usage]]\nversion = "2.1.0"\nbackend = "aqua:jdx/usage"\n'
            )
            overlay = self.make_overlay_repository(
                temp,
                {
                    "config/mise/config.toml": '[tools]\nnode = "24"\nusage = "latest"\n',
                    "config/mise/mise.lock": original_lock,
                },
            )
            config = overlay / "config/mise/config.toml"
            lock = overlay / "config/mise/mise.lock"
            env = os.environ.copy()
            env.update(self.overlay_environment(overlay, temp / "state"))
            env.update({"MISE_PROJECT_ROOT": str(repo), "usage_tool": "node"})
            run(
                [str(repo / ".mise/tasks/tool/remove")],
                cwd=repo,
                env=env,
                check=True,
            )
            with config.open("rb") as handle:
                tools = tomllib.load(handle)["tools"]
            with lock.open("rb") as handle:
                locked = tomllib.load(handle)["tools"]
            self.assertNotIn("node", tools)
            self.assertNotIn("node", locked)
            self.assertIn("usage", tools)
            self.assertIn("usage", locked)

            env["usage_tool"] = "usage"
            refused = run(
                [str(repo / ".mise/tasks/tool/remove")],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(refused.returncode, 2)
            self.assertIn("command runtime", refused.stderr)

    def test_tool_remove_relocks_remaining_versions_transactionally(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = self.make_config_repo(temp)
            copy_files(repo, ".mise/tasks/tool/remove")
            original_config = '[settings]\nlockfile = true\n\n[tools]\nnode = ["24", "lts"]\nusage = "latest"\n'
            original_lock = (
                '[[tools.node]]\nversion = "24.18.0"\nbackend = "core:node"\n\n'
                '[[tools.node]]\nversion = "22.20.0"\nbackend = "core:node"\n\n'
                '[[tools.usage]]\nversion = "2.1.0"\nbackend = "aqua:jdx/usage"\n'
            )
            overlay = self.make_overlay_repository(
                temp,
                {
                    "config/mise/config.toml": original_config,
                    "config/mise/mise.lock": original_lock,
                },
            )
            config = overlay / "config/mise/config.toml"
            lock = overlay / "config/mise/mise.lock"
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "mise-log"
            executable(
                fake_bin / "mise",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    printf '%s\\n' "$*" >"$MISE_LOG"
                    [ "$1" = lock ] && [ "$2" = --global ] && [ "$3" = node ] || exit 12
                    grep -Fq 'node = "lts"' "$MISE_GLOBAL_CONFIG_FILE" || exit 13
                    cat >"$(dirname "$MISE_GLOBAL_CONFIG_FILE")/mise.lock" <<'EOF'
                    [[tools.node]]
                    version = "22.20.0"
                    backend = "core:node"

                    [[tools.usage]]
                    version = "2.1.0"
                    backend = "aqua:jdx/usage"
                    EOF
                    """
                ),
            )
            env = os.environ.copy()
            env.update(self.overlay_environment(overlay, temp / "state"))
            env.update(
                {
                    "MISE_PROJECT_ROOT": str(repo),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MISE_LOG": str(log),
                    "usage_tool": "node@24",
                }
            )
            run(
                [str(repo / ".mise/tasks/tool/remove")],
                cwd=repo,
                env=env,
                check=True,
            )
            self.assertEqual(tomllib.loads(config.read_text())["tools"]["node"], "lts")
            self.assertEqual(
                [entry["version"] for entry in tomllib.loads(lock.read_text())["tools"]["node"]],
                ["22.20.0"],
            )
            self.assertEqual(log.read_text().strip(), "lock --global node")

            config.write_text(original_config)
            lock.write_text(original_lock)
            git_commit_all(overlay, "restore original")
            executable(fake_bin / "mise", "#!/bin/sh\nexit 31\n")
            failed = run(
                [str(repo / ".mise/tasks/tool/remove")],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(failed.returncode, 31)
            self.assertEqual(config.read_text(), original_config)
            self.assertEqual(lock.read_text(), original_lock)

    def test_tool_add_rolls_back_config_and_lock_on_resolution_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = self.make_config_repo(temp)
            copy_files(repo, ".mise/tasks/tool/add")
            original_config = '[tools]\nnode = "24"\n'
            original_lock = "lock-before\n"
            overlay = self.make_overlay_repository(
                temp,
                {
                    "config/mise/config.toml": original_config,
                    "config/mise/mise.lock": original_lock,
                },
            )
            config = overlay / "config/mise/config.toml"
            lock = overlay / "config/mise/mise.lock"
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            executable(
                fake_bin / "mise",
                "#!/bin/sh\n"
                'printf "# lock-after\\n" >"$(dirname "$MISE_GLOBAL_CONFIG_FILE")/mise.lock"\n'
                "echo 'mise WARN Failed to resolve tool version list for broken'\n"
                "exit 0\n",
            )
            env = os.environ.copy()
            env.update(self.overlay_environment(overlay, temp / "state"))
            env.update(
                {
                    "MISE_PROJECT_ROOT": str(repo),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "usage_tool": "aqua:gastownhall/beads",
                    "usage_version": "latest",
                }
            )
            result = run(
                [str(repo / ".mise/tasks/tool/add")],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(config.read_text(), original_config)
            self.assertEqual(lock.read_text(), original_lock)
            self.assertIn("repository config and lock were not changed", result.stderr)

    def test_tool_add_restores_lock_when_config_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = self.make_config_repo(temp)
            copy_files(repo, ".mise/tasks/tool/add")
            original_config = '[tools]\nnode = "24"\n'
            original_lock = "lock-before\n"
            overlay = self.make_overlay_repository(
                temp,
                {
                    "config/mise/config.toml": original_config,
                    "config/mise/mise.lock": original_lock,
                },
            )
            config = overlay / "config/mise/config.toml"
            lock = overlay / "config/mise/mise.lock"
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            executable(
                fake_bin / "mise",
                "#!/bin/sh\n"
                'printf "# lock-after\n" >"$(dirname "$MISE_GLOBAL_CONFIG_FILE")/mise.lock"\n'
                "echo installed\n",
            )
            executable(
                fake_bin / "mv",
                "#!/bin/sh\n"
                'last=""; for arg in "$@"; do last="$arg"; done\n'
                'if [ "$last" = "$FAIL_DEST" ] && [ ! -e "$FAIL_MARKER" ]; then\n'
                '  : >"$FAIL_MARKER"; exit 71\n'
                "fi\n"
                'exec /bin/mv "$@"\n',
            )
            env = os.environ.copy()
            env.update(self.overlay_environment(overlay, temp / "state"))
            env.update(
                {
                    "MISE_PROJECT_ROOT": str(repo),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "usage_tool": "aqua:gastownhall/beads",
                    "usage_version": "1.1.0",
                    "FAIL_DEST": str(config.resolve()),
                    "FAIL_MARKER": str(temp / "failed-once"),
                }
            )
            result = run(
                [str(repo / ".mise/tasks/tool/add")],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(config.read_text(), original_config)
            self.assertEqual(lock.read_text(), original_lock)

    def test_tool_add_commits_config_and_candidate_lock_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = self.make_config_repo(temp)
            copy_files(repo, ".mise/tasks/tool/add")
            overlay = self.make_overlay_repository(
                temp,
                {
                    "config/mise/config.toml": '[tools]\nnode = "24"\n',
                    "config/mise/mise.lock": "lock-before\n",
                },
            )
            config = overlay / "config/mise/config.toml"
            lock = overlay / "config/mise/mise.lock"
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            executable(
                fake_bin / "mise",
                "#!/bin/sh\n"
                'printf "# lock-after\\n" >"$(dirname "$MISE_GLOBAL_CONFIG_FILE")/mise.lock"\n'
                "echo installed\n",
            )
            env = os.environ.copy()
            env.update(self.overlay_environment(overlay, temp / "state"))
            env.update(
                {
                    "MISE_PROJECT_ROOT": str(repo),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "usage_tool": "aqua:gastownhall/beads",
                    "usage_version": "1.1.0",
                }
            )
            run([str(repo / ".mise/tasks/tool/add")], cwd=repo, env=env, check=True)
            with config.open("rb") as handle:
                tools = tomllib.load(handle)["tools"]
            self.assertEqual(tools["aqua:gastownhall/beads"], "1.1.0")
            self.assertEqual(lock.read_text(), "# lock-after\n")
            self.assertEqual(
                self.git(overlay, "log", "-1", "--format=%s").stdout.strip(),
                "added(tool): `aqua:gastownhall/beads@1.1.0`",
            )
            self.assertEqual(
                set(
                    self.git(
                        overlay,
                        "diff-tree",
                        "--no-commit-id",
                        "--name-only",
                        "-r",
                        "HEAD",
                    ).stdout.split()
                ),
                {"config/mise/config.toml", "config/mise/mise.lock"},
            )
