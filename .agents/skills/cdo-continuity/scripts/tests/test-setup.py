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
    def test_installs_and_probes_ir_delegates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            (root / ".agents" / "skills" / "bmad-bus-cybersec-team-incident-commander").mkdir(parents=True)
            (root / ".agents" / "skills" / "bmad-bus-cybersec-team-incident-commander" / "SKILL.md").write_text("x")
            proc, data = run("--project-root", str(root), "--assets-dir", str(ASSETS))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(data["ir_ready"])
            self.assertTrue((orch / "learning" / "cases").is_dir())
            self.assertTrue((orch / "backlogs" / "continuity.md").is_file())

    def test_blocked_without_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = run("--project-root", str(Path(tmp)))
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
