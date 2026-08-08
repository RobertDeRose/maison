from __future__ import annotations

from tests.support.topology import *

TASK = ROOT / ".mise/tasks/test/bootstrap/mac"


class MacOSIntegrationContractTest(unittest.TestCase):
    def test_mac_task_is_hidden_and_directly_available(self) -> None:
        text = TASK.read_text()
        self.assertIn("#MISE hide=true", text)
        self.assertIn('# [MISE] depends=["test:lume:install"]', text)

        hidden = run(
            ["mise", "-C", str(ROOT), "tasks", "--name-only", "--hidden"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(hidden.returncode, 0, hidden.stderr)
        self.assertIn("test:bootstrap:mac", hidden.stdout.splitlines())
        self.assertNotIn("test:bootstrap:mac-sip", hidden.stdout.splitlines())

        public = run(
            ["mise", "-C", str(ROOT), "tasks", "--name-only"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(public.returncode, 0, public.stderr)
        self.assertNotIn("test:bootstrap:mac", public.stdout.splitlines())

    def test_mac_task_uses_supplied_local_disposable_lume_worker(self) -> None:
        text = TASK.read_text()
        for contract in (
            'base_name="${MAISON_MACOS_BASE_NAME:-macos-tahoe-with-nix}"',
            "MAISON_MACOS_BASE_NAME",
            "local Lume VM",
            "[A-Za-z0-9]*)",
            "lume_get_json",
            "wait_for_lume_ssh",
            "wait_for_lume_nix",
            "--format json",
            "lume_command clone",
            "--source-storage default",
            "--dest-storage default",
            "--storage default",
            "lume_command run",
            "--detach",
            "--display none",
            '"$lume_binary" stop',
            '"$lume_binary" delete',
            "--force",
            "csrutil status",
            "26.6.1",
            "25G76",
            "enabled",
            "/Library/Developer/CommandLineTools",
            "xcode-select",
            "/nix/var/nix/profiles/default/bin/nix",
            "/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh",
            "/nix/var/nix/daemon-socket/socket",
            "Preparing disposable macOS worker privilege",
            "sudoers.d/lume",
            "tester ALL=(ALL) NOPASSWD: ALL",
            "softwareupdate -l",
            "Command Line Tools for Xcode",
            "installondemand.in-progress",
            "experimental-features = nix-command flakes",
            "find /nix/store -maxdepth 3 -path '*/bin/bash'",
            "Nix Bash is unavailable",
            "sysadminctl -addUser tester",
            "mkdir -p /Users/tester",
            "chown tester:staff /Users/tester",
            "autoLoginUser",
            "IdentitiesOnly=yes",
            "BatchMode=yes",
            "PreferredAuthentications=publickey",
            "PasswordAuthentication=no",
            "KbdInteractiveAuthentication=no",
            'test "$(defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser 2>/dev/null)" = "lume"',
            "locale -a",
            "ssh-keygen",
            "scp",
            "consumer_integration_stage",
            "consumer_integration_fetch_bootstrap",
            "consumer_integration_resolve_github_ref",
            "MAISON_MACOS_BOOTSTRAP_REF",
            "feat/test-bootstrap-macos",
            "bootstrap_revision",
            '--ref "$bootstrap_ref"',
            "consumer_integration_fetch_framework_artifact",
            "Installing consumer fnox prerequisite",
            "remote_root/mise",
            'trust "$remote_root/consumer/mise.toml"',
            "MAISON_CONSUMER_ROOT",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)

        self.assertNotIn("lume_command pull", text)
        self.assertNotIn("base_provenance", text)
        self.assertNotIn("grep -Fq lume", text)
        verify_text = text[text.index("<<'REMOTE_VERIFY'") :]
        self.assertNotIn("export LANG=C.UTF-8", verify_text)
        self.assertNotIn("export LC_CTYPE=C.UTF-8", verify_text)
        self.assertIn('system = "aarch64-darwin"', text)
        self.assertIn('profiles = ["base", "mac"]', text)
        self.assertIn("locale -a | grep -Fx 'C.UTF-8'", text)
        self.assertIn("env -i LANG=C.UTF-8 LC_CTYPE=C.UTF-8", text)

    def test_mac_task_does_not_copy_private_host_state_or_pipe_installers(self) -> None:
        text = TASK.read_text()
        for forbidden in (
            '"$HOME/.ssh/id_',
            'cp "$HOME/.ssh',
            "curl | bash",
            "curl -sSfL",
            "curl -fsSL",
            "test:bootstrap:mac-sip",
            "darwin-rebuild switch",
            "sudo defaults write",
        ):
            with self.subTest(pattern=forbidden):
                self.assertNotIn(forbidden, text)
        self.assertIn("rm -rf", text)
        self.assertIn("trap cleanup EXIT", text)
        self.assertIn("trap 'exit 130' INT", text)
        self.assertIn("trap 'exit 143' TERM", text)

    def test_mac_task_uses_lume_account_only_for_public_key_bootstrap(self) -> None:
        text = TASK.read_text()
        self.assertIn("--user lume", text)
        self.assertIn("--password lume", text)
        self.assertIn("authorized_keys", text)
        self.assertIn('ssh "${ssh_options[@]}"', text)
        self.assertIn('scp "${scp_options[@]}"', text)
        self.assertNotIn('scp "$ssh_key"', text)


if __name__ == "__main__":
    unittest.main()
