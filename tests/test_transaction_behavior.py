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
            "scripts/user-apply-packages.sh",
        )
        return repo

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
            (".mise/tasks/package/add", "config.toml", {"usage_package": "brew:new-package"}),
            (".mise/tasks/app/add", "config.macos-arm64.toml", {"usage_cask": "new-app"}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (task_name, config_name, extra_env) in enumerate(cases):
                with self.subTest(task=task_name):
                    temp = root / str(index)
                    repo = self.make_config_repo(temp)
                    copy_files(repo, task_name)
                    config = repo / "config/mise" / config_name
                    config.write_text('[bootstrap.packages]\n"brew:existing" = "latest"\n')
                    original = config.read_text()
                    fake_bin = temp / "bin"
                    fake_bin.mkdir(parents=True)
                    executable(fake_bin / "mise", "#!/bin/sh\necho unrelated failure >&2\nexit 23\n")
                    env = os.environ.copy()
                    env.update(extra_env)
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

    def test_remove_mutators_leave_config_unchanged_when_target_is_absent(self) -> None:
        cases = [
            (".mise/tasks/package/remove", "config.toml", {"usage_package": "brew:missing"}),
            (".mise/tasks/app/remove", "config.macos-arm64.toml", {"usage_cask": "missing"}),
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
            config = root / "config/mise/config.toml"
            lock = root / "config/mise/mise.lock"
            config.write_text('[tools]\nusage = "latest"\n')
            lock.write_text('[[tools.usage]]\nversion = "1.0.0"\n')
            before_config = config.read_bytes()
            before_lock = lock.read_bytes()
            env = os.environ.copy()
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
            config = repo / "config/mise/config.toml"
            lock = repo / "config/mise/mise.lock"
            config.write_text('[tools]\nnode = "24"\nusage = "latest"\n')
            lock.write_text(
                '[[tools.node]]\nversion = "24.1.0"\nbackend = "core:node"\n\n'
                '[[tools.usage]]\nversion = "2.1.0"\nbackend = "aqua:jdx/usage"\n'
            )
            env = os.environ.copy()
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
            config = repo / "config/mise/config.toml"
            lock = repo / "config/mise/mise.lock"
            original_config = '[settings]\nlockfile = true\n\n[tools]\nnode = ["24", "lts"]\nusage = "latest"\n'
            original_lock = (
                '[[tools.node]]\nversion = "24.18.0"\nbackend = "core:node"\n\n'
                '[[tools.node]]\nversion = "22.20.0"\nbackend = "core:node"\n\n'
                '[[tools.usage]]\nversion = "2.1.0"\nbackend = "aqua:jdx/usage"\n'
            )
            config.write_text(original_config)
            lock.write_text(original_lock)
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
            config = repo / "config/mise/config.toml"
            lock = repo / "config/mise/mise.lock"
            original_config = '[tools]\nnode = "24"\n'
            original_lock = "lock-before\n"
            config.write_text(original_config)
            lock.write_text(original_lock)
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
            env.update(
                {
                    "MISE_PROJECT_ROOT": str(repo),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "usage_tool": "aqua:gastownhall/beads",
                    "usage_version": "latest",
                }
            )
            result = run([str(repo / ".mise/tasks/tool/add")], cwd=repo, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(config.read_text(), original_config)
            self.assertEqual(lock.read_text(), original_lock)
            self.assertIn("repository config and lock were not changed", result.stderr)

    def test_tool_add_restores_lock_when_config_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = self.make_config_repo(temp)
            copy_files(repo, ".mise/tasks/tool/add")
            config = repo / "config/mise/config.toml"
            lock = repo / "config/mise/mise.lock"
            original_config = '[tools]\nnode = "24"\n'
            original_lock = "lock-before\n"
            config.write_text(original_config)
            lock.write_text(original_lock)
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
            env.update(
                {
                    "MISE_PROJECT_ROOT": str(repo),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "usage_tool": "aqua:gastownhall/beads",
                    "usage_version": "1.1.0",
                    "FAIL_DEST": str(config),
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
            config = repo / "config/mise/config.toml"
            lock = repo / "config/mise/mise.lock"
            config.write_text('[tools]\nnode = "24"\n')
            lock.write_text("lock-before\n")
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            executable(
                fake_bin / "mise",
                "#!/bin/sh\n"
                'printf "# lock-after\\n" >"$(dirname "$MISE_GLOBAL_CONFIG_FILE")/mise.lock"\n'
                "echo installed\n",
            )
            env = os.environ.copy()
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
