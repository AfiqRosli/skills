#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for health-check.py — exercises run() with python itself (bun-free)."""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixture import SCRIPTS  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestHealthCheck(unittest.TestCase):
    def test_run_pass_and_fail(self):
        hc = load("health-check")
        ok = hc.run([sys.executable, "-c", "print('hi')"], SCRIPTS)
        self.assertEqual(ok["status"], "pass")
        bad = hc.run([sys.executable, "-c", "import sys; sys.exit(3)"], SCRIPTS)
        self.assertEqual(bad["status"], "fail")
        self.assertEqual(bad["exit"], 3)

    def test_missing_binary_is_error_not_crash(self):
        hc = load("health-check")
        res = hc.run(["definitely-not-a-real-binary-xyz"], SCRIPTS)
        self.assertEqual(res["status"], "error")

    def test_cli_json_contract(self):
        # A bare temp dir outside any repo: bun finds no package.json, fails
        # fast, and the script must still emit valid JSON.
        import tempfile
        with tempfile.TemporaryDirectory() as bare:
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "health-check.py"), bare],
                capture_output=True, text=True, timeout=120)
        data = json.loads(proc.stdout)
        self.assertIn(data["status"], ("pass", "fail"))
        self.assertEqual(len(data["checks"]), 3)


if __name__ == "__main__":
    unittest.main()
