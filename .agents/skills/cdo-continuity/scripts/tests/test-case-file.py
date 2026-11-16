"""Tests for case-file.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CASEFILE = Path(__file__).parent.parent / "case-file.py"


def run(*args):
    proc = subprocess.run([sys.executable, str(CASEFILE), *args],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestCaseFile(unittest.TestCase):
    def test_assembles_from_all_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "docs" / "orchestration"
            (orch / "backlogs").mkdir(parents=True)
            (orch / "alignment" / "2026" / "10" / "14").mkdir(parents=True)
            (orch / "flow-ledger.yaml").write_text(
                "stories:\n"
                "  S5: {status: quarantined, attempts: 3, step: dev,\n"
                "       findings: ['2026-10-14T08:00 stall', '2026-10-14T08:30 retry failed']}\n"
                "pool:\n  confirmed: []\n  quarantined:\n    - {key: S5, reason: 'loop detected'}\n"
                "signals:\n  - {type: stall, key: S5, detail: 'dev step 45m'}\n",
                encoding="utf-8")
            (orch / "backlogs" / "code.md").write_text("- [-] S5 — broken thing\n", encoding="utf-8")
            (orch / "alignment" / "2026" / "10" / "14" / "S5.md").write_text("# card S5", encoding="utf-8")
            (orch / "doctrine.md").write_text("- 2026-10-14 S5 looped on migrations\n", encoding="utf-8")
            proc, data = run("--orchestration-dir", str(orch), "S5")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["timeline"]["ledger_story"]["status"], "quarantined")
            self.assertEqual(len(data["timeline"]["signals"]), 1)
            self.assertEqual(data["timeline"]["quarantine"][0]["reason"], "loop detected")
            self.assertTrue((orch / "learning" / "cases").glob("S5-*.md"))

    def test_unknown_key_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "docs" / "orchestration"
            orch.mkdir(parents=True)
            proc, data = run("--orchestration-dir", str(orch), "ZZZ")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(data["status"], "not_found")


if __name__ == "__main__":
    unittest.main()
