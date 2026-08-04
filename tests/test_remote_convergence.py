from __future__ import annotations

import importlib.util
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.topology import *

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / ".mise/lib/user_convergence.py"


def load_user_convergence():
    spec = importlib.util.spec_from_file_location("user_convergence_recovery", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RestrictedRecoveryPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.convergence = load_user_convergence()
        cls.root = Path("/repo")
        cls.home = Path("/home/maison")

    def plan(self, *, force_dotfiles: bool = False):
        return self.convergence.build_command_plan(
            mode="recovery",
            force_dotfiles=force_dotfiles,
            root=self.root,
            home=self.home,
        )

    def test_recovery_plan_contains_only_safe_user_steps(self) -> None:
        plan = self.plan()

        self.assertEqual(
            [command.name for command in plan.convergence_commands],
            ["prepare", "dotfiles", "lockfiles", "mise"],
        )
        self.assertEqual(
            [command.name for command in plan.apply_only_commands],
            ["trust", "finalize"],
        )
        self.assertTrue(all(not command.dry_run for command in plan.convergence_commands))
        self.assertNotIn("packages", [command.name for command in plan.convergence_commands])
        self.assertNotIn("packages", [command.name for command in plan.apply_only_commands])
        self.assertIn("--recovery", plan.command("prepare").argv)
        self.assertIn("--skip", plan.command("mise").argv)
        self.assertIn("packages", plan.command("mise").argv)
        self.assertIn("dotfiles", plan.command("mise").argv)

    def test_recovery_never_invokes_package_helper(self) -> None:
        plan = self.plan()
        commands = (*plan.convergence_commands, *plan.apply_only_commands)

        self.assertNotIn("packages", [command.name for command in commands])
        self.assertNotIn(
            "user-apply-packages.sh",
            " ".join(argument for command in commands for argument in command.argv),
        )
        self.assertNotIn("bootstrap.packages", " ".join(argument for command in commands for argument in command.argv))

    def test_force_dotfiles_is_forwarded_only_when_explicit(self) -> None:
        without_force = self.plan(force_dotfiles=False)
        with_force = self.plan(force_dotfiles=True)

        for command in (*without_force.convergence_commands, *without_force.apply_only_commands):
            self.assertNotIn("--force-dotfiles", command.argv)
        for name in ("prepare", "dotfiles", "mise"):
            self.assertIn("--force-dotfiles", with_force.command(name).argv)

    def test_missing_initial_events_remain_unknown_after_recovery_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "events.json"
            event_file.write_text(json.dumps([{"mode": "recovery", "phase": "trust", "status": "failed"}]))

            self.assertEqual(
                self.convergence._package_phase(json.loads(event_file.read_text()), event_file),
                "unknown",
            )

    def test_initial_failure_before_packages_is_not_started(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "events.json"
            events = [
                {"mode": "apply", "phase": "dotfiles", "status": "failed"},
                {"mode": "recovery", "phase": "trust", "status": "completed"},
            ]
            event_file.write_text(json.dumps(events))

            self.assertEqual(self.convergence._package_phase(events, event_file), "not-started")

    def test_report_contract_records_revisions_steps_and_external_effects(self) -> None:
        report = self.convergence.build_recovery_report(
            failed_revision="f" * 40,
            restored_revision="0" * 40,
            initial_exit_code=23,
            package_phase="started",
            recovery_status="succeeded",
            recovery_exit_code=0,
            recovery_steps=("prepare", "dotfiles", "lockfiles", "mise", "finalize"),
            force_dotfiles=False,
        )

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["kind"], "remote-convergence-recovery")
        self.assertEqual(report["failed_revision"], "f" * 40)
        self.assertEqual(report["restored_revision"], "0" * 40)
        self.assertEqual(report["initial_convergence"]["status"], "failed")
        self.assertEqual(report["initial_convergence"]["exit_code"], 23)
        self.assertEqual(report["initial_convergence"]["package_phase"], "started")
        self.assertEqual(report["recovery"]["status"], "succeeded")
        self.assertEqual(report["recovery"]["steps"], ["prepare", "dotfiles", "lockfiles", "mise", "finalize"])
        self.assertFalse(report["recovery"]["force_dotfiles"])
        self.assertEqual(report["external_side_effects"]["package_app"]["status"], "started")
        self.assertEqual(report["external_side_effects"]["package_app"]["rollback"], "not-attempted")
        self.assertTrue(report["external_side_effects"]["package_app"]["follow_up"])

    def test_report_is_written_atomically_with_private_permissions(self) -> None:
        report = self.convergence.build_recovery_report(
            failed_revision="f" * 40,
            restored_revision="0" * 40,
            initial_exit_code=23,
            package_phase="not-started",
            recovery_status="failed",
            recovery_exit_code=9,
            recovery_steps=("prepare",),
            force_dotfiles=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recovery.json"
            self.convergence.write_recovery_report(path, report)

            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(json.loads(path.read_text()), report)
            self.assertFalse(path.with_suffix(".tmp").exists())


class RemoteDeploymentRecoveryContractTest(unittest.TestCase):
    def test_deploy_rolls_back_before_running_managed_user_recovery(self) -> None:
        deploy = read(".mise/tasks/deploy")

        self.assertIn("mise run user:recover", deploy)
        self.assertIn("action=rollback", deploy)
        self.assertLess(deploy.index("action=rollback"), deploy.index("mise run user:recover"))
        self.assertLess(deploy.index("finalize $quoted_action"), deploy.index("mise run user:recover"))
        self.assertIn('ssh "$user@$hostname"', deploy)
        self.assertIn("MAISON_RECOVERY_REPORT", deploy)
        self.assertIn("run_recovery()", deploy)
        self.assertIn("command -v mise", deploy)

    def test_recovery_task_uses_restored_repository_and_internal_mode(self) -> None:
        recover = read(".mise/tasks/user/recover")

        self.assertIn(".mise/lib/user_convergence.py", recover)
        self.assertIn("recovery", recover)
        self.assertIn("--force-dotfiles", recover)
        self.assertIn("MAISON_RECOVERY_REPORT", recover)


if __name__ == "__main__":
    unittest.main()
