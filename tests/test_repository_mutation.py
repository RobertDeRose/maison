from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.support.processes import (
    DEVNULL,
    CompletedProcess,
    run,
    start_process,
    terminate_process_tree,
)

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".mise/lib/repository_mutation.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("repository_mutation", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryMutationLockTest(unittest.TestCase):
    def helper(self, state_root: Path, *args: str) -> CompletedProcess[str]:
        env = os.environ.copy()
        env["MAISON_REPOSITORY_MUTATION_STATE_DIR"] = str(state_root)
        return run(
            [sys.executable, str(HELPER), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_state_directory_is_untracked_owner_only_and_keyed_by_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = temp / "repo"
            repo.mkdir()
            state_root = temp / "state"
            helper = load_helper()

            state = helper.repository_state(repo, state_root=state_root)

            self.assertTrue(state.directory.is_dir())
            self.assertEqual(state.directory.stat().st_mode & 0o777, 0o700)
            self.assertTrue(str(state.directory).startswith(str(state_root)))
            self.assertIn(helper.repository_key(repo), state.directory.name)
            self.assertFalse(str(state.directory).startswith(str(repo)))

    def test_run_fails_fast_when_repository_lock_is_busy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = temp / "repo"
            repo.mkdir()
            state_root = temp / "state"
            holder = start_process(
                [
                    sys.executable,
                    str(HELPER),
                    "run",
                    "--repo",
                    str(repo),
                    "--",
                    sys.executable,
                    "-c",
                    "import time; time.sleep(5)",
                ],
                env={**os.environ, "MAISON_REPOSITORY_MUTATION_STATE_DIR": str(state_root)},
                stdout=DEVNULL,
                stderr=DEVNULL,
                text=True,
            )
            try:
                deadline = time.monotonic() + 5
                lock_file = None
                while time.monotonic() < deadline:
                    matches = list(state_root.glob("*/repository.lock"))
                    if matches:
                        lock_file = matches[0]
                        break
                    time.sleep(0.05)
                self.assertIsNotNone(lock_file)

                blocked = self.helper(
                    state_root,
                    "run",
                    "--repo",
                    str(repo),
                    "--",
                    sys.executable,
                    "-c",
                    "",
                )

                self.assertNotEqual(blocked.returncode, 0)
                self.assertIn("repository mutation lock is busy", blocked.stderr)
                self.assertIn(str(repo.resolve()), blocked.stderr)
            finally:
                terminate_process_tree(holder)

    def test_recovery_restores_original_for_incomplete_journal_states(self) -> None:
        helper = load_helper()
        states = ["created", "validated", "committing", "replacing"]
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            state_root = temp / "state"
            for state in states:
                with self.subTest(state=state):
                    repo = temp / state / "repo"
                    repo.mkdir(parents=True)
                    config = repo / "config.toml"
                    candidate = temp / state / "candidate.toml"
                    config.write_text("original\n")
                    candidate.write_text("candidate\n")
                    journal = helper.begin_journal(
                        repo,
                        operation="test",
                        files=[config],
                        state_root=state_root,
                    )
                    helper.record_candidate(journal, config, candidate)
                    helper.mark_journal_state(journal, state)
                    config.write_text("partial\n")

                    recovered = self.helper(state_root, "recover", "--repo", str(repo))

                    self.assertEqual(recovered.returncode, 0, recovered.stderr)
                    self.assertEqual(config.read_text(), "original\n")
                    self.assertFalse(journal.path.exists())

    def test_recovery_failure_preserves_journal_and_diagnostics(self) -> None:
        helper = load_helper()
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = temp / "repo"
            repo.mkdir()
            state_root = temp / "state"
            config = repo / "config.toml"
            candidate = temp / "candidate.toml"
            config.write_text("original\n")
            candidate.write_text("candidate\n")
            journal = helper.begin_journal(
                repo,
                operation="test",
                files=[config],
                state_root=state_root,
            )
            helper.record_candidate(journal, config, candidate)
            helper.mark_journal_state(journal, "replacing")
            config.unlink()
            config.mkdir()

            recovered = self.helper(state_root, "recover", "--repo", str(repo))

            self.assertNotEqual(recovered.returncode, 0)
            self.assertIn("rollback failed", recovered.stderr)
            self.assertTrue(journal.path.exists())
            self.assertTrue(config.is_dir())


class AuthoringCheckoutGuardTest(unittest.TestCase):
    def helper(self, *args: str) -> CompletedProcess[str]:
        return run(
            [sys.executable, str(HELPER), *args],
            capture_output=True,
            text=True,
        )

    def test_authoring_checkout_accepts_git_directory_and_worktree_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            git_dir_repo = temp / "git-dir"
            git_file_repo = temp / "git-file"
            git_dir_repo.mkdir()
            git_file_repo.mkdir()
            (git_dir_repo / ".git").mkdir()
            (git_file_repo / ".git").write_text("gitdir: ../actual.git\n")

            for repo in (git_dir_repo, git_file_repo):
                with self.subTest(repo=repo.name):
                    result = self.helper(
                        "require-authoring",
                        "--repo",
                        str(repo),
                        "--operation",
                        "test:add",
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_deployed_snapshot_rejects_authoring_mutation_with_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "mise.toml").write_text("[tasks]\n")
            (repo / "flake.nix").write_text("{}\n")
            (repo / ".maison-revision").write_text("0123456789abcdef\n")

            result = self.helper(
                "require-authoring",
                "--repo",
                str(repo),
                "--operation",
                "tool:add",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("deployed Maison snapshot", result.stderr)
            self.assertIn("Git authoring checkout", result.stderr)
            self.assertIn("private overlay repository", result.stderr)
            self.assertIn("tool:add", result.stderr)


class RepositoryMutationTaskSurfaceTest(unittest.TestCase):
    mutating_tasks = (
        ".mise/tasks/tool/add",
        ".mise/tasks/tool/remove",
        ".mise/tasks/package/add",
        ".mise/tasks/package/remove",
        ".mise/tasks/app/add",
        ".mise/tasks/app/remove",
        ".mise/tasks/host/add",
        ".mise/tasks/update",
    )
    runtime_tasks = (
        ".mise/tasks/apply",
        ".mise/tasks/plan",
        ".mise/tasks/system/apply",
        ".mise/tasks/system/plan",
        ".mise/tasks/user/apply",
        ".mise/tasks/user/plan",
        ".mise/tasks/user/status",
    )
    read_only_tasks = (
        ".mise/tasks/host/list",
        ".mise/tasks/host/validate",
        ".mise/tasks/package/search",
        ".mise/tasks/user/status",
        ".mise/tasks/plan",
    )

    def test_repository_mutators_require_authoring_checkout_before_lock(self) -> None:
        for task in self.mutating_tasks:
            with self.subTest(task=task):
                text = (ROOT / task).read_text()
                self.assertIn("transaction_require_authoring_checkout", text)
                self.assertIn("transaction_require_lock", text)
                self.assertLess(
                    text.index("transaction_require_authoring_checkout"),
                    text.index("transaction_require_lock"),
                )

    def test_repository_mutators_enter_shared_lock_before_reads(self) -> None:
        for task in self.mutating_tasks:
            with self.subTest(task=task):
                text = (ROOT / task).read_text()
                self.assertIn("transaction_require_lock", text)
                self.assertLess(
                    text.index("transaction_require_lock"),
                    text.index("transaction_directory"),
                )

    def test_runtime_and_read_only_tasks_do_not_take_authoring_guard_or_lock(self) -> None:
        for task in sorted(set(self.runtime_tasks + self.read_only_tasks)):
            with self.subTest(task=task):
                text = (ROOT / task).read_text()
                self.assertNotIn("transaction_require_authoring_checkout", text)
                self.assertNotIn("transaction_require_lock", text)


class MaisonCommandDeployedSnapshotTest(unittest.TestCase):
    def test_runtime_command_dispatch_still_works_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            install = temp / "maison"
            bin_dir = install / "bin"
            task_dir = install / ".mise" / "tasks" / "user"
            fake_bin = temp / "bin"
            bin_dir.mkdir(parents=True)
            task_dir.mkdir(parents=True)
            fake_bin.mkdir()
            shutil.copy2(ROOT / "bin/maison", bin_dir / "maison")
            os.chmod(
                bin_dir / "maison",
                os.stat(bin_dir / "maison").st_mode | stat.S_IXUSR,
            )
            (install / "mise.toml").write_text("[tasks]\n")
            (install / "flake.nix").write_text("{}\n")
            (install / ".maison-revision").write_text("0123456789abcdef\n")
            (task_dir / "status").write_text("#!/usr/bin/env bash\nexit 0\n")
            os.chmod(task_dir / "status", 0o755)
            fake_mise = fake_bin / "mise"
            fake_mise.write_text('#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" > "$MAISON_FAKE_MISE_LOG"\nexit 0\n')
            os.chmod(fake_mise, 0o755)
            log = temp / "mise.log"

            result = run(
                [str(bin_dir / "maison"), "user", "status"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "MAISON_HOME": str(install),
                    "MAISON_FAKE_MISE_LOG": str(log),
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().strip(), "run user:status --")


if __name__ == "__main__":
    unittest.main()
