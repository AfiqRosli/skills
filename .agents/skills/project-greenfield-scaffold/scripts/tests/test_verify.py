"""Tests for verify.py — check discovery, JSON report shape."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "verify.py"


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


if __name__ == "__main__":
    unittest.main()
