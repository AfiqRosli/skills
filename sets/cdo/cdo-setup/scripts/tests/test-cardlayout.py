"""Tests for cdo-setup cardlayout.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "cardlayout.py"


def run_layout(*args):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestCardlayout(unittest.TestCase):
    def test_contract_dump(self):
        proc, data = run_layout()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        c = data["contract"]
        self.assertIn("drafts", c["bays"])
        self.assertIn("{key}", c["archive"])
        self.assertIn("schema-migration", c["risk_tokens"])

    def test_key_requires_orch_dir(self):
        proc, data = run_layout("13-01-x")
        self.assertEqual(proc.returncode, 2)

    def test_confirmed_card_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "orch"
            archive = orch / "alignment" / "2026" / "01" / "01"
            archive.mkdir(parents=True)
            (archive / "13-01-x.md").write_text("# Alignment Card — 13-01-x: T\n")
            proc, data = run_layout("13-01-x", "--orchestration-dir", str(orch))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "confirmed")
            self.assertTrue(data["confirmed_card"].endswith("13-01-x.md"))

    def test_bay_card_is_not_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "orch"
            drafts = orch / "alignment" / "drafts"
            drafts.mkdir(parents=True)
            (drafts / "13-01-x.md").write_text("# Alignment Card — 13-01-x: T\n")
            proc, data = run_layout("13-01-x", "--orchestration-dir", str(orch))
            self.assertEqual(proc.returncode, 1)
            self.assertIsNone(data["confirmed_card"])

    def test_rejected_card_not_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "orch"
            archive = orch / "alignment" / "2026" / "01" / "01"
            archive.mkdir(parents=True)
            (archive / "k.md").write_text("<!-- reject — scope -->\n# Card\n")
            proc, data = run_layout("k", "--orchestration-dir", str(orch))
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
