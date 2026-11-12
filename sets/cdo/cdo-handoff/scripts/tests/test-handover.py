"""Tests for handover.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "handover.py"


def run(orch: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), *args],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_orch(root: Path):
    orch = root / "docs" / "orchestration"
    orch.mkdir(parents=True)
    (orch / "flow-ledger.yaml").write_text(
        "batch: {id: b3, manifest: [S1, S2]}\n"
        "pool:\n  confirmed: [S2]\n  quarantined:\n    - {key: S9, reason: missing creds}\n"
        "stories:\n  S1: {status: in-flight, step: dev, session: s-7}\n"
        "autonomy: {enabled: true, streak: 6, threshold: 10}\n"
        "signals:\n  - {type: stall, key: S1, detail: 90m at dev, at: '2026-10-14T09:00'}\n",
        encoding="utf-8",
    )
    (orch / "alignment-checklist.md").write_text(
        "## Needs Attention\n\n- [ ] E1 — approve schema migration\n",
        encoding="utf-8",
    )
    return orch


class TestHandover(unittest.TestCase):
    def test_write_rebuilds_from_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run(orch, "write", "--summary", "s-7 ended mid-dev")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = (orch / "handover.md").read_text(encoding="utf-8")
            self.assertIn("batch: b3", doc)
            self.assertIn("S1 @ dev", doc)
            self.assertIn("S9: missing creds", doc)
            self.assertIn("stall", doc)
            self.assertIn("E1 — approve schema migration", doc)
            self.assertIn("s-7 ended mid-dev", doc)

    def test_write_infers_next_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run(orch, "write")
            self.assertIn("in-flight", data["next_action"])
            self.assertIn("S1", data["next_action"])

    def test_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run(orch, "write", "--next-action", "dispatch S2")
            proc, data = run(orch, "read")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["in_flight"], "S1")
            self.assertIn("dispatch S2", data["next_action"])
            self.assertEqual(data["integrity_anomalies"], [])

    def test_read_detects_handover_lying(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run(orch, "write")
            # ledger changed after handover — story finished
            (orch / "flow-ledger.yaml").write_text(
                "pool: {confirmed: [S2], quarantined: []}\n"
                "stories:\n  S1: {status: done}\n",
                encoding="utf-8",
            )
            proc, data = run(orch, "read")
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("disagrees" in a for a in data["integrity_anomalies"]))

    def test_read_no_handover(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run(orch, "read")
            self.assertEqual(data["status"], "no-handover")


if __name__ == "__main__":
    unittest.main()
