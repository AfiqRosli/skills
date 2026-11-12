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

    def test_installs_and_finds_cybersec_delegates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            # fake a synced cybersec skill
            (root / ".agents" / "skills" / "bmad-bus-cybersec-team-security-architecture-review").mkdir(parents=True)
            (root / ".agents" / "skills" / "bmad-bus-cybersec-team-security-architecture-review" / "SKILL.md").write_text("x")
            proc, data = run_setup(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(data["security_audit_ready"])
            self.assertIn("bmad-bus-cybersec-team-security-architecture-review",
                          data["delegates"]["available"])
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            self.assertIn("security-audit", caps["departments"]["cdo-quality"]["capabilities"])

    def test_idempotent_and_preserves_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            run_setup(root)
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            caps["departments"]["cdo-product"] = {"dept": "cdo-product"}
            (orch / "capabilities.yaml").write_text(yaml.safe_dump(caps), encoding="utf-8")
            proc, data = run_setup(root)
            self.assertEqual(proc.returncode, 0)
            caps = yaml.safe_load((orch / "capabilities.yaml").read_text(encoding="utf-8"))
            self.assertIn("cdo-product", caps["departments"])


if __name__ == "__main__":
    unittest.main()
