"""Tests for setup.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SETUP = Path(__file__).parent.parent / "setup.py"
ASSETS = Path(__file__).parent.parent.parent / "assets"


def run(*args):
    proc = subprocess.run([sys.executable, str(SETUP), *args],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestSetup(unittest.TestCase):
    def test_installs_backlog_and_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            proc, data = run("--project-root", str(root), "--assets-dir", str(ASSETS))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((orch / "backlogs" / "platform.md").is_file())
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            self.assertIn("ship", caps["departments"]["cdo-platform"]["capabilities"])


if __name__ == "__main__":
    unittest.main()
