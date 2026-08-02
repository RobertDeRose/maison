from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
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

    def test_active_overlay_is_used_for_every_user_convergence_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay = Path(directory) / "overlay"
            config = overlay / "config/mise"
            config.mkdir(parents=True)
            (config / "config.toml").write_text("[dotfiles]\n")
            (config / "mise.lock").write_text("# overlay lock\n")
            (config / "config.macos.lock").write_text("# overlay macOS lock\n")
            previous = os.environ.get("MAISON_OVERLAY_PATH")
            os.environ["MAISON_OVERLAY_PATH"] = str(overlay)
            try:
                plan = self.convergence.build_command_plan(
                    mode="plan",
                    force_dotfiles=False,
                    root=ROOT,
                    home=self.home,
                )
            finally:
                if previous is None:
                    os.environ.pop("MAISON_OVERLAY_PATH", None)
                else:
                    os.environ["MAISON_OVERLAY_PATH"] = previous

            expected_config = str((config / "config.toml").resolve())
            for command in plan.convergence_commands:
                self.assertEqual(expected_config, command.env["MISE_GLOBAL_CONFIG_FILE"])
                self.assertEqual(str(overlay.resolve()), command.env["MAISON_USER_CONFIG_ROOT"])

            lockfiles = plan.command("lockfiles")
            self.assertEqual(str(overlay.resolve()), lockfiles.env["MAISON_USER_CONFIG_ROOT"])

    def test_user_convergence_falls_back_to_public_config_without_overlay(self) -> None:
        previous = os.environ.pop("MAISON_OVERLAY_PATH", None)
        try:
            plan = self.convergence.build_command_plan(
                mode="plan",
                force_dotfiles=False,
                root=ROOT,
                home=self.home,
            )
        finally:
            if previous is not None:
                os.environ["MAISON_OVERLAY_PATH"] = previous

        self.assertEqual(
            str(ROOT / "config/mise/config.toml"),
            plan.command("mise").env["MISE_GLOBAL_CONFIG_FILE"],
        )
        self.assertEqual(str(ROOT), plan.command("mise").env["MAISON_USER_CONFIG_ROOT"])

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

    def test_overlay_config_is_restored_after_a_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            (home / ".config/mise").mkdir(parents=True)
            installed = home / ".config/mise/config.toml"
            overlay = temp / "overlay"
            (overlay / "config/mise").mkdir(parents=True)
            overlay_config = overlay / "config/mise/config.toml"
            overlay_config.write_text("old config\n")
            overlay_macos_config = overlay / "config/mise/config.macos.toml"
            overlay_macos_config.write_text("old macos config\n")
            installed.symlink_to(overlay_config)
            installed_macos = home / ".config/mise/config.macos.toml"
            installed_macos.symlink_to(overlay_macos_config)
            probe = temp / "probe.sh"
            executable(
                probe,
                '#!/bin/sh\n[ ! -e "$HOME/.config/mise/config.toml" ] && [ ! -e "$HOME/.config/mise/config.macos.toml" ] && exit 0\nexit 11\n',
            )
            command = self.convergence.Command(
                name="mise",
                argv=(str(probe),),
                cwd=home,
                env={
                    "HOME": str(home),
                    "MAISON_USER_CONFIG_ROOT": str(overlay),
                    "MISE_GLOBAL_CONFIG_FILE": str(overlay / "config/mise/config.toml"),
                },
                dry_run=True,
                semantic_action="probe",
            )
            plan = self.convergence.CommandPlan("plan", False, (command,))
            self.convergence.run_command_plan(plan)
            self.assertEqual("old config\n", installed.read_text())
            self.assertEqual("old macos config\n", installed_macos.read_text())

    def test_overlay_config_is_retained_after_successful_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            (home / ".config/mise").mkdir(parents=True)
            installed = home / ".config/mise/config.toml"
            overlay = temp / "overlay"
            (overlay / "config/mise").mkdir(parents=True)
            overlay_config = overlay / "config/mise/config.toml"
            overlay_config.write_text("old config\n")
            overlay_macos_config = overlay / "config/mise/config.macos.toml"
            overlay_macos_config.write_text("old macos config\n")
            installed.symlink_to(overlay_config)
            installed_macos = home / ".config/mise/config.macos.toml"
            installed_macos.symlink_to(overlay_macos_config)
            probe = temp / "probe.sh"
            executable(
                probe,
                '#!/bin/sh\n[ ! -e "$HOME/.config/mise/config.toml" ] && [ ! -e "$HOME/.config/mise/config.macos.toml" ] || exit 11\nprintf "new config\\n" > "$HOME/.config/mise/config.toml"\n',
            )
            command = self.convergence.Command(
                name="mise",
                argv=(str(probe),),
                cwd=home,
                env={
                    "HOME": str(home),
                    "MAISON_USER_CONFIG_ROOT": str(overlay),
                    "MISE_GLOBAL_CONFIG_FILE": str(overlay / "config/mise/config.toml"),
                },
                dry_run=False,
                semantic_action="probe",
            )
            plan = self.convergence.CommandPlan("apply", False, (command,))
            self.convergence.run_command_plan(plan)
            self.assertEqual("new config\n", installed.read_text())
            self.assertEqual("old macos config\n", installed_macos.read_text())

    def test_overlay_config_is_restored_after_failed_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            (home / ".config/mise").mkdir(parents=True)
            installed = home / ".config/mise/config.toml"
            overlay = temp / "overlay"
            (overlay / "config/mise").mkdir(parents=True)
            overlay_config = overlay / "config/mise/config.toml"
            overlay_config.write_text("old config\n")
            overlay_macos_config = overlay / "config/mise/config.macos.toml"
            overlay_macos_config.write_text("old macos config\n")
            installed.symlink_to(overlay_config)
            installed_macos = home / ".config/mise/config.macos.toml"
            installed_macos.symlink_to(overlay_macos_config)
            probe = temp / "probe.sh"
            executable(
                probe,
                '#!/bin/sh\n[ ! -e "$HOME/.config/mise/config.toml" ] && [ ! -e "$HOME/.config/mise/config.macos.toml" ] && exit 23\n',
            )
            command = self.convergence.Command(
                name="mise",
                argv=(str(probe),),
                cwd=home,
                env={
                    "HOME": str(home),
                    "MAISON_USER_CONFIG_ROOT": str(overlay),
                    "MISE_GLOBAL_CONFIG_FILE": str(overlay / "config/mise/config.toml"),
                },
                dry_run=False,
                semantic_action="probe",
            )
            plan = self.convergence.CommandPlan("apply", False, (command,))
            with self.assertRaises(subprocess.CalledProcessError):
                self.convergence.run_command_plan(plan)
            self.assertEqual("old config\n", installed.read_text())
            self.assertEqual("old macos config\n", installed_macos.read_text())

    def test_status_uses_overlay_sources_without_moving_installed_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            project = temp / "project"
            project.mkdir()
            home = temp / "home"
            (home / ".config/mise").mkdir(parents=True)
            overlay = temp / "overlay"
            (overlay / "config/mise").mkdir(parents=True)
            overlay_config = overlay / "config/mise/config.toml"
            overlay_config.write_text(
                '[dotfiles]\n"~/.config/mise/config.toml" = '
                '{ source = "../../config/mise/config.toml", mode = "symlink" }\n'
            )
            installed = home / ".config/mise/config.toml"
            installed.symlink_to(overlay_config)
            previous_overlay = os.environ.get("MAISON_OVERLAY_PATH")
            os.environ["MAISON_OVERLAY_PATH"] = str(overlay)
            calls: list[tuple[tuple[str, ...], Path, dict[str, str]]] = []

            def runner(
                argv: tuple[str, ...],
                *,
                cwd: Path,
                env: dict[str, str],
                check: bool,
                capture_output: bool,
                text: bool,
            ) -> subprocess.CompletedProcess[str]:
                self.assertTrue(check)
                self.assertTrue(capture_output)
                self.assertTrue(text)
                self.assertTrue(installed.is_symlink())
                self.assertEqual(str(overlay_config.resolve()), env["MISE_GLOBAL_CONFIG_FILE"])
                calls.append((argv, cwd, env))
                return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    self.convergence.run_user_status(root=project, home=home, runner=runner)
            finally:
                if previous_overlay is None:
                    os.environ.pop("MAISON_OVERLAY_PATH", None)
                else:
                    os.environ["MAISON_OVERLAY_PATH"] = previous_overlay

            self.assertTrue(installed.is_symlink())
            self.assertIn("applied", output.getvalue())
            self.assertNotIn("source missing", output.getvalue())
            self.assertEqual(1, len(calls))
            self.assertEqual(("mise", "bootstrap", "status"), calls[0][0])
            self.assertEqual(project, calls[0][1])
            self.assertEqual(str(overlay.resolve()), calls[0][2]["MAISON_USER_CONFIG_ROOT"])

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

    def test_user_tasks_export_the_active_overlay_before_planning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            overlay = temp / "overlay"
            (overlay / "config/mise").mkdir(parents=True)
            (overlay / "config/mise/config.toml").write_text("[dotfiles]\n")
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            captured = temp / "overlay-path"
            real_python = str(Path(sys.executable).resolve())
            helper = str(ROOT / "scripts/maison_overlay.py")
            executable(
                fake_bin / "python3",
                f'''#!/bin/sh
if [ "$1" = "-c" ] || [ "$1" = "{helper}" ]; then
  exec "{real_python}" "$@"
fi
printf '%s\\n' "$MAISON_OVERLAY_PATH" > "$MAISON_CAPTURE"
''',
            )
            environment = {
                **os.environ,
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                "MISE_PROJECT_ROOT": str(ROOT),
                "MAISON_CAPTURE": str(captured),
                "MAISON_OVERLAY_PATH": str(overlay),
            }
            run([str(ROOT / ".mise/tasks/user/plan")], env=environment, check=True)
            self.assertEqual(str(overlay), captured.read_text().strip())

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
