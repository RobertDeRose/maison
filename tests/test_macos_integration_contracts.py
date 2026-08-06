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

    def test_mac_task_uses_pinned_disposable_lume_worker(self) -> None:
        text = TASK.read_text()
        for contract in (
            "macos-tahoe-cua:26.5.2",
            "lume_command pull",
            "base_provenance",
            "image=$image",
            "lume_get_json",
            "--format json",
            "lume_command clone",
            "lume_command run",
            "--detach",
            "--display none",
            '"$lume_binary" stop',
            '"$lume_binary" delete',
            "--force",
            "csrutil status",
            "25F84",
            "/Library/Developer/CommandLineTools",
            "autoLoginUser",
            "IdentitiesOnly=yes",
            "ssh-keygen",
            "scp",
            "consumer_integration_stage",
            "consumer_integration_fetch_bootstrap",
            "MAISON_CONSUMER_ROOT",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)

        self.assertIn('system = "aarch64-darwin"', text)
        self.assertIn('profiles = ["base", "mac"]', text)
        self.assertIn('test "$LANG" = "C.UTF-8"', text)
        self.assertIn('test "$LC_CTYPE" = "C.UTF-8"', text)

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
