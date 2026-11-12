"""Tests for ready-set.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / "ready-set.py"


def run_rs(orch: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), *args],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def minutes_ago(n):
    return (datetime.now(timezone.utc) - timedelta(minutes=n)).strftime("%Y-%m-%dT%H:%M")


def make_orch(root: Path, confirmed=(), stories=None, backlog_text=""):
    orch = root / "docs" / "orchestration"
    (orch / "alignment" / "2026" / "10" / "14").mkdir(parents=True)
    (orch / "backlogs").mkdir(parents=True)
    st = ""
    if stories:
        st = "stories:\n" + "".join(
            f"  {k}: {{status: {v}}}\n" for k, v in stories.items())
    (orch / "flow-ledger.yaml").write_text(
        "batch: {id: b1}\n"
        "pool:\n  confirmed: [%s]\n  quarantined: []\n%s"
        % (", ".join(confirmed), st or "stories: {}\n"),
        encoding="utf-8",
    )
    (orch / "backlogs" / "code.md").write_text(backlog_text, encoding="utf-8")
    for k in confirmed:
        (orch / "alignment" / "2026" / "10" / "14" / f"{k}.md").write_text(
            f"# Card {k}\n- **Confidence:** 90%\n\n## Externals Needed\n\n- none\n",
            encoding="utf-8",
        )
    return orch


class TestReadySet(unittest.TestCase):
    def test_all_independent_dispatch_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2", "S3"], backlog_text=(
                "- [x] S1 — a | touches: app/one\n"
                "- [x] S2 — b | touches: app/two\n"
                "- [x] S3 — c | touches: app/three\n"
            ))
            proc, data = run_rs(orch)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["dispatch_now"], ["S1", "S2", "S3"])

    def test_spawn_plan_solo_keys_are_own_sessions(self):
        """13-45 — independent keys each get a solo session in the plan."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2", "S3"], backlog_text=(
                "- [x] S1 — a | deps: none\n"
                "- [x] S2 — b | deps: none\n"
                "- [x] S3 — c | deps: none\n"
            ))
            proc, data = run_rs(orch)
            self.assertEqual(data["spawn_plan"], [
                {"keys": ["S1"], "mode": "solo"},
                {"keys": ["S2"], "mode": "solo"},
                {"keys": ["S3"], "mode": "solo"},
            ])

    def test_spawn_plan_dep_chain_is_one_linear_group(self):
        """13-45 — dep-connected keys form ONE linear group, topo order."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2", "S3"], backlog_text=(
                "- [x] S1 — a | deps: none\n"
                "- [x] S2 — b | deps: S1\n"
                "- [x] S3 — c | deps: S2\n"
            ))
            proc, data = run_rs(orch)
            self.assertEqual(data["spawn_plan"], [
                {"keys": ["S1", "S2", "S3"], "mode": "linear"},
            ])

    def test_spawn_plan_mixed_groups(self):
        """13-45 — a chain plus an independent key: two groups, chain first
        (pool order of the group's first member)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2", "S3"], backlog_text=(
                "- [x] S1 — a | deps: none\n"
                "- [x] S2 — b | deps: S1\n"
                "- [x] S3 — c | deps: none\n"
            ))
            proc, data = run_rs(orch)
            self.assertEqual(data["spawn_plan"], [
                {"keys": ["S1", "S2"], "mode": "linear"},
                {"keys": ["S3"], "mode": "solo"},
            ])

    def test_rejected_card_never_dispatches(self):
        """A rejected card is archived (audit) but carries `<!-- reject` —
        it must not authorize dispatch even if the key is still pooled."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"], backlog_text=(
                "- [x] S1 — a | touches: app/one\n"))
            card = orch / "alignment" / "2026" / "10" / "14" / "S1.md"
            card.write_text("<!-- reject 2026-10-14 08:00 UTC — no -->\n\n"
                            + card.read_text(encoding="utf-8"),
                            encoding="utf-8")
            proc, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], [])
            self.assertIn("S1", data["waiting"])

    def test_dep_in_flight_reports_as_in_flight(self):
        """A dep that is claimed/in-flight must read as such — not
        'never finished' which implies the dep was never aligned."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S2"],
                             stories={"S1": "in-flight"}, backlog_text=(
                "- [x] S2 — b | touches: app/two | deps: S1\n"))
            proc, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], [])
            self.assertTrue(any("in-flight" in r
                                for r in data["waiting"]["S2"]))

    def test_dep_orders_dependent_first(self):
        """An in-pool dep is an ordering edge, not a blocker — the drain
        list runs the dep first."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"], backlog_text=(
                "- [x] S1 — a | touches: app/one\n"
                "- [x] S2 — b | deps: S1 | touches: app/two\n"
            ))
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], ["S1", "S2"])
            self.assertNotIn("S2", data["waiting"])

    def test_dep_chain_orders_transitively(self):
        """S1<-S2<-S3 — one list, dep-first ordered, no parallel split."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S3", "S1", "S2"],
                             backlog_text=(
                "- [x] S1 — a | touches: app/one\n"
                "- [x] S2 — b | deps: S1 | touches: app/two\n"
                "- [x] S3 — c | deps: S2 | touches: app/three\n"
            ))
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], ["S1", "S2", "S3"])

    def test_dep_pooled_but_undispatchable_blocks(self):
        """Dep in the candidate set but failing its own checks → the
        dependent waits — it can't ride a drain that isn't going."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"],
                             stories={"S1": "in-flight"}, backlog_text=(
                "- [x] S1 — a | touches: app/one\n"
                "- [x] S2 — b | deps: S1 | touches: app/two\n"
            ))
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], [])
            self.assertTrue(any("dep S1" in r for r in data["waiting"]["S2"]))

    def test_dep_satisfied_when_shipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(
                Path(tmp), confirmed=["S2"], stories={"S1": "shipped"},
                backlog_text=(
                    "- [x] S1 — a | touches: app/one\n"
                    "- [x] S2 — b | deps: S1 | touches: app/two\n"
                ))
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], ["S2"])

    def test_dep_done_only_when_finished(self):
        # dep in pool but not shipped → blocks; dep quarantined → blocks
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"], backlog_text=(
                "- [x] S1 — a | touches: app/one\n"
                "- [x] S2 — b | deps: S1 | touches: app/two\n"
            ))
            _, data = run_rs(orch, "--keys", "S2")
            self.assertEqual(data["dispatch_now"], [])

    def test_touches_overlap_is_advisory(self):
        """Overlapping touches don't split or gate — dispatch is linear;
        touches is blast-radius context for reviewers, not a concurrency key."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"], backlog_text=(
                "- [x] S1 — a | touches: components/Waitlist, nuxt.config.ts\n"
                "- [x] S2 — b | touches: components, server/api.ts\n"
            ))
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], ["S1", "S2"])
            self.assertNotIn("S2", data["waiting"])

    def test_independent_keys_share_one_list(self):
        """Unlinked keys land in the same ordered list — the drain handles
        them serially, no per-group sessions."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2", "S3"],
                             backlog_text=(
                "- [x] S1 — a | touches: app/one\n"
                "- [x] S2 — b | deps: S1 | touches: app/two\n"
                "- [x] S3 — c | touches: app/three\n"
            ))
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], ["S1", "S2", "S3"])

    def test_drain_lock_holds_every_key(self):
        """locks/g-*.lock marks all comma-listed keys held — the drain
        session owns them until it exits or the lock ages out."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"],
                             backlog_text=(
                "- [x] S1 — a | touches: app/one\n"
                "- [x] S2 — b | touches: app/two\n"
            ))
            (orch / "locks").mkdir()
            (orch / "locks" / "g-s1-1.lock").write_text(
                f"w-drain-1 {minutes_ago(3)} S1,S2", encoding="utf-8")
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], [])
            self.assertTrue(any("lock" in r for r in data["waiting"]["S1"]))
            self.assertTrue(any("lock" in r for r in data["waiting"]["S2"]))

    def test_drain_lock_survives_story_stall_window(self):
        """A g-lock at 3h is still fresh — a cloud drain can't heartbeat,
        so it ages against a 24h horizon, not the story stall window."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"],
                             backlog_text="- [x] S1 — a | touches: app/one\n")
            (orch / "locks").mkdir()
            (orch / "locks" / "g-s1-1.lock").write_text(
                f"w-drain-1 {minutes_ago(180)} S1", encoding="utf-8")
            _, data = run_rs(orch)
            self.assertIn("S1", data["waiting"])
            (orch / "locks" / "g-s1-1.lock").write_text(
                f"w-drain-1 {minutes_ago(60*25)} S1", encoding="utf-8")
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], ["S1"])

    def test_single_candidate_no_touches_ok(self):
        # one story can't collide with itself — touches unproven doesn't matter
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"],
                             backlog_text="- [x] S1 — a\n")
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], ["S1"])

    def test_missing_touches_is_advisory(self):
        """No touches: field doesn't gate — dispatch is sequential, so an
        undescribed blast radius can't collide with a sibling."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"], backlog_text=(
                "- [x] S1 — a | touches: app/one\n"
                "- [x] S2 — b\n"
            ))
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], ["S1", "S2"])

    def test_in_flight_and_locked_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"],
                             stories={"S1": "in-flight"}, backlog_text=(
                                 "- [x] S1 — a | touches: app/one\n"
                                 "- [x] S2 — b | touches: app/two\n"
                             ))
            (orch / "locks").mkdir()
            (orch / "locks" / "S2.lock").write_text(
                f"w-S2 {minutes_ago(3)} S2", encoding="utf-8")
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], [])
            self.assertTrue(any("in-flight" in r for r in data["waiting"]["S1"]))
            self.assertTrue(any("lock" in r for r in data["waiting"]["S2"]))

    def test_stale_lock_does_not_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"],
                             backlog_text="- [x] S1 — a | touches: app/one\n")
            (orch / "locks").mkdir()
            (orch / "locks" / "S1.lock").write_text(
                f"dead {minutes_ago(300)} S1", encoding="utf-8")
            _, data = run_rs(orch)
            self.assertEqual(data["dispatch_now"], ["S1"])

    def test_dep_edge_only_when_dep_is_a_candidate(self):
        """--keys scoping: a dep that's pooled but outside the candidate
        set blocks (it isn't shipping in this dispatch either)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"], backlog_text=(
                "- [x] S1 — a | touches: app/one\n"
                "- [x] S2 — b | deps: S1 | touches: app/two\n"
            ))
            _, data = run_rs(orch, "--keys", "S2")
            self.assertEqual(data["dispatch_now"], [])
            self.assertTrue(any("dep S1" in r for r in data["waiting"]["S2"]))


if __name__ == "__main__":
    unittest.main()
