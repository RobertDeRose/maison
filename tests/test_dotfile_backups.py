from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from tests.support.processes import run
from tests.support.topology import ROOT

HELPER = ROOT / ".mise/lib/dotfile_backups.py"


def backup(home: Path, backup_dir: Path, *targets: Path):
    return run(
        [
            "python3",
            str(HELPER),
            "backup",
            "--home",
            str(home),
            "--backup-dir",
            str(backup_dir),
            *[argument for target in targets for argument in ("--target", str(target))],
        ],
        cwd=ROOT,
    )


def restore(home: Path, backup_dir: Path, *, force: bool = False):
    arguments = [
        "python3",
        str(HELPER),
        "restore",
        "--home",
        str(home),
        "--backup-dir",
        str(backup_dir),
    ]
    if force:
        arguments.append("--force")
    return run(arguments, cwd=ROOT)


def restore_task(home: Path, backup_dir: Path):
    env = os.environ | {
        "HOME": str(home),
        "MISE_PROJECT_ROOT": str(ROOT),
        "usage_backup_directory": str(backup_dir),
        "usage_force": "true",
    }
    return run([str(ROOT / ".mise/tasks/user/restore-dotfiles")], cwd=ROOT, env=env)


class DotfileBackupTest(unittest.TestCase):
    def test_backup_preserves_objects_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            backup_dir = home / ".local/state/maison/backups/dotfiles/20260731T000000Z"
            home.mkdir()
            regular = home / ".config/example/settings"
            directory_target = home / ".config/example/nested"
            external = temp / "external"
            regular.parent.mkdir(parents=True)
            regular.write_text("settings\n")
            regular.chmod(0o640)
            directory_target.mkdir()
            (directory_target / "child").write_text("child\n")
            external.write_text("must not be copied\n")
            link = home / ".config/example/external-link"
            link.symlink_to(external)

            result = backup(home, backup_dir, regular, directory_target, link)
            self.assertEqual(result.returncode, 0, result.stderr)

            manifest = json.loads((backup_dir / "manifest.json").read_text())
            self.assertEqual(manifest["version"], 1)
            entries = {entry["source"]: entry for entry in manifest["entries"]}
            self.assertEqual(
                set(entries),
                {
                    ".config/example/settings",
                    ".config/example/nested",
                    ".config/example/external-link",
                },
            )
            regular_entry = entries[".config/example/settings"]
            self.assertEqual(regular_entry["type"], "file")
            self.assertEqual(regular_entry["mode"], 0o640)
            self.assertIn("mtime_ns", regular_entry)
            self.assertEqual(regular_entry["restore_status"], "pending")
            self.assertEqual((backup_dir / regular_entry["backup_path"]).read_text(), "settings\n")
            self.assertTrue((backup_dir / entries[".config/example/nested"]["backup_path"]).is_dir())
            link_entry = entries[".config/example/external-link"]
            backup_link = backup_dir / link_entry["backup_path"]
            self.assertEqual(link_entry["type"], "symlink")
            self.assertEqual(link_entry["symlink_target"], str(external))
            self.assertTrue(backup_link.is_symlink())
            self.assertEqual(os.readlink(backup_link), str(external))
            self.assertFalse((backup_dir / "external").exists())

    def test_restore_requires_force_then_restores_files_directories_and_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            backup_dir = home / ".local/state/maison/backups/dotfiles/20260731T000000Z"
            home.mkdir()
            regular = home / ".config/example/settings"
            nested = home / ".config/example/nested"
            external = temp / "external"
            regular.parent.mkdir(parents=True)
            regular.write_text("original\n")
            nested.mkdir()
            (nested / "child").write_text("child\n")
            external.write_text("external\n")
            link = home / ".config/example/link"
            link.symlink_to(external)
            self.assertEqual(backup(home, backup_dir, regular, nested, link).returncode, 0)
            regular.write_text("replacement\n")
            (nested / "replacement").write_text("replacement\n")
            link.unlink()
            link.write_text("replacement\n")

            refused = restore(home, backup_dir)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("--force", refused.stderr)
            self.assertEqual(regular.read_text(), "replacement\n")

            applied = restore_task(home, backup_dir)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(regular.read_text(), "original\n")
            self.assertEqual((nested / "child").read_text(), "child\n")
            self.assertFalse((nested / "replacement").exists())
            self.assertTrue(link.is_symlink())
            self.assertEqual(os.readlink(link), str(external))
            manifest = json.loads((backup_dir / "manifest.json").read_text())
            self.assertEqual({entry["restore_status"] for entry in manifest["entries"]}, {"restored"})

    def test_rejects_special_files_before_removing_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            backup_dir = home / ".local/state/maison/backups/dotfiles/20260731T000000Z"
            home.mkdir()
            fifo = home / ".config/example/fifo"
            fifo.parent.mkdir(parents=True)
            os.mkfifo(fifo)

            result = backup(home, backup_dir, fifo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported", result.stderr)
            self.assertTrue(stat.S_ISFIFO(fifo.lstat().st_mode))
            self.assertFalse(backup_dir.exists())

    def test_restore_rejects_escaping_manifest_and_preserves_partial_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            backup_dir = home / ".local/state/maison/backups/dotfiles/20260731T000000Z"
            home.mkdir()
            first = home / ".config/example/first"
            second = home / ".config/example/second"
            first.parent.mkdir(parents=True)
            first.write_text("first\n")
            second.write_text("second\n")
            self.assertEqual(backup(home, backup_dir, first, second).returncode, 0)
            first.write_text("changed\n")
            second.write_text("changed\n")
            manifest_path = backup_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["entries"][1]["backup_path"] = "missing-payload"
            manifest_path.write_text(json.dumps(manifest))

            failed = restore(home, backup_dir, force=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(first.read_text(), "first\n")
            self.assertEqual(second.read_text(), "changed\n")
            statuses = json.loads(manifest_path.read_text())["entries"]
            self.assertEqual(statuses[0]["restore_status"], "restored")
            self.assertEqual(statuses[1]["restore_status"], "pending")

            manifest = json.loads(manifest_path.read_text())
            manifest["entries"][0]["source"] = "../outside"
            manifest_path.write_text(json.dumps(manifest))
            rejected = restore(home, backup_dir, force=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("outside home", rejected.stderr)
