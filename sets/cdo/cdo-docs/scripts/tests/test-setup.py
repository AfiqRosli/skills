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
    def test_installs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((orch / "backlogs" / "docs.md").is_file())
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            caps = caps["departments"]["cdo-docs"]["capabilities"]
            self.assertIn("produce", caps)
            self.assertIn("audit", caps)
            self.assertIn("detect", caps)

    def test_detects_docs_stack_during_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            vp = root / "docs" / ".vitepress"
            vp.mkdir(parents=True)
            (vp / "config.ts").write_text("export default {};", encoding="utf-8")
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["docs_detection"]["framework"], "vitepress")
            profile = yaml.safe_load(
                (orch / "docs-profile.yaml").read_text(encoding="utf-8"))
            self.assertEqual(profile["framework"], "vitepress")
            self.assertEqual(profile["nav_config"], "docs/.vitepress/config.ts")

    def test_blocked_without_orchestration_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run(Path(tmp))
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(data["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
