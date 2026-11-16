"""Tests for state-digest.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "state-digest.py"


def run_digest(orch: Path, extra=()):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), *extra],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def minutes_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=n)).strftime("%Y-%m-%dT%H:%M")


class TestStateDigest(unittest.TestCase):
    def test_missing_ledger_is_anomaly(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_digest(Path(tmp))
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("flow-ledger" in a for a in data["integrity_anomalies"]))

    def test_stall_detection_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text(
                f"stories:\n  S1:\n    status: in-flight\n    step: develop\n"
                f"    step_started: '{minutes_ago(120)}'\n"
                f"  S2:\n    status: in-flight\n    step: audit\n"
                f"    step_started: '{minutes_ago(10)}'\n",
                encoding="utf-8",
            )
            proc, data = run_digest(orch, ["--stall-timeout-minutes", "45"])
            self.assertIn("S1", data["stalled_stories"])
            self.assertNotIn("S2", data["stalled_stories"])

    def test_dispatch_locks_fresh_and_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text("stories: {}\n", encoding="utf-8")
            locks = orch / "locks"
            locks.mkdir()
            lock = locks / "S1.lock"
            lock.write_text(f"session-1 {minutes_ago(5)} S1", encoding="utf-8")
            _, data = run_digest(orch)
            self.assertIn("S1", data["dispatch_locks"])
            self.assertFalse(data["dispatch_locks"]["S1"]["stale"])

            lock.write_text(f"session-1 {minutes_ago(300)} S1", encoding="utf-8")
            _, data = run_digest(orch)
            self.assertTrue(data["dispatch_locks"]["S1"]["stale"])

    def test_legacy_dispatch_lock_still_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text("stories: {}\n", encoding="utf-8")
            (orch / "dispatch.lock").write_text(
                f"session-1 {minutes_ago(5)} S9", encoding="utf-8")
            _, data = run_digest(orch)
            self.assertIn("S9", data["dispatch_locks"])
            self.assertTrue(data["dispatch_locks"]["S9"]["legacy"])

    def test_parallel_inflight_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text(
                f"stories:\n  S1:\n    status: in-flight\n    step: dev\n"
                f"    step_started: '{minutes_ago(10)}'\n    session: w-S1\n"
                f"  S2:\n    status: in-flight\n    step: qa\n"
                f"    step_started: '{minutes_ago(5)}'\n    session: w-S2\n",
                encoding="utf-8",
            )
            locks = orch / "locks"
            locks.mkdir()
            (locks / "S1.lock").write_text(f"w-S1 {minutes_ago(10)} S1", encoding="utf-8")
            (locks / "S2.lock").write_text(f"w-S2 {minutes_ago(5)} S2", encoding="utf-8")
            _, data = run_digest(orch)
            self.assertEqual(len(data["in_flight"]), 2)
            self.assertTrue(all(f["lock_held"] for f in data["in_flight"]))
            self.assertEqual(data["stalled_stories"], [])

    def test_inflight_without_lock_anomalies(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text(
                f"stories:\n  S1:\n    status: in-flight\n    step: dev\n"
                f"    step_started: '{minutes_ago(10)}'\n",
                encoding="utf-8",
            )
            _, data = run_digest(orch)
            self.assertTrue(any("no lock" in a for a in data["integrity_anomalies"]))

    def test_frago_pending_counts_unconsumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text("stories: {}\n", encoding="utf-8")
            orch.joinpath("frago-inbox.md").write_text(
                "### 2026-10-14 09:00\nhalt after current\n→ processed 09:05 halted\n\n"
                "### 2026-10-14 10:00\nreprioritize story 9\n",
                encoding="utf-8",
            )
            _, data = run_digest(orch)
            self.assertEqual(data["frago_pending"], 1)

    def test_checklist_section_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text("stories: {}\n", encoding="utf-8")
            orch.joinpath("alignment-checklist.md").write_text(
                "## Needs Attention\n- [ ] a\n- [ ] b\n## Routine\n- [ ] c\n- [x] done\n",
                encoding="utf-8",
            )
            _, data = run_digest(orch)
            self.assertEqual(data["operator_items_pending"]["Needs Attention"], 2)
            self.assertEqual(data["operator_items_pending"]["Routine"], 1)
            self.assertEqual(data["operator_items_total"], 3)

    def test_delivered_pending_per_attempt(self):
        """Reviewable = shipped/blocked/killed/deferred; a story reviewed at
        attempt 1 but re-shipped at attempt 2 is pending again."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text(
                "stories:\n"
                "  S1: {status: shipped, attempts: 1}\n"
                "  S2: {status: blocked, attempts: 1}\n"
                "  S3: {status: shipped, attempts: 2,\n"
                "       delivery_review: {verdict: sound, attempt: 1}}\n"
                "  S4: {status: shipped, attempts: 1,\n"
                "       delivery_review: {verdict: sound, attempt: 1}}\n",
                encoding="utf-8",
            )
            _, data = run_digest(orch)
            self.assertEqual(set(data["delivered_pending"]), {"S1", "S2", "S3"})

    def test_intent_stale_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text("stories: {}\n",
                                                        encoding="utf-8")
            _, data = run_digest(orch)
            self.assertTrue(data["intent_stale"])  # missing doc = stale
            (orch / "intent.md").write_text(
                "**Refreshed:** 2026-10-10\n", encoding="utf-8")
            (orch / "doctrine.md").write_text(
                "## Decision Log\n\n### 2026-10-14 — S5\n- decision: x\n",
                encoding="utf-8")
            _, data = run_digest(orch)
            self.assertTrue(data["intent_stale"])  # doctrine newer than stamp
            (orch / "intent.md").write_text(
                "**Refreshed:** 2026-10-15\n", encoding="utf-8")
            _, data = run_digest(orch)
            self.assertFalse(data["intent_stale"])

    def test_wave_pending_on_drain(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text(
                "batch: {id: b1}\n"
                "pool: {confirmed: []}\n"
                "stories:\n  S1: {status: shipped, attempts: 1,\n"
                "       delivery_review: {verdict: sound, attempt: 1}}\n",
                encoding="utf-8",
            )
            _, data = run_digest(orch)
            self.assertTrue(data["wave_pending"])
            # filed wave clears it
            orch.joinpath("flow-ledger.yaml").write_text(
                "batch: {id: b1, wave_review: {at: '2026-10-15'}}\n"
                "pool: {confirmed: []}\n"
                "stories:\n  S1: {status: shipped, attempts: 1,\n"
                "       delivery_review: {verdict: sound, attempt: 1}}\n",
                encoding="utf-8",
            )
            _, data = run_digest(orch)
            self.assertFalse(data["wave_pending"])

    def test_flag_rate_by_conf_band(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text(
                "stories:\n"
                "  S1: {status: shipped,\n"
                "       delivery_review: {verdict: sound, attempt: 1}}\n"
                "  S2: {status: shipped,\n"
                "       delivery_review: {verdict: 'flagged:delivery-x', attempt: 1}}\n",
                encoding="utf-8",
            )
            cards = orch / "alignment" / "2026" / "10" / "15"
            cards.mkdir(parents=True)
            (cards / "S1.md").write_text("- **Confidence:** 97%\n")
            (cards / "S2.md").write_text("- **Confidence:** 97%\n")
            _, data = run_digest(orch)
            band = data["review_flag_rate_by_conf"][">=95"]
            self.assertEqual(band, {"filed": 2, "flagged": 1})

    def test_autonomy_surfaced_from_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            orch.joinpath("flow-ledger.yaml").write_text(
                "autonomy:\n  enabled: true\n  streak: 11\n  threshold: 10\n",
                encoding="utf-8",
            )
            _, data = run_digest(orch)
            self.assertTrue(data["autonomy"]["self_approve_active"])
            self.assertEqual(data["autonomy"]["streak"], 11)


if __name__ == "__main__":
    unittest.main()
