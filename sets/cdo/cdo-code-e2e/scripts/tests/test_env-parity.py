#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for env-parity.py — env-var name extraction and parity reporting."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixture import SCRIPTS, Fixture  # noqa: E402


class TestEnvParity(Fixture):
    def setUp(self):
        super().setUp()
        src = self.root / "stores" / "pay.ts"
        src.parent.mkdir(parents=True)
        src.write_text(
            "const a = process.env.STRIPE_KEY\n"
            "const b = import.meta.env.VITE_API_URL\n"
            'const c = process.env["SECRET_TOKEN"]\n',
            encoding="utf-8")
        (self.root / ".env").write_text("VITE_API_URL=x\n", encoding="utf-8")
        (self.root / ".env.example").write_text(
            "VITE_API_URL=\nSTRIPE_KEY=\n", encoding="utf-8")

    def run_parity(self, *files):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "env-parity.py"), str(self.root),
             "--files", *files], capture_output=True, text=True)

    def test_missing_names_reported(self):
        proc = self.run_parity(" M stores/pay.ts")
        data = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(data["status"], "fail")
        self.assertEqual(data["missing_in_env"], ["SECRET_TOKEN", "STRIPE_KEY"])
        self.assertEqual(data["missing_in_env_example"], ["SECRET_TOKEN"])
        self.assertIn("STRIPE_KEY", data["referenced"])

    def test_parity_passes_when_defined(self):
        (self.root / ".env").write_text(
            "VITE_API_URL=x\nSTRIPE_KEY=y\nSECRET_TOKEN=z\n", encoding="utf-8")
        (self.root / ".env.example").write_text(
            "VITE_API_URL=\nSTRIPE_KEY=\nSECRET_TOKEN=\n", encoding="utf-8")
        proc = self.run_parity("stores/pay.ts")
        data = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(data["status"], "pass")
        self.assertEqual(data["missing_in_env"], [])


if __name__ == "__main__":
    import unittest
    unittest.main()
