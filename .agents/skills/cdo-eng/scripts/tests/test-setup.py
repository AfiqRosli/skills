"""Tests for setup.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / "setup.py"
ASSETS = Path(__file__).parent.parent.parent / "assets"


def run_setup(root: Path, *extra):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root),
         "--assets-dir", str(ASSETS), *extra],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestSetup(unittest.TestCase):
    def test_blocked_without_cdo_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_setup(Path(tmp))
            self.assertEqual(proc.returncode, 1)

    def test_installs_and_flags_missing_cdo_code_e2e(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            proc, data = run_setup(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(data["code_pipeline_ready"])
            self.assertTrue(data["warnings"])
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            self.assertIn("produce", caps["departments"]["cdo-eng"]["capabilities"])

    def test_detects_cdo_code_e2e_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs" / "orchestration").mkdir(parents=True)
            (root / ".agents" / "skills" / "cdo-code-e2e").mkdir(parents=True)
            (root / ".agents" / "skills" / "cdo-code-e2e" / "SKILL.md").write_text("x")
            proc, data = run_setup(root)
            self.assertTrue(data["code_pipeline_ready"])


if __name__ == "__main__":
    unittest.main()
