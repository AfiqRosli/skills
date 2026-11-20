"""Tests for verify.py — check discovery, JSON report shape."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "verify.py"


def load_verify():
    spec = importlib.util.spec_from_file_location("verify", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVerify(unittest.TestCase):
    def test_no_package_json(self):
        with tempfile.TemporaryDirectory() as td:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), td],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 2)

    def test_report_shape_with_fake_scripts(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / "package.json").write_text(json.dumps({
                "scripts": {
                    # 'exit 0'/'exit 1' are valid shell commands on all platforms
                    "type-check": "exit 0",
                    "lint": "exit 1",
                }
            }))
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(target),
                 "--checks", "type-check,lint"],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(proc.stdout)
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["summary"]["passed"], 1)
            self.assertEqual(report["summary"]["failed"], 1)
            lint = next(c for c in report["checks"] if c["check"] == "lint")
            self.assertEqual(lint["exit_code"], 1)

    def test_check_timeout_kills_and_flags_exit_hang(self):
        verify = load_verify()
        with tempfile.TemporaryDirectory() as td:
            class HungProc:
                returncode = -9

                def communicate(self, timeout=None):
                    if timeout:
                        raise subprocess.TimeoutExpired(cmd="x", timeout=timeout)
                    # After the kill: build had already printed its marker
                    return ("✨ Build complete!", "")

            with mock.patch.object(verify.subprocess, "Popen", return_value=HungProc()), \
                 mock.patch.object(verify, "kill_tree") as kill:
                r = verify.run_check(Path(td), "build", "bun", 40, False, 5)

            self.assertEqual(r["status"], "fail")
            self.assertTrue(r["timed_out"])
            self.assertIn("Build complete", "\n".join(r["output_tail"]))
            self.assertIn("leaked handle", r["note"])
            kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
