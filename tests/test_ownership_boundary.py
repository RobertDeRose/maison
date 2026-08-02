from __future__ import annotations

from tests.support.topology import *


class OwnershipBoundaryTest(unittest.TestCase):
    def test_home_manager_is_removed_from_nix_graph(self) -> None:
        files = [ROOT / "flake.nix", *sorted((ROOT / "nix").rglob("*.nix"))]
        stale = []
        for path in files:
            text = path.read_text()
            if re.search(r"home-manager|homeConfigurations|homeConfig", text):
                stale.append(str(path.relative_to(ROOT)))
        self.assertEqual(stale, [])
        self.assertFalse((ROOT / "nix/modules/home").exists())
        self.assertFalse((ROOT / "packages.toml").exists())

    def test_system_outputs_are_explicit(self) -> None:
        outputs = read("nix/outputs.nix")
        for output in ("darwinConfigurations", "systemConfigs", "deploy"):
            self.assertRegex(outputs, rf"\b{re.escape(output)}\b")
        self.assertNotIn("homeConfigurations", outputs)

    def test_privileged_macos_state_remains_in_nix(self) -> None:
        darwin = read("nix/modules/darwin/system.nix")
        for token in (
            "security.pam.services.sudo_local",
            "touchIdAuth = true",
            "watchIdAuth = true",
            "reattach = true",
            "defaults.loginwindow.GuestEnabled = false",
            "remapCapsLockToEscape = true",
        ):
            self.assertIn(token, darwin)

    def test_user_defaults_do_not_claim_privileged_domains(self) -> None:
        with (ROOT / "config/mise/config.macos.toml").open("rb") as handle:
            data = tomllib.load(handle)
        defaults = data.get("bootstrap", {}).get("macos", {}).get("defaults", {})
        banned = {
            "com.apple.loginwindow",
            "/Library/Preferences/com.apple.loginwindow",
            "/Library/Preferences/com.apple.alf",
            "com.apple.security",
        }
        self.assertTrue(banned.isdisjoint(defaults))
        self.assertEqual(defaults, {})

    def test_system_integrations_remain_nix_owned(self) -> None:
        fonts = read("nix/modules/darwin/fonts.nix")
        homebrew = read("nix/modules/darwin/homebrew-system.nix")
        mac_packages = read("config/mise/config.macos-arm64.toml")
        self.assertIn("fonts.packages", fonts)
        self.assertIn("nix-homebrew", homebrew)
        self.assertIn("fuse-t", homebrew)
        self.assertNotIn("brew-cask:font-", mac_packages)
        self.assertNotIn("fuse-t", mac_packages)

    def test_nix_system_package_closure_is_administrative(self) -> None:
        darwin = read("nix/modules/darwin/system.nix")
        for package in ("pkgs.nh", "pkgs.deploy-rs", "pkgs.nixd"):
            self.assertIn(package, darwin)
        for interactive in ("pkgs.helix", "pkgs.starship", "pkgs.git", "pkgs.ripgrep"):
            self.assertNotIn(interactive, darwin)

        linux = read("nix/modules/linux/system.nix")
        for package in ("pkgs.curl", "pkgs.gitMinimal", "pkgs.gnutar", "pkgs.nh"):
            self.assertIn(package, linux)
        for interactive in ("pkgs.helix", "pkgs.starship", "pkgs.ripgrep"):
            self.assertNotIn(interactive, linux)

    def test_global_mise_config_and_platform_files_are_deployed(self) -> None:
        root_config = read("mise.toml")
        self.assertNotIn("[dotfiles]", root_config)
        self.assertNotIn("~/.config/mise/", root_config)
        self.assertNotIn("dotfiles/", root_config)

        lock_script = read("scripts/user-link-mise-lock.sh")
        self.assertIn("mise.lock", lock_script)
        self.assertIn("config.macos.lock", lock_script)

    def test_platform_package_policy_and_single_ownership(self) -> None:
        common = tomllib.loads(read("config/mise/config.toml"))
        mac = tomllib.loads(read("config/mise/config.macos.toml"))
        mac_arm = tomllib.loads(read("config/mise/config.macos-arm64.toml"))
        linux = tomllib.loads(read("config/mise/config.linux.toml"))

        common_packages = common["bootstrap"]["packages"]
        mac_packages = mac_arm["bootstrap"]["packages"]
        self.assertNotIn("bootstrap", linux)
        self.assertEqual(common_packages, {})
        self.assertEqual(mac_packages, {})
        self.assertFalse(set(common_packages) & set(mac_packages))

        tools = common["tools"]
        self.assertEqual(tools, {})

        active_tool_tables = {
            "common": tools,
            "mac": mac["tools"],
            "repo": tomllib.loads(read("mise.toml"))["tools"],
        }
        scoped_runtime_tools: set[str] = set()
        for left_name, left in active_tool_tables.items():
            for right_name, right in active_tool_tables.items():
                if left_name >= right_name:
                    continue
                duplicate_tools = (set(left) & set(right)) - scoped_runtime_tools
                self.assertFalse(
                    duplicate_tools,
                    f"duplicate tool ownership between {left_name} and {right_name}",
                )
        brew_formulae = {package.removeprefix("brew:") for package in common_packages if package.startswith("brew:")}
        self.assertFalse(set(tools) & brew_formulae)

        self.assertEqual(mac["tools"], {})

    def test_intel_darwin_is_removed_from_supported_surface(self) -> None:
        candidates = [
            ROOT / "README.md",
            ROOT / "mise.toml",
            ROOT / "config/mise/config.toml",
            ROOT / ".mise/lib/platform.sh",
            ROOT / ".github/scripts/build-platform-targets.sh",
            ROOT / "nix/lib/validation.nix",
            ROOT / "nix/outputs.nix",
        ]
        candidates += list((ROOT / "docs").rglob("*.md"))
        candidates += [path for path in (ROOT / "mise.lock",) if path.exists()]
        candidates += list((ROOT / "config/mise").glob("*.lock"))
        for path in candidates:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                self.assertNotIn("x86_64-darwin", text)
                self.assertNotIn("macos-x64", text)
        self.assertFalse((ROOT / "config/mise/config.macos-x64.toml").exists())

    def test_repository_tools_are_isolated_from_machine_convergence(self) -> None:
        base = tomllib.loads(read("mise.toml"))
        user_tools = tomllib.loads(read("config/mise/config.toml"))["tools"]
        self.assertEqual(user_tools, {})
        for tool in ("actionlint", "hk", "shellcheck", "shfmt", "tombi", "usage"):
            self.assertIn(tool, base["tools"])
            self.assertNotIn(tool, user_tools)
        self.assertNotIn("jq", base["tools"])
        user_apply = read(".mise/tasks/user/apply")
        self.assertNotIn("mise install", user_apply)
        self.assertIn("mise install", read(".mise/tasks/check/_default"))

    def test_public_repository_has_no_user_dotfiles(self) -> None:
        self.assertFalse((ROOT / "dotfiles/direnv/direnvrc").exists())
        self.assertFalse((ROOT / "dotfiles/zsh/zshrc").exists())
        self.assertFalse((ROOT / "dotfiles/pi/extensions").exists())
        self.assertTrue((ROOT / "examples/template/dotfiles/README.md").is_file())
