from __future__ import annotations

import importlib.util
import os
import stat
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/maison_deploy_transaction.py"
spec = importlib.util.spec_from_file_location("maison_deploy_transaction", MODULE_PATH)
assert spec is not None and spec.loader is not None
module: Any = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class DeployArchiveResourceLimitTest(unittest.TestCase):
    def make_archive(self, directory: Path, sizes: tuple[int, ...]) -> Path:
        source = directory / "source"
        source.mkdir()
        files = []
        for index, size in enumerate(sizes):
            path = source / f"member-{index}"
            with path.open("wb") as handle:
                handle.truncate(size)
            files.append(path)
        archive = directory / "archive.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for path in files:
                bundle.add(path, arcname=path.name)
        return archive

    def test_extracts_valid_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_archive(root, (3, 5))
            destination = root / "destination"
            destination.mkdir()

            module._safe_extract(archive, destination)

            self.assertEqual((destination / "member-0").read_bytes(), b"\0" * 3)
            self.assertEqual((destination / "member-1").read_bytes(), b"\0" * 5)

    def test_rejects_compressed_archive_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_archive(root, (1,))
            destination = root / "destination"
            destination.mkdir()
            previous = module.MAX_ARCHIVE_COMPRESSED_BYTES
            module.MAX_ARCHIVE_COMPRESSED_BYTES = archive.stat().st_size - 1
            try:
                with self.assertRaisesRegex(module.DeploymentTransactionError, "compressed archive exceeds"):
                    module._safe_extract(archive, destination)
            finally:
                module.MAX_ARCHIVE_COMPRESSED_BYTES = previous

    def test_rejects_member_count_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for index in range(3):
                    bundle.addfile(tarfile.TarInfo(f"member-{index}"))
            destination = root / "destination"
            destination.mkdir()
            previous = module.MAX_ARCHIVE_MEMBER_COUNT
            module.MAX_ARCHIVE_MEMBER_COUNT = 2
            try:
                with self.assertRaisesRegex(module.DeploymentTransactionError, "member count exceeds"):
                    module._safe_extract(archive, destination)
            finally:
                module.MAX_ARCHIVE_MEMBER_COUNT = previous

    def test_rejects_per_member_expanded_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_archive(root, (4,))
            destination = root / "destination"
            destination.mkdir()
            previous = module.MAX_ARCHIVE_MEMBER_BYTES
            module.MAX_ARCHIVE_MEMBER_BYTES = 3
            try:
                with self.assertRaisesRegex(module.DeploymentTransactionError, "member exceeds"):
                    module._safe_extract(archive, destination)
            finally:
                module.MAX_ARCHIVE_MEMBER_BYTES = previous

    def test_rejects_total_expanded_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_archive(root, (3, 3))
            destination = root / "destination"
            destination.mkdir()
            previous = module.MAX_ARCHIVE_EXPANDED_BYTES
            module.MAX_ARCHIVE_EXPANDED_BYTES = 5
            try:
                with self.assertRaisesRegex(module.DeploymentTransactionError, "expanded size exceeds"):
                    module._safe_extract(archive, destination)
            finally:
                module.MAX_ARCHIVE_EXPANDED_BYTES = previous


class DeployTransactionPathContractTest(unittest.TestCase):
    def test_default_transaction_root_is_outside_managed_home(self) -> None:
        managed_home = Path("/home/deploy-user")
        repo_path = managed_home / ".maison"

        root = module.default_transaction_root(repo_path, "deploy-user", managed_home)
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory).resolve()
            local_home = temp / "home" / "deploy-user"
            local_repo = local_home / ".maison"
            transaction_root = temp / ".maison-deploy" / "transactions" / "deploy-user" / module.repo_hash(local_repo)
            local_home.mkdir(parents=True)
            transaction_root.mkdir(parents=True)
            paths = module.allocate_transaction_paths(
                repo_path=local_repo,
                managed_user="deploy-user",
                managed_home=local_home,
                transaction_root=transaction_root.parent,
                transaction_id="test-transaction",
                expected_owner_uid=os.getuid(),
            )

        self.assertEqual(root, Path("/home/.maison-deploy/transactions/deploy-user"))
        self.assertNotIn("/home/deploy-user/", f"{root}/")
        self.assertEqual(paths.journal_path.name, "journal.jsonl")
        self.assertEqual(paths.lock_path.name, "transaction.lock")
        self.assertTrue(str(paths.staging_dir).endswith("/test-transaction/staging"))
        self.assertTrue(str(paths.rollback_dir).endswith("/test-transaction/rollback"))

    def test_transaction_root_must_not_be_beneath_managed_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory).resolve()
            managed_home = temp / "home" / "maison-test"
            repo_path = managed_home / ".maison"
            unsafe_root = managed_home / ".maison-deploy"
            unsafe_root.mkdir(parents=True)

            with self.assertRaisesRegex(module.DeploymentTransactionError, "outside managed home"):
                module.validate_transaction_root(
                    repo_path=repo_path,
                    managed_home=managed_home,
                    transaction_root=unsafe_root,
                    expected_owner_uid=os.getuid(),
                )

    def test_configured_transaction_root_under_managed_home_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory).resolve()
            managed_home = temp / "home" / "maison-test"
            repo_path = managed_home / ".maison"
            unsafe_base = managed_home / ".maison-deploy"
            managed_home.mkdir(parents=True)
            previous = os.environ.get("MAISON_TRANSACTION_ROOT")
            os.environ["MAISON_TRANSACTION_ROOT"] = str(unsafe_base)
            try:
                with self.assertRaisesRegex(module.DeploymentTransactionError, "outside managed home"):
                    module._make_namespace(repo_path, "maison-test", managed_home)
            finally:
                if previous is None:
                    os.environ.pop("MAISON_TRANSACTION_ROOT", None)
                else:
                    os.environ["MAISON_TRANSACTION_ROOT"] = previous
            self.assertFalse(unsafe_base.exists())

    def test_transaction_root_rejects_symlink_wrong_owner_and_writable_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory).resolve()
            managed_home = temp / "home" / "maison-test"
            repo_path = managed_home / ".maison"
            managed_home.mkdir(parents=True)
            safe_root = temp / ".maison-deploy" / "transactions" / "maison-test"
            safe_root.mkdir(parents=True)

            link_root = temp / "link-root"
            link_root.symlink_to(safe_root, target_is_directory=True)
            with self.assertRaisesRegex(module.DeploymentTransactionError, "must not be a symlink"):
                module.validate_transaction_root(
                    repo_path=repo_path,
                    managed_home=managed_home,
                    transaction_root=link_root,
                    expected_owner_uid=os.getuid(),
                )

            linked_parent = temp / "linked-parent"
            linked_parent.symlink_to(safe_root.parent, target_is_directory=True)
            with self.assertRaisesRegex(module.DeploymentTransactionError, "must not be a symlink"):
                module.validate_transaction_root(
                    repo_path=repo_path,
                    managed_home=managed_home,
                    transaction_root=linked_parent / safe_root.name,
                    expected_owner_uid=os.getuid(),
                )

            with self.assertRaisesRegex(module.DeploymentTransactionError, "owned by uid"):
                module.validate_transaction_root(
                    repo_path=repo_path,
                    managed_home=managed_home,
                    transaction_root=safe_root,
                    expected_owner_uid=os.getuid() + 1,
                )

            safe_root.chmod(stat.S_IRWXU | stat.S_IWOTH)
            with self.assertRaisesRegex(module.DeploymentTransactionError, "group/world writable"):
                module.validate_transaction_root(
                    repo_path=repo_path,
                    managed_home=managed_home,
                    transaction_root=safe_root,
                    expected_owner_uid=os.getuid(),
                )

    def test_transaction_root_must_be_on_same_filesystem(self) -> None:
        class Info:
            def __init__(self, device: int) -> None:
                self.st_dev = device

        with self.assertRaisesRegex(module.DeploymentTransactionError, "same filesystem"):
            module._assert_same_filesystem(
                transaction_root=Path("/home/.maison-deploy/transactions/user/hash"),
                transaction_root_info=Info(1),
                repo_anchor=Path("/home/user"),
                repo_anchor_info=Info(2),
            )

    def test_transaction_ids_are_unpredictable_and_path_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory).resolve()
            managed_home = temp / "home" / "maison-test"
            repo_path = managed_home / ".maison"
            transaction_root = temp / ".maison-deploy" / "transactions" / "maison-test" / module.repo_hash(repo_path)
            managed_home.mkdir(parents=True)
            transaction_root.mkdir(parents=True)

            first = module.allocate_transaction_paths(
                repo_path=repo_path,
                managed_user="maison-test",
                managed_home=managed_home,
                transaction_root=transaction_root.parent,
                expected_owner_uid=os.getuid(),
            )
            second = module.allocate_transaction_paths(
                repo_path=repo_path,
                managed_user="maison-test",
                managed_home=managed_home,
                transaction_root=transaction_root.parent,
                expected_owner_uid=os.getuid(),
            )

            self.assertNotEqual(first.transaction_id, second.transaction_id)
            self.assertNotIn("/", first.transaction_id)
            self.assertIn(transaction_root, first.transaction_dir.parents)
            with self.assertRaisesRegex(module.DeploymentTransactionError, "invalid transaction id"):
                module.allocate_transaction_paths(
                    repo_path=repo_path,
                    managed_user="maison-test",
                    managed_home=managed_home,
                    transaction_root=transaction_root.parent,
                    transaction_id="../escape",
                    expected_owner_uid=os.getuid(),
                )


if __name__ == "__main__":
    unittest.main()
