from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from tests.support.topology import *


class SelfUpdateTest(unittest.TestCase):
    def make_consumer(self, root: Path) -> Path:
        consumer = root / "consumer"
        consumer.mkdir()
        (consumer / "flake.nix").write_text("{ outputs = _: {}; }\n")
        (consumer / "flake.lock").write_text(
            json.dumps(
                {
                    "nodes": {
                        "root": {"inputs": {"maison": "maison"}},
                        "maison": {"locked": {"type": "github", "rev": "old"}},
                    },
                    "root": "root",
                }
            )
            + "\n"
        )
        (consumer / "inventory.toml").write_text("schema = 1\n")
        git_init(consumer)
        return consumer

    def task_environment(
        self, consumer: Path, fake_bin: Path, state_file: Path, log: Path, cli_log: Path
    ) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "MAISON_HOME": str(ROOT),
                "MAISON_CONSUMER_ROOT": str(consumer),
                "MISE_PROJECT_ROOT": str(ROOT),
                "MAISON_CLI_STATE_FILE": str(state_file),
                "SELF_LOG": str(log),
                "SELF_CLI_LOG": str(cli_log),
                "SELF_CANDIDATE_STORE": str(state_file.parent / "candidate-store"),
                "MISE_GITHUB_TOKEN": "fixture-token",
                "XDG_STATE_HOME": str(state_file.parent / "xdg-state"),
                "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
            }
        )
        return environment

    def install_fake_nix(self, fake_bin: Path, candidate_status: int = 0) -> None:
        executable(
            fake_bin / "nix",
            """#!/bin/sh
set -eu
printf 'nix %s|%s\n' "$PWD" "$*" >>"$SELF_LOG"
case " $* " in
  *" flake update "*)
    output=""
    previous=""
    for argument in "$@"; do
      if [ "$previous" = --output-lock-file ]; then output="$argument"; fi
      previous="$argument"
    done
    cat >"$output" <<'EOF'
{"nodes":{"root":{"inputs":{"maison":"maison-new"}},"maison-new":{"locked":{"type":"github","rev":"new"}}},"root":"root"}
EOF
    ;;
  *" build "*)
    printf '%s\n' "$SELF_CANDIDATE_STORE"
    ;;
  *)
    echo "unexpected nix invocation" >&2
    exit 91
    ;;
esac
""",
        )
        executable(
            fake_bin / "nix-store",
            """#!/bin/sh
set -eu
root=""
previous=""
for argument in "$@"; do
  if [ "$previous" = --add-root ]; then root="$argument"; fi
  previous="$argument"
done
[ -n "$root" ] || exit 92
mkdir -p "$root/bin"
cp "$SELF_CANDIDATE_SCRIPT" "$root/bin/maison"
chmod 755 "$root/bin/maison"
""",
        )
        candidate = fake_bin / "candidate-maison"
        executable(
            candidate,
            f"""#!/bin/sh
printf 'candidate:%s|%s|%s\n' "$*" "${{MAISON_HOME:-}}" "${{MAISON_CONSUMER_ROOT:-}}" >>"$SELF_CLI_LOG"
exit {candidate_status}
""",
        )

    def run_task(self, consumer: Path, environment: dict[str, str]):
        return run(
            ["bash", str(ROOT / ".mise/tasks/self/update")],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

    def test_success_updates_only_consumer_lock_and_cli_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            state_file = temp / "state" / "maison-cli"
            state_file.parent.mkdir()
            state_file.write_text("old-cli\n")
            log = temp / "nix.log"
            cli_log = temp / "candidate.log"
            self.install_fake_nix(fake_bin)
            environment = self.task_environment(consumer, fake_bin, state_file, log, cli_log)
            environment["SELF_CANDIDATE_SCRIPT"] = str(fake_bin / "candidate-maison")
            maison_lock = (ROOT / "flake.lock").read_bytes()

            result = self.run_task(consumer, environment)

            self.assertEqual(result.returncode, 0, result.stderr)
            lock = json.loads((consumer / "flake.lock").read_text())
            self.assertEqual(lock["nodes"]["root"]["inputs"]["maison"], "maison-new")
            self.assertEqual((ROOT / "flake.lock").read_bytes(), maison_lock)
            self.assertTrue(state_file.read_text().startswith(str(state_file) + ".root."))
            self.assertEqual(state_file.stat().st_mode & 0o777, 0o600)
            self.assertIn("candidate:consumer validate --consumer", cli_log.read_text())
            self.assertIn(str(consumer), cli_log.read_text())
            self.assertIn(" flake update ", log.read_text())
            self.assertIn(" maison\n", log.read_text())

    def test_failure_restores_lock_and_cli_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            consumer = self.make_consumer(temp)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            state_file = temp / "state" / "maison-cli"
            state_file.parent.mkdir()
            state_file.write_text("old-cli\n")
            original_lock = (consumer / "flake.lock").read_bytes()
            log = temp / "nix.log"
            cli_log = temp / "candidate.log"
            self.install_fake_nix(fake_bin, candidate_status=23)
            environment = self.task_environment(consumer, fake_bin, state_file, log, cli_log)
            environment["SELF_CANDIDATE_SCRIPT"] = str(fake_bin / "candidate-maison")

            result = self.run_task(consumer, environment)

            self.assertEqual(result.returncode, 1)
            self.assertEqual((consumer / "flake.lock").read_bytes(), original_lock)
            self.assertEqual(state_file.read_text(), "old-cli\n")
            self.assertIn("candidate Maison validation failed", result.stderr)
            self.assertIn("candidate:consumer validate", cli_log.read_text())
            self.assertEqual(list((temp / "state").glob("*.root.*")), [])

    def test_launcher_delegates_to_persisted_cli_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            candidate = temp / "candidate-maison"
            log = temp / "launcher.log"
            executable(candidate, f'#!/bin/sh\nprintf \'%s\n\' "$*" >"{log}"\n')
            state_file = temp / "cli-state"
            state_file.write_text(f"{candidate}\n")
            environment = os.environ.copy()
            environment.pop("MAISON_HOME", None)
            environment.pop("MISE_PROJECT_ROOT", None)
            environment["MAISON_CLI_STATE_FILE"] = str(state_file)

            result = run(
                ["bash", str(ROOT / "bin/maison"), "--version"],
                cwd=temp,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().strip(), "--version")


if __name__ == "__main__":
    unittest.main()
