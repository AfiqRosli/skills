"""Tests for watch.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / "watch.py"

CHECKLIST = (
    "# Checklist\n\n## Needs Attention\n\n- [ ] S1 — pending\n\n"
    "## Routine Review\n\n- [x] S2 — done → sound 2020-01-01\n"
    "- [x] S3 — just resolved (no verdict date)\n"
)


def run_watch(orch: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), *args],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def minutes_ago(n):
    return (datetime.now(timezone.utc) - timedelta(minutes=n)).strftime("%Y-%m-%dT%H:%M")


def make_orch(root: Path, ledger_text=None):
    orch = root / "docs" / "orchestration"
    orch.mkdir(parents=True)
    (orch / "alignment-checklist.md").write_text(CHECKLIST, encoding="utf-8")
    (orch / "flow-ledger.yaml").write_text(
        ledger_text or "pool:\n  confirmed: []\n  quarantined: []\nstories: {}\n",
        encoding="utf-8",
    )
    return orch


class TestWatchScan(unittest.TestCase):
    def test_clean_org(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_watch(orch)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "clean")

    def test_stall_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), (
                "pool: {confirmed: [], quarantined: []}\nstories:\n"
                f"  S1: {{status: in-flight, step: dev, step_started: '{minutes_ago(120)}'}}\n"
            ))
            (orch / "locks").mkdir(exist_ok=True)
            (orch / "locks" / "S1.lock").write_text(f"s-1 {minutes_ago(120)} S1", encoding="utf-8")
            proc, data = run_watch(orch, "--stall-timeout-minutes", "45")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(data["signals"][0]["type"], "stall")
            # signal landed in the ledger for Marshal's triage
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["signals"][0]["type"], "stall")

    def test_inflight_without_lock_is_anomaly(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), (
                "pool: {confirmed: [], quarantined: []}\nstories:\n"
                f"  S1: {{status: in-flight, step: dev, step_started: '{minutes_ago(5)}'}}\n"
            ))
            _, data = run_watch(orch)
            self.assertTrue(any("locks/S1.lock" in a for a in data["anomalies"]))

    def test_draft_without_checklist_line_is_anomaly(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "alignment" / "drafts").mkdir(parents=True)
            (orch / "alignment" / "drafts" / "S9.md").write_text("# orphan", encoding="utf-8")
            _, data = run_watch(orch)
            self.assertTrue(any("S9" in a for a in data["anomalies"]))

    def test_cost_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), (
                "pool: {confirmed: [], quarantined: []}\nstories: {}\n"
                "cost: {budget: 5, burned: 6}\n"
            ))
            _, data = run_watch(orch)
            self.assertTrue(any(s["type"] == "cost-ceiling" for s in data["signals"]))

    def test_cost_ceiling_signal_is_resolvable(self):
        """The cost-ceiling signal carries key='cost' — a keyless signal can
        never resolve and would mute every future breach forever."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), (
                "pool: {confirmed: [], quarantined: []}\nstories: {}\n"
                "cost: {budget: 5, burned: 6}\n"
            ))
            run_watch(orch)
            proc, data = run_watch(orch, "--mode", "resolve", "--key", "cost")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("cost-ceiling", data["resolved"])

    def test_headless_flag_accepted(self):
        """SKILL.md advertises -H for headless callers — parse_args must
        accept it (output is machine JSON regardless)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_watch(orch, "-H")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "clean")


class TestWatchIntake(unittest.TestCase):
    def test_consumes_signal_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "signals").mkdir()
            (orch / "signals" / "line-stop-s3.md").write_text(
                "LINE_STOP: dev loop repeated identical diff 3×", encoding="utf-8"
            )
            proc, data = run_watch(orch, "--mode", "intake")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("line-stop-s3.md", data["consumed"])
            self.assertFalse((orch / "signals" / "line-stop-s3.md").exists())
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["signals"][0]["type"], "line-stop")


class TestWatchJanitor(unittest.TestCase):
    def test_prunes_resolved_and_breaks_stale_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            # legacy lock AND a fresh per-key lock: stale breaks, fresh survives
            (orch / "dispatch.lock").write_text(
                f"dead {minutes_ago(500)} S1", encoding="utf-8"
            )
            (orch / "locks").mkdir(exist_ok=True)
            (orch / "locks" / "S2.lock").write_text(
                f"live {minutes_ago(5)} S2", encoding="utf-8"
            )
            proc, data = run_watch(orch, "--mode", "janitor")
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(any("pruned" in a for a in data["actions"]))
            self.assertFalse((orch / "dispatch.lock").exists())
            self.assertTrue((orch / "locks" / "S2.lock").exists())
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            # an old verdict-dated line prunes; an undated resolved line
            # stays — undated could be seconds old, never evidence of age
            self.assertNotIn("- [x] S2", text)
            self.assertIn("- [x] S3", text)
            self.assertIn("- [ ] S1", text)

    def test_janitor_breaks_stale_per_key_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "locks").mkdir(exist_ok=True)
            (orch / "locks" / "S7.lock").write_text(
                f"dead {minutes_ago(500)} S7", encoding="utf-8"
            )
            proc, data = run_watch(orch, "--mode", "janitor")
            self.assertFalse((orch / "locks" / "S7.lock").exists())
            self.assertTrue(any("S7.lock" in a for a in data["actions"]))




class TestWatchResolve(unittest.TestCase):
    def test_intake_per_key_dedupe_and_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "signals").mkdir()
            (orch / "signals" / "line-stop-S3.md").write_text("LINE_STOP: loop A", encoding="utf-8")
            (orch / "signals" / "line-stop-S7.md").write_text("LINE_STOP: loop B", encoding="utf-8")
            proc, data = run_watch(orch, "--mode", "intake")
            # second line-stop for a DIFFERENT key must not be eaten
            self.assertEqual(len(data["consumed"]), 2)
            self.assertEqual(data["skipped_dupes"], [])
            # same key again → still a dupe
            (orch / "signals" / "line-stop-S3.md").write_text("LINE_STOP: loop A again", encoding="utf-8")
            proc, data = run_watch(orch, "--mode", "intake")
            self.assertIn("line-stop-S3.md", data["skipped_dupes"])
            # resolve S3 → a third S3 signal is fresh again
            proc, data = run_watch(orch, "--mode", "resolve", "--key", "S3")
            self.assertEqual(data["resolved"], ["line-stop"])
            (orch / "signals" / "line-stop-S3.md").write_text("LINE_STOP: loop A recurred", encoding="utf-8")
            proc, data = run_watch(orch, "--mode", "intake")
            self.assertIn("line-stop-S3.md", data["consumed"])
            # bodies archived, not destroyed
            self.assertTrue((orch / "signals" / "archive" / "line-stop-S7.md").exists())


if __name__ == "__main__":
    unittest.main()
