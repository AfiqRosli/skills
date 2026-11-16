"""Tests for metrics.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "metrics.py"


def run(orch):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--orchestration-dir", str(orch)],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestMetrics(unittest.TestCase):
    def test_computes_from_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "docs" / "orchestration"
            orch.mkdir(parents=True)
            (orch / "flow-ledger.yaml").write_text(
                "pool:\n  confirmed: [S3]\n  quarantined:\n    - {key: S9, reason: x}\n"
                "stories:\n"
                "  S1: {status: verified, attempts: 2, step_started: '2026-10-14T08:00',\n"
                "       findings: ['2026-10-14T09:30 dev done']}\n"
                "  S2: {status: in-flight, attempts: 1, step_started: '2026-10-14T10:00'}\n"
                "autonomy: {enabled: true, streak: 7, threshold: 10}\n",
                encoding="utf-8")
            proc, data = run(orch)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["stories_by_status"]["verified"], 1)
            self.assertEqual(data["stories_by_status"]["in-flight"], 1)
            self.assertEqual(data["completed"], 1)
            self.assertEqual(data["cycle_minutes"]["avg"], 90.0)
            self.assertEqual(data["quarantined"], 1)
            self.assertAlmostEqual(data["attempts"]["avg"], 1.5)

    def test_empty_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "docs" / "orchestration"
            orch.mkdir(parents=True)
            (orch / "flow-ledger.yaml").write_text("stories: {}\n", encoding="utf-8")
            proc, data = run(orch)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["completed"], 0)


if __name__ == "__main__":
    unittest.main()
