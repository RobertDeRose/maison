from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.processes import run

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / ".mise/lib/user_convergence.py"


def load_user_convergence():
    spec = importlib.util.spec_from_file_location("user_convergence", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


class UserConvergencePlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.convergence = load_user_convergence()
        cls.root = Path("/repo")
        cls.home = Path("/home/maison")

    def plans(self, *, force_dotfiles: bool):
        plan = self.convergence.build_command_plan(
            mode="plan",
            force_dotfiles=force_dotfiles,
            root=self.root,
            home=self.home,
        )
        apply = self.convergence.build_command_plan(
            mode="apply",
            force_dotfiles=force_dotfiles,
            root=self.root,
            home=self.home,
        )
        return plan, apply

    def test_default_plan_and_apply_keep_dotfile_force_disabled(self) -> None:
        plan, apply = self.plans(force_dotfiles=False)

        self.assertFalse(plan.force_dotfiles)
        self.assertFalse(apply.force_dotfiles)
        for command in (*plan.convergence_commands, *apply.convergence_commands):
            self.assertNotIn("--force-dotfiles", command.argv)

    def test_explicit_force_dotfiles_is_shared_by_plan_and_apply(self) -> None:
        plan, apply = self.plans(force_dotfiles=True)

        self.assertTrue(plan.force_dotfiles)
        self.assertTrue(apply.force_dotfiles)
        for name in ("prepare", "dotfiles", "mise"):
            self.assertIn("--force-dotfiles", plan.command(name).argv)
            self.assertIn("--force-dotfiles", apply.command(name).argv)

    def test_convergence_steps_match_except_documented_execution_substitutions(self) -> None:
        plan, apply = self.plans(force_dotfiles=True)

        self.assertEqual(
            [command.name for command in plan.convergence_commands],
            [command.name for command in apply.convergence_commands],
        )
        self.assertEqual(
            ["prepare", "dotfiles", "lockfiles", "packages", "mise"],
            [command.name for command in plan.convergence_commands],
        )
        self.assertTrue(all(command.dry_run for command in plan.convergence_commands))
        self.assertTrue(all(not command.dry_run for command in apply.convergence_commands))
        self.assertEqual(plan.command("dotfiles").semantic_arguments, apply.command("dotfiles").semantic_arguments)
        self.assertEqual(plan.command("mise").semantic_arguments, apply.command("mise").semantic_arguments)
        self.assertEqual(plan.command("packages").semantic_action, apply.command("packages").semantic_action)
        self.assertNotEqual(plan.command("packages").argv, apply.command("packages").argv)
        self.assertEqual(plan.command("lockfiles").cwd, apply.command("lockfiles").cwd)
        self.assertEqual(plan.command("mise").env, apply.command("mise").env)

    def test_apply_only_steps_are_explicitly_documented(self) -> None:
        plan, apply = self.plans(force_dotfiles=False)

        self.assertEqual([], [command.name for command in plan.apply_only_commands])
        self.assertEqual(["trust", "finalize"], [command.name for command in apply.apply_only_commands])
        self.assertTrue(all(command.documented_substitution for command in apply.apply_only_commands))

    def test_aggregate_force_dotfiles_forwarding_matches_user_commands(self) -> None:
        self.assertEqual((), self.convergence.aggregate_user_arguments(force_dotfiles=False))
        self.assertEqual(
            ("--force-dotfiles",),
            self.convergence.aggregate_user_arguments(force_dotfiles=True),
        )

    def test_user_tasks_forward_force_dotfiles_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            captured = temp / "python-arguments"
            executable(
                fake_bin / "python3",
                '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$MAISON_CAPTURE"\n',
            )
            base_environment = {
                **os.environ,
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                "MISE_PROJECT_ROOT": str(ROOT),
                "MAISON_CAPTURE": str(captured),
            }
            for mode in ("plan", "apply"):
                for force_dotfiles in (False, True):
                    with self.subTest(mode=mode, force_dotfiles=force_dotfiles):
                        environment = base_environment | {"usage_force_dotfiles": str(force_dotfiles).lower()}
                        run([str(ROOT / f".mise/tasks/user/{mode}")], env=environment, check=True)
                        arguments = captured.read_text().splitlines()
                        self.assertEqual(str(ROOT / ".mise/lib/user_convergence.py"), arguments[0])
                        self.assertEqual(mode, arguments[1])
                        self.assertEqual("--force-dotfiles" in arguments, force_dotfiles)

    def test_aggregate_plan_forwards_force_dotfiles_to_user_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            captured = temp / "mise-arguments"
            executable(
                fake_bin / "mise",
                '#!/bin/sh\nprintf \'<%s>\' "$@" >> "$MAISON_CAPTURE"; printf \'\\n\' >> "$MAISON_CAPTURE"\n',
            )
            environment = {
                **os.environ,
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                "MAISON_CAPTURE": str(captured),
                "usage_force_dotfiles": "true",
            }
            run([str(ROOT / ".mise/tasks/plan")], env=environment, check=True)
            calls = captured.read_text().splitlines()
            self.assertEqual("<run><system:plan><-->", calls[0])
            self.assertEqual("<run><user:plan><--><--force-dotfiles>", calls[1])


if __name__ == "__main__":
    unittest.main()
