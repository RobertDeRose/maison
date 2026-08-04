from __future__ import annotations

import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.topology import *

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/maison_overlay_git.py"


def load_module():
    spec = importlib.util.spec_from_file_location("maison_overlay_git", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OverlayGitBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.overlay_git = load_module()

    def setUp(self) -> None:
        self.previous_git_config = {key: os.environ.get(key) for key in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}
        os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"

    def tearDown(self) -> None:
        for key, value in self.previous_git_config.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def git(self, repository: Path, *arguments: str, check: bool = True):
        return run(
            ["git", "-C", str(repository), *arguments],
            env=fixture_git_env(),
            check=check,
            capture_output=True,
            text=True,
        )

    def make_remote_overlay(self, directory: Path, remote_name: str = "origin") -> tuple[Path, Path]:
        remote = directory / "overlay.git"
        remote.parent.mkdir(parents=True, exist_ok=True)
        remote.mkdir()
        run(
            ["git", "init", "--bare", "-q", str(remote)],
            env=fixture_git_env(),
            check=True,
        )

        overlay = directory / "overlay"
        overlay.mkdir()
        git_init(overlay)
        (overlay / "state.txt").write_text("base\n")
        git_commit_all(overlay, "base")
        self.git(overlay, "remote", "add", remote_name, str(remote))
        self.git(overlay, "push", "-q", "-u", remote_name, "main")
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
        return overlay, remote

    def clone_remote(self, remote: Path, destination: Path) -> Path:
        run(
            ["git", "clone", "-q", str(remote), str(destination)],
            env=fixture_git_env(),
            check=True,
        )
        self.git(destination, "config", "user.name", "Maison Tests")
        self.git(destination, "config", "user.email", "tests@example.invalid")
        self.git(destination, "config", "commit.gpgSign", "false")
        return destination

    def test_status_reports_clean_in_sync_and_fetches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay, _ = self.make_remote_overlay(Path(directory))

            status = self.overlay_git.inspect_repository(overlay)

            self.assertEqual(status.worktree, "clean")
            self.assertEqual(status.relationship, "in-sync")
            self.assertEqual(status.comparison, "fresh")
            self.assertEqual(status.upstream, "origin/main")

    def test_status_refresh_and_publish_support_slash_remote_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overlay, remote = self.make_remote_overlay(root, remote_name="team/origin")

            status = self.overlay_git.inspect_repository(overlay)

            self.assertEqual(status.upstream, "team/origin/main")
            self.assertEqual(status.relationship, "in-sync")

            other = self.clone_remote(remote, root / "other")
            (other / "remote.txt").write_text("remote\n")
            remote_head = git_commit_all(other, "remote")
            self.git(other, "push", "-q")

            refresh = self.overlay_git.refresh_repository(overlay)

            self.assertTrue(refresh.updated)
            self.assertEqual(self.git(overlay, "rev-parse", "HEAD").stdout.strip(), remote_head)

            (overlay / "local.txt").write_text("local\n")
            local_head = git_commit_all(overlay, "local")
            publish = self.overlay_git.publish_repository(overlay)

            self.assertTrue(publish.pushed)
            self.assertEqual(
                self.git(overlay, "--git-dir", str(remote), "rev-parse", "refs/heads/main").stdout.strip(),
                local_head,
            )

    def test_status_distinguishes_dirty_tracked_and_untracked_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay, _ = self.make_remote_overlay(Path(directory))
            (overlay / ".gitignore").write_text("ignored.txt\n")
            git_commit_all(overlay, "ignore rules")
            self.git(overlay, "push", "-q")
            (overlay / "state.txt").write_text("changed\n")
            (overlay / "untracked.txt").write_text("untracked\n")
            (overlay / "ignored.txt").write_text("ignored\n")

            status = self.overlay_git.inspect_repository(overlay)

            self.assertEqual(status.worktree, "dirty")
            self.assertTrue(status.tracked_changes)
            self.assertTrue(status.untracked_changes)
            self.assertNotIn("ignored.txt", status.changed_paths)

    def test_status_reports_ahead_behind_and_diverged_histories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overlay, _ = self.make_remote_overlay(root / "ahead")
            (overlay / "local.txt").write_text("local\n")
            git_commit_all(overlay, "local")
            self.assertEqual(self.overlay_git.inspect_repository(overlay).relationship, "ahead")

            behind_overlay, behind_remote = self.make_remote_overlay(root / "behind")
            other = self.clone_remote(behind_remote, root / "behind-other")
            (other / "remote.txt").write_text("remote\n")
            git_commit_all(other, "remote")
            self.git(other, "push", "-q")
            self.assertEqual(
                self.overlay_git.inspect_repository(behind_overlay).relationship,
                "behind",
            )

            diverged_overlay, diverged_remote = self.make_remote_overlay(root / "diverged")
            other = self.clone_remote(diverged_remote, root / "diverged-other")
            (diverged_overlay / "local.txt").write_text("local\n")
            git_commit_all(diverged_overlay, "local")
            (other / "remote.txt").write_text("remote\n")
            git_commit_all(other, "remote")
            self.git(other, "push", "-q")
            self.assertEqual(
                self.overlay_git.inspect_repository(diverged_overlay).relationship,
                "diverged",
            )

    def test_status_reports_last_known_comparison_when_fetch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay, _ = self.make_remote_overlay(Path(directory))
            self.git(
                overlay,
                "remote",
                "set-url",
                "origin",
                str(Path(directory) / "offline.git"),
            )

            status = self.overlay_git.inspect_repository(overlay)
            rendered = self.overlay_git.format_status(status)

            self.assertEqual(status.comparison, "last-known")
            self.assertIsNotNone(status.fetch_error)
            self.assertIn("last-known", rendered)
            self.assertIn("unavailable", rendered)

    def test_status_reports_no_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay = Path(directory) / "overlay"
            overlay.mkdir()
            git_init(overlay)
            (overlay / "state.txt").write_text("base\n")
            git_commit_all(overlay)

            status = self.overlay_git.inspect_repository(overlay)

            self.assertEqual(status.relationship, "no-upstream")
            self.assertEqual(status.comparison, "not-configured")

    def test_publish_fetches_then_preserves_tracked_untracked_and_ignored_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay, remote = self.make_remote_overlay(Path(directory))
            (overlay / ".gitignore").write_text("ignored.txt\n")
            git_commit_all(overlay, "ignore rules")
            self.git(overlay, "push", "-q")
            (overlay / "local.txt").write_text("local\n")
            git_commit_all(overlay, "local")
            (overlay / "state.txt").write_text("dirty tracked\n")
            (overlay / "untracked.txt").write_text("dirty untracked\n")
            (overlay / "ignored.txt").write_text("do not stash\n")
            expected_head = self.git(overlay, "rev-parse", "HEAD").stdout.strip()

            result = self.overlay_git.publish_repository(overlay)

            self.assertTrue(result.pushed)
            self.assertEqual(self.git(overlay, "rev-parse", "HEAD").stdout.strip(), expected_head)
            self.assertEqual((overlay / "state.txt").read_text(), "dirty tracked\n")
            self.assertEqual((overlay / "untracked.txt").read_text(), "dirty untracked\n")
            self.assertEqual((overlay / "ignored.txt").read_text(), "do not stash\n")
            self.assertEqual(self.git(overlay, "stash", "list").stdout, "")
            self.assertEqual(
                self.git(overlay, "--git-dir", str(remote), "rev-parse", "refs/heads/main").stdout.strip(),
                expected_head,
            )

    def test_publish_refuses_remote_changes_before_stashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overlay, remote = self.make_remote_overlay(root)
            other = self.clone_remote(remote, root / "other")
            (other / "remote.txt").write_text("remote\n")
            git_commit_all(other, "remote")
            self.git(other, "push", "-q")
            (overlay / "state.txt").write_text("keep local work\n")

            with self.assertRaises(self.overlay_git.OverlayGitError):
                self.overlay_git.publish_repository(overlay)

            self.assertEqual((overlay / "state.txt").read_text(), "keep local work\n")
            self.assertEqual(self.git(overlay, "stash", "list").stdout, "")

    def test_publish_restores_work_when_push_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay, remote = self.make_remote_overlay(Path(directory))
            (overlay / "local.txt").write_text("local\n")
            git_commit_all(overlay, "local")
            hook = remote / "hooks/pre-receive"
            hook.write_text("#!/bin/sh\nexit 1\n")
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
            (overlay / "state.txt").write_text("dirty\n")
            (overlay / "untracked.txt").write_text("untracked\n")

            with self.assertRaises(self.overlay_git.OverlayGitError):
                self.overlay_git.publish_repository(overlay)

            self.assertEqual((overlay / "state.txt").read_text(), "dirty\n")
            self.assertEqual((overlay / "untracked.txt").read_text(), "untracked\n")
            self.assertEqual(self.git(overlay, "stash", "list").stdout, "")

    def test_stash_round_trip_preserves_staged_and_untracked_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay, _ = self.make_remote_overlay(Path(directory))
            (overlay / "state.txt").write_text("staged\n")
            self.git(overlay, "add", "--", "state.txt")
            (overlay / "untracked.txt").write_text("untracked\n")

            stash = self.overlay_git.create_stash(overlay)
            self.assertIsNotNone(stash)
            self.overlay_git.restore_stash(overlay, stash)

            self.assertEqual((overlay / "state.txt").read_text(), "staged\n")
            status = self.git(overlay, "status", "--porcelain=v1").stdout
            self.assertIn("M  state.txt", status)
            self.assertIn("?? untracked.txt", status)

    def test_stash_restore_conflict_leaves_stash_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay, _ = self.make_remote_overlay(Path(directory))
            (overlay / "state.txt").write_text("local\n")
            stash = self.overlay_git.create_stash(overlay)
            self.assertIsNotNone(stash)
            (overlay / "state.txt").write_text("conflicting\n")

            with self.assertRaises(self.overlay_git.OverlayGitError):
                self.overlay_git.restore_stash(overlay, stash)

            self.assertNotEqual(self.git(overlay, "stash", "list").stdout, "")

    def test_publish_refuses_offline_before_stashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay, _ = self.make_remote_overlay(Path(directory))
            self.git(
                overlay,
                "remote",
                "set-url",
                "origin",
                str(Path(directory) / "offline.git"),
            )
            (overlay / "state.txt").write_text("keep local work\n")

            with self.assertRaises(self.overlay_git.OverlayGitError):
                self.overlay_git.publish_repository(overlay)

            self.assertEqual((overlay / "state.txt").read_text(), "keep local work\n")
            self.assertEqual(self.git(overlay, "stash", "list").stdout, "")

    def test_refresh_fast_forwards_and_restores_local_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overlay, remote = self.make_remote_overlay(root)
            other = self.clone_remote(remote, root / "other")
            (other / "remote.txt").write_text("remote\n")
            remote_head = git_commit_all(other, "remote")
            self.git(other, "push", "-q")
            (overlay / "state.txt").write_text("local work\n")
            (overlay / "untracked.txt").write_text("untracked\n")

            result = self.overlay_git.refresh_repository(overlay)

            self.assertTrue(result.updated)
            self.assertEqual(self.git(overlay, "rev-parse", "HEAD").stdout.strip(), remote_head)
            self.assertEqual((overlay / "state.txt").read_text(), "local work\n")
            self.assertEqual((overlay / "untracked.txt").read_text(), "untracked\n")

    def test_refresh_refuses_offline_before_stashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay, _ = self.make_remote_overlay(Path(directory))
            self.git(
                overlay,
                "remote",
                "set-url",
                "origin",
                str(Path(directory) / "offline.git"),
            )
            (overlay / "state.txt").write_text("keep local work\n")

            with self.assertRaises(self.overlay_git.OverlayGitError):
                self.overlay_git.refresh_repository(overlay)

            self.assertEqual((overlay / "state.txt").read_text(), "keep local work\n")
            self.assertEqual(self.git(overlay, "stash", "list").stdout, "")

    def test_active_repository_rejects_public_maison_as_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "maison"
            root.mkdir()
            git_init(root)
            (root / "state.txt").write_text("base\n")
            git_commit_all(root)
            previous = os.environ.get("MAISON_OVERLAY_PATH")
            os.environ["MAISON_OVERLAY_PATH"] = str(root)
            try:
                with self.assertRaises(self.overlay_git.OverlayGitError):
                    self.overlay_git.active_repository(root=root)
            finally:
                if previous is None:
                    os.environ.pop("MAISON_OVERLAY_PATH", None)
                else:
                    os.environ["MAISON_OVERLAY_PATH"] = previous

    def test_commit_paths_preserves_unrelated_index_and_worktree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay = Path(directory) / "overlay"
            overlay.mkdir()
            git_init(overlay)
            target = overlay / "config/mise/config.toml"
            target.parent.mkdir(parents=True)
            target.write_text("before\n")
            (overlay / "unrelated.txt").write_text("before\n")
            git_commit_all(overlay)
            target.write_text("after\n")
            (overlay / "unrelated.txt").write_text("staged unrelated\n")
            self.git(overlay, "add", "--", "unrelated.txt")
            (overlay / "untracked.txt").write_text("untracked\n")

            commit = self.overlay_git.commit_paths(
                overlay,
                operation="added",
                scope="tool",
                identifier="github:owner/tool@1.2.3",
                paths=[target],
            )

            self.assertEqual(commit.subject, "added(tool): `github:owner/tool@1.2.3`")
            self.assertEqual(commit.paths, ("config/mise/config.toml",))
            self.assertEqual(
                self.git(overlay, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.strip(),
                "config/mise/config.toml",
            )
            status = self.git(overlay, "status", "--porcelain=v1").stdout
            self.assertIn("M  unrelated.txt", status)
            self.assertIn("?? untracked.txt", status)


if __name__ == "__main__":
    unittest.main()
