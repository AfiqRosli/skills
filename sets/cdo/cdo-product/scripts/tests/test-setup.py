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


def make_core(root: Path):
    orch = root / "docs" / "orchestration"
    orch.mkdir(parents=True)
    return orch


class TestSetup(unittest.TestCase):
    def test_blocked_without_cdo_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_setup(Path(tmp))
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(data["status"], "blocked")

    def test_installs_backlog_and_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = make_core(root)
            proc, data = run_setup(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((orch / "backlogs" / "product.md").is_file())
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            self.assertIn("cdo-product", caps["departments"])
            self.assertIn("co-sign", caps["departments"]["cdo-product"]["capabilities"])

    def test_idempotent_and_preserves_other_depts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = make_core(root)
            run_setup(root)
            # a second dept already registered + a hand-added backlog line
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            caps["departments"]["cdo-eng"] = {"dept": "cdo-eng"}
            (orch / "capabilities.yaml").write_text(yaml.safe_dump(caps), encoding="utf-8")
            (orch / "backlogs" / "product.md").write_text(
                (orch / "backlogs" / "product.md").read_text(encoding="utf-8") + "- [ ] P9 custom\n",
                encoding="utf-8",
            )
            proc, data = run_setup(root)
            self.assertEqual(proc.returncode, 0)
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            self.assertIn("cdo-eng", caps["departments"])  # preserved
            self.assertIn("P9 custom", (orch / "backlogs" / "product.md").read_text(encoding="utf-8"))

    def test_delegate_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_core(root)
            proc, data = run_setup(root)
            self.assertIn("delegates", data)
            self.assertIsInstance(data["delegates"]["missing"], list)


if __name__ == "__main__":
    unittest.main()
