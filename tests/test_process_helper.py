from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

from tests.support.processes import CommandTimeout, run, temporary_directory


class ProcessHelperTest(unittest.TestCase):
    def test_success_captures_output_and_cwd(self) -> None:
        with temporary_directory() as tmp:
            marker = tmp / "marker.txt"
            result = run(
                [sys.executable, "-c", "from pathlib import Path; Path('marker.txt').write_text('ok'); print('done')"],
                cwd=tmp,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "done")
            self.assertEqual(marker.read_text(), "ok")

    def test_check_failure_includes_truncated_diagnostics(self) -> None:
        with self.assertRaisesRegex(AssertionError, "exit code 7") as caught:
            run(
                [
                    sys.executable,
                    "-c",
                    "import sys; print('o' * 5000); print('e' * 5000, file=sys.stderr); raise SystemExit(7)",
                ],
                check=True,
            )

        message = str(caught.exception)
        self.assertIn("stdout", message)
        self.assertIn("stderr", message)
        self.assertLess(len(message), 3000)

    def test_environment_is_explicitly_passed(self) -> None:
        env = os.environ.copy()
        env["MAISON_HELPER_TEST"] = "present"
        result = run(
            [sys.executable, "-c", "import os; print(os.environ['MAISON_HELPER_TEST'])"],
            env=env,
        )
        self.assertEqual(result.stdout.strip(), "present")

    def test_timeout_terminates_process_group(self) -> None:
        result_path: Path
        with temporary_directory() as tmp:
            result_path = tmp / "child-alive"
            script = tmp / "spawn.py"
            script.write_text(
                "import pathlib, subprocess, sys, time\n"
                "marker = pathlib.Path(sys.argv[1])\n"
                "import "
                "subprocess as sp\n"
                "sp.Popen([sys.executable, '-c', \"import pathlib, sys, time; time.sleep(5); pathlib.Path(sys.argv[1]).write_text('alive')\", str(marker)])\n"
                "time.sleep(5)\n"
            )
            start = time.monotonic()
            with self.assertRaises(CommandTimeout):
                run([sys.executable, str(script), str(result_path)], timeout=0.2)
            self.assertLess(time.monotonic() - start, 3)
            time.sleep(0.4)
            self.assertFalse(result_path.exists())

    def test_timeout_upper_bound_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            run([sys.executable, "-c", "print('never')"], timeout=301)


if __name__ == "__main__":
    unittest.main()
