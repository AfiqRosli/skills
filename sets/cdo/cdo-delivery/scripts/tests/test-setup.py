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


def run(root, *args):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(root),
                           "--assets-dir", str(ASSETS), *args],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestSetup(unittest.TestCase):
    def test_blocked_without_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = run(Path(tmp))
            self.assertEqual(proc.returncode, 1)

    def test_installs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((orch / "backlogs" / "delivery.md").is_file())
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            self.assertIn("plan", caps["departments"]["cdo-delivery"]["capabilities"])


if __name__ == "__main__":
    unittest.main()
