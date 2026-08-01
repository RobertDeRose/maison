from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import tomllib

from tests.support.processes import run

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("config_edit", ROOT / ".mise/lib/config_edit.py")
assert SPEC and SPEC.loader
CONFIG_EDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIG_EDIT)


class ConfigEditTest(unittest.TestCase):
    def parse(self, path: Path) -> dict:
        with path.open("rb") as handle:
            return tomllib.load(handle)

    def test_add_and_remove_tool_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('[settings]\nexperimental = true\n\n[tools]\nnode = "24"\n')
            CONFIG_EDIT.edit_tool(path, "node", "lts", False)
            self.assertEqual(self.parse(path)["tools"]["node"], ["24", "lts"])
            CONFIG_EDIT.edit_tool(path, "node@24", "latest", True)
            self.assertEqual(self.parse(path)["tools"]["node"], "lts")
            CONFIG_EDIT.edit_tool(path, "node", "latest", True)
            self.assertNotIn("node", self.parse(path).get("tools", {}))

    def test_backend_qualified_tool_is_not_split_without_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text("[tools]\n")
            tool = "npm:@fission-ai/openspec"
            CONFIG_EDIT.edit_tool(path, tool, "latest", False)
            self.assertEqual(self.parse(path)["tools"][tool], "latest")

    def test_tool_edit_preserves_commented_table_header_and_following_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                "# user tool configuration\n"
                "[tools] # mise-managed user tools\n"
                "# keep the operator's rationale\n"
                'node = "24"\n\n'
                "[settings]\n"
                "lockfile = true\n"
            )
            CONFIG_EDIT.edit_tool(path, "ruby", "3.3", False)
            text = path.read_text()
            self.assertIn("[tools] # mise-managed user tools", text)
            self.assertIn("# keep the operator's rationale", text)
            self.assertIn("[settings]\nlockfile = true", text)
            data = self.parse(path)
            self.assertEqual(data["tools"]["node"], "24")
            self.assertEqual(data["tools"]["ruby"], "3.3")

    def test_tool_edit_preserves_quoted_keys_arrays_comments_and_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_bytes(
                b"[tools]\r\n"
                b"# backend-qualified plugin runtime\r\n"
                b'"aqua:owner/tool" = "1.0"\r\n'
                b'node = ["24", "lts"] # keep both release tracks\r\n\r\n'
                b"[[plugins]]\r\n"
                b'name = "local"\r\n'
            )
            CONFIG_EDIT.edit_tool(path, "python", "3.12", False)
            text = path.read_text()
            self.assertIn('"aqua:owner/tool" = "1.0"', text)
            self.assertIn("# backend-qualified plugin runtime", text)
            self.assertIn('node = ["24", "lts"] # keep both release tracks', text)
            self.assertIn("[[plugins]]", text)
            self.assertNotIn(b"\n", path.read_bytes().replace(b"\r\n", b""))
            data = self.parse(path)
            self.assertEqual(data["tools"]["aqua:owner/tool"], "1.0")
            self.assertEqual(data["tools"]["node"], ["24", "lts"])
            self.assertEqual(data["tools"]["python"], "3.12")
            self.assertEqual(data["plugins"][0]["name"], "local")

    def test_config_edit_cli_works_without_ambient_site_packages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('[tools] # trailing comments used to break section matching\nnode = "24"\n')
            result = run(
                [
                    sys.executable,
                    "-S",
                    str(ROOT / ".mise/lib/config_edit.py"),
                    "tool",
                    "--file",
                    str(path),
                    "--name",
                    "ruby",
                    "--version",
                    "3.3",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.parse(path)["tools"]["ruby"], "3.3")

    def test_remove_lock_entry_preserves_other_versions_and_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mise.lock"
            path.write_text(
                "# generated\n\n"
                '[[tools.node]]\nversion = "24.1.0"\nbackend = "core:node"\n\n'
                '[tools.node."platforms.linux-x64"]\nurl = "one"\n\n'
                '[[tools.node]]\nversion = "22.2.0"\nbackend = "core:node"\n\n'
                '[[tools."aqua:owner/tool"]]\nversion = "1.0"\n'
                'backend = "aqua:owner/tool"\n\n'
                "[metadata]\nvalue = true\n"
            )
            CONFIG_EDIT.remove_locked_tool(path, "node@24.1.0")
            data = self.parse(path)
            self.assertEqual([entry["version"] for entry in data["tools"]["node"]], ["22.2.0"])
            self.assertIn("aqua:owner/tool", data["tools"])
            self.assertTrue(data["metadata"]["value"])

            CONFIG_EDIT.remove_locked_tool(path, "aqua:owner/tool")
            data = self.parse(path)
            self.assertNotIn("aqua:owner/tool", data["tools"])
            self.assertTrue(data["metadata"]["value"])

            config = Path(directory) / "config.toml"
            config.write_text("[tools]\n")
            CONFIG_EDIT.remove_locked_tool(path, "node@22", config)
            data = self.parse(path)
            self.assertNotIn("node", data.get("tools", {}))
            self.assertTrue(data["metadata"]["value"])

    def test_remove_lock_entry_preserves_arrays_of_tables_and_trailing_comments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mise.lock"
            path.write_text(
                "# generated\n\n"
                "[[tools.node]] # primary node resolver\n"
                'version = "24.1.0"\n'
                'backend = "core:node"\n\n'
                "[[tools.node.bins]]\n"
                'name = "node"\n\n'
                "[[tools.node]]\n"
                'version = "22.2.0"\n'
                'backend = "core:node"\n\n'
                "[[tools.usage]]\n"
                'version = "2.1.0"\n'
                'backend = "aqua:jdx/usage"\n\n'
                "[[tools.usage.bins]]\n"
                'name = "usage"\n\n'
                "[metadata] # keep unrelated lock metadata\n"
                "value = true\n"
            )
            CONFIG_EDIT.remove_locked_tool(path, "node@24.1.0")
            text = path.read_text()
            self.assertNotIn("24.1.0", text)
            self.assertIn("[[tools.usage.bins]]", text)
            self.assertIn("[metadata] # keep unrelated lock metadata", text)
            data = self.parse(path)
            self.assertEqual([entry["version"] for entry in data["tools"]["node"]], ["22.2.0"])
            self.assertEqual(data["tools"]["usage"][0]["bins"][0]["name"], "usage")
            self.assertTrue(data["metadata"]["value"])

    def test_lock_remove_rejects_malformed_input_without_partial_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mise.lock"
            original = '[[tools.node]]\nversion = "24.1.0"\n\n[metadata]\nvalue =\n'
            path.write_text(original)
            with self.assertRaises(CONFIG_EDIT.ConfigError):
                CONFIG_EDIT.remove_locked_tool(path, "node")
            self.assertEqual(path.read_text(), original)

    def test_add_and_remove_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('[bootstrap.packages]\n"brew:git" = "latest"\n')
            CONFIG_EDIT.edit_package(path, "brew:helix", "latest", False)
            self.assertEqual(self.parse(path)["bootstrap"]["packages"]["brew:helix"], "latest")
            CONFIG_EDIT.edit_package(path, "brew:git", "latest", True)
            self.assertNotIn("brew:git", self.parse(path)["bootstrap"]["packages"])

    def test_package_edit_preserves_comments_and_following_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                "[bootstrap.packages] # installation declarations\n"
                "# keep taps grouped with packages\n"
                '"brew:git" = "latest"\n\n'
                "[settings]\n"
                "lockfile = true\n"
            )
            CONFIG_EDIT.edit_package(path, "brew:helix", "latest", False)
            text = path.read_text()
            self.assertIn("[bootstrap.packages] # installation declarations", text)
            self.assertIn("# keep taps grouped with packages", text)
            self.assertIn("[settings]\nlockfile = true", text)
            self.assertEqual(self.parse(path)["bootstrap"]["packages"]["brew:helix"], "latest")

    def test_add_host_preserves_inventory_comments_and_following_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.toml"
            path.write_text(
                "schema = 1\n\n"
                "[defaults]\n"
                'user = "operator"\n\n'
                "[users.operator]\n"
                'username = "operator"\n'
                'full_name = "Maison Operator"\n'
                'email = "operator@example.invalid"\n'
                'github = "example-user"\n\n'
                "[hosts.example-linux] # existing host\n"
                'system = "aarch64-linux"\n'
                'user = "operator"\n'
                'profiles = ["base", "linux"]\n\n'
                "[metadata]\n"
                'owner = "tests"\n'
            )
            CONFIG_EDIT.add_host(
                path,
                "new-linux",
                system="aarch64-linux",
                user="operator",
                profiles=["base", "dev", "linux"],
            )
            text = path.read_text()
            self.assertIn("[hosts.example-linux] # existing host", text)
            self.assertIn('[metadata]\nowner = "tests"', text)
            data = self.parse(path)
            self.assertEqual(data["hosts"]["new-linux"]["system"], "aarch64-linux")
            self.assertEqual(data["hosts"]["new-linux"]["profiles"], ["base", "dev", "linux"])


if __name__ == "__main__":
    unittest.main()
