from __future__ import annotations

import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/maison_deploy_transaction.py"
spec = importlib.util.spec_from_file_location("maison_deploy_transaction", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


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
