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
            backlog = (orch / "backlogs" / "docs.md").read_text(encoding="utf-8")
            self.assertIn("DOC1", backlog)
            self.assertIn("DOC2", backlog)
            self.assertIn("type: guide", backlog)

    def test_idempotent_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run(orch)
            proc, data = run(orch)
            self.assertEqual(data["status"], "no_new")
            backlog = (orch / "backlogs" / "docs.md").read_text(encoding="utf-8")
            self.assertEqual(backlog.count("DOC"), 2)

    def test_source_token_boundary(self):
        """A backlog referencing S12 must not block feeding S1."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "backlogs" / "docs.md").write_text(
                "- [ ] DOC1 — x | source: S12 | type: guide\n", encoding="utf-8")
            proc, data = run(orch)
            self.assertEqual(len(data["items_added"]), 2)


if __name__ == "__main__":
    unittest.main()
