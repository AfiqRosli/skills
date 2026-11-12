"""Tests for feed.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "feed.py"


def run(orch):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--orchestration-dir", str(orch)],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_orch(root):
    orch = root / "docs" / "orchestration"
    (orch / "backlogs").mkdir(parents=True)
    (orch / "flow-ledger.yaml").write_text(
        "stories:\n"
        "  S1: {status: done}\n"
        "  S2: {status: verified}\n"
        "  S3: {status: in-flight}\n"
        "  S4: {status: quarantined}\n",
        encoding="utf-8")
    return orch


class TestFeed(unittest.TestCase):
    def test_done_and_verified_feed_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run(orch)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(len(data["items_added"]), 2)
            sources = {i["source"] for i in data["items_added"]}
            self.assertEqual(sources, {"S1", "S2"})
            backlog = (orch / "backlogs" / "content.md").read_text(encoding="utf-8")
            self.assertIn("CT1", backlog)
            self.assertIn("CT2", backlog)

    def test_idempotent_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run(orch)
            proc, data = run(orch)
            self.assertEqual(data["status"], "no_new")
            backlog = (orch / "backlogs" / "content.md").read_text(encoding="utf-8")
            self.assertEqual(backlog.count("source: S1"), 1)


if __name__ == "__main__":
    unittest.main()
