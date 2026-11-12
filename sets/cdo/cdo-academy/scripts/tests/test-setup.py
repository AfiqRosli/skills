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


def run(root):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(root),
                           "--assets-dir", str(ASSETS)],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestSetup(unittest.TestCase):
    def test_installs_academy_platform_and_ops_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # public platform
            academy = root / "docs" / "academy"
            self.assertTrue((academy / "index.md").is_file())
            self.assertTrue((academy / "catalog.yaml").is_file())
            # ops side under orchestration
            self.assertTrue((orch / "learning" / "knowledge").is_dir())
            self.assertTrue((orch / "backlogs" / "curriculum.md").is_file())
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            self.assertIn("extract", caps["departments"]["cdo-academy"]["capabilities"])
            self.assertEqual(data["academy_dir"], str(academy.resolve()))


if __name__ == "__main__":
    unittest.main()
