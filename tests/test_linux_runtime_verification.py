from __future__ import annotations

import importlib.util
import sys

from tests.support.topology import *

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/verify_linux_runtime.py"


def load_runtime_verifier():
    spec = importlib.util.spec_from_file_location("linux_runtime_verifier", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RuntimeSnapshotContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_runtime_verifier()

    def snapshot(self, **changes):
        values = {
            "systemd_active": True,
            "hostname": "example-linux",
            "timezone": "America/New_York",
            "localtime_target": "/usr/share/zoneinfo/America/New_York",
            "ssh_config_valid": True,
            "ssh_reload_succeeded": True,
            "active_units": frozenset({"system-manager.target", "prefill-authorized-keys.service"}),
        }
        values.update(changes)
        return self.verifier.RuntimeSnapshot(**values)

    def verify(self, snapshot):
        return self.verifier.verify_runtime_state(
            snapshot,
            expected_hostname="example-linux",
            expected_timezone="America/New_York",
            required_units=(
                "system-manager.target",
                "prefill-authorized-keys.service",
            ),
        )

    def assert_rejected(self, snapshot, field: str) -> None:
        with self.assertRaises(self.verifier.RuntimeVerificationError) as raised:
            self.verify(snapshot)
        self.assertIn(field, str(raised.exception).lower())

    def test_accepts_matching_systemd_runtime(self) -> None:
        self.assertEqual(self.verify(self.snapshot()), ())

    def test_rejects_non_systemd_runtime(self) -> None:
        self.assert_rejected(self.snapshot(systemd_active=False), "systemd")

    def test_rejects_active_hostname_mismatch(self) -> None:
        self.assert_rejected(self.snapshot(hostname="wrong-host"), "hostname")

    def test_rejects_timezone_mismatch(self) -> None:
        self.assert_rejected(self.snapshot(timezone="UTC"), "timezone")

    def test_rejects_localtime_mismatch(self) -> None:
        self.assert_rejected(self.snapshot(localtime_target="/usr/share/zoneinfo/UTC"), "localtime")

    def test_rejects_ssh_configuration_failure(self) -> None:
        self.assert_rejected(self.snapshot(ssh_config_valid=False), "ssh")

    def test_rejects_ssh_reload_failure(self) -> None:
        self.assert_rejected(self.snapshot(ssh_reload_succeeded=False), "reload")

    def test_rejects_inactive_required_service_unit(self) -> None:
        self.assert_rejected(
            self.snapshot(
                active_units=frozenset({"system-manager.target"}),
            ),
            "prefill-authorized-keys.service",
        )


class LinuxRuntimeActivationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = read("nix/modules/linux/system.nix")
        cls.deployments = read("nix/lib/deployments.nix")
        cls.system_apply = read(".mise/tasks/system/apply")
        prefill_parts = cls.source.split("systemd.services.prefill-authorized-keys", 1)
        cls.prefill = (
            prefill_parts[1].split(
                "# ------------------------------------------------------------------ #\n  # Users", 1
            )[0]
            if len(prefill_parts) > 1
            else ""
        )

    def test_systemd_only_runtime_verifier_is_wired_into_activation(self) -> None:
        self.assertIn("scripts/verify_linux_runtime.py", self.source)
        self.assertRegex(self.source, r"system-manager\.preActivationAssertions\.systemd[A-Za-z0-9_-]*")
        self.assertIn("systemd.services.maison-runtime-verification", self.source)
        self.assertIn('wantedBy = [ "system-manager.target" ];', self.source)
        self.assertIn('after = [ "prefill-authorized-keys.service" ];', self.source)
        self.assertIn("system-manager.target", self.source)
        self.assertIn("prefill-authorized-keys.service", self.source)
        for argument in ("--expected-hostname", "--expected-timezone", "--required-unit"):
            with self.subTest(argument=argument):
                self.assertIn(argument, self.source)

    def test_ssh_reload_failure_is_not_suppressed(self) -> None:
        self.assertIn("sshd -t", self.prefill)
        self.assertRegex(self.prefill, r"systemctl.{0,160}(reload|restart|try-restart)")
        self.assertNotRegex(self.prefill, r"systemctl[^\n]*\|\|\s*true")

    def test_runtime_verification_is_required_and_persistent(self) -> None:
        runtime_parts = self.source.split("systemd.services.maison-runtime-verification", 1)
        self.assertEqual(len(runtime_parts), 2)
        runtime = runtime_parts[1]
        self.assertIn('requiredBy = [ "system-manager.target" ];', runtime)
        self.assertIn('before = [ "system-manager.target" ];', runtime)
        self.assertIn("RemainAfterExit = true;", runtime)
        self.assertIn("RemainAfterExit = true;", self.prefill)

    def test_localtime_is_replaced_when_preexisting(self) -> None:
        localtime_parts = self.source.split('"localtime" = {', 1)
        self.assertEqual(len(localtime_parts), 2)
        localtime = localtime_parts[1].split("};", 1)[0]
        self.assertIn("replaceExisting = true;", localtime)

    def test_activation_adapters_reject_degraded_runtime(self) -> None:
        for source in (self.system_apply, self.deployments):
            with self.subTest(source=source):
                for unit in ("system-manager.target", "maison-runtime-verification.service"):
                    self.assertIn(f"systemctl is-active --quiet {unit}", source)

    def test_deploy_rs_reuses_the_system_configuration_activation(self) -> None:
        self.assertIn("base = systemConfigs.${name};", self.deployments)
        self.assertIn(
            'profilePath = "/nix/var/nix/profiles/system-manager-profiles/system-manager";',
            self.deployments,
        )


if __name__ == "__main__":
    unittest.main()
