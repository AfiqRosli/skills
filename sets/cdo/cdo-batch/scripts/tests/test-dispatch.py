"""Tests for dispatch.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / "dispatch.py"


def run_dispatch(orch: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), *args],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_orch(root: Path, confirmed=()):
    orch = root / "docs" / "orchestration"
    (orch / "alignment" / "2026" / "10" / "14").mkdir(parents=True)
    (orch / "backlogs").mkdir(parents=True)
    (orch / "flow-ledger.yaml").write_text(
        "batch: {id: b1, manifest: [S1, S2]}\n"
        "pool:\n  confirmed: [%s]\n  quarantined: []\n"
        "stories: {}\n" % ", ".join(confirmed),
        encoding="utf-8",
    )
    (orch / "backlogs" / "code.md").write_text("- [x] S1\n- [A] S2\n", encoding="utf-8")
    for k in confirmed:
        (orch / "alignment" / "2026" / "10" / "14" / f"{k}.md").write_text(
            f"# Card {k}\n- **Confidence:** 96%\n\n## Externals Needed\n\n- `STRIPE_KEY` — payments\n",
            encoding="utf-8",
        )
    return orch



class TestOutcomeTransitions(unittest.TestCase):
    """13-26 — machine-gated outcome transitions."""

    def _claim(self, orch, key="S1"):
        run_dispatch(orch, "claim", key, "--session", "s-1")

    def test_happy_chain_done_verified_shipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            self._claim(orch)
            for st in ("done", "verified", "shipped"):
                proc, data = run_dispatch(orch, "outcome", "S1", "--status", st)
                self.assertEqual(proc.returncode, 0, st)
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["stories"]["S1"]["status"], "shipped")

    def test_skip_legs_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            self._claim(orch)
            proc, data = run_dispatch(orch, "outcome", "S1", "--status", "shipped")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("illegal outcome transition", data["errors"][0])
            proc, _ = run_dispatch(orch, "outcome", "S1", "--status", "verified")
            self.assertEqual(proc.returncode, 1)
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["stories"]["S1"]["status"], "in-flight")

    def test_force_override_journals(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            self._claim(orch)
            proc, _ = run_dispatch(
                orch, "outcome", "S1", "--status", "shipped",
                "--force", "--reason", "manual repair",
            )
            self.assertEqual(proc.returncode, 0)
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertTrue(any("FORCE-OVERRIDE" in f for f in ledger["stories"]["S1"]["findings"]))

    def test_escape_hatches_from_in_flight_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            # blocked on an unclaimed story refuses
            proc, _ = run_dispatch(orch, "outcome", "S1", "--status", "blocked", "--reason", "x")
            self.assertEqual(proc.returncode, 1)
            self._claim(orch)
            proc, _ = run_dispatch(orch, "outcome", "S1", "--status", "deferred", "--reason", "later")
            self.assertEqual(proc.returncode, 0)


class TestDispatch(unittest.TestCase):
    def test_check_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            (Path(tmp) / ".env").write_text("STRIPE_KEY=x\n", encoding="utf-8")
            proc, data = run_dispatch(orch, "check", "S1", "--env-file", str(Path(tmp) / ".env"))
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(data["ready"])

    def test_check_missing_env_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            (Path(tmp) / ".env").write_text("", encoding="utf-8")
            proc, data = run_dispatch(orch, "check", "S1", "--env-file", str(Path(tmp) / ".env"))
            self.assertFalse(data["ready"])
            self.assertEqual(data["missing_env"], ["STRIPE_KEY"])

    def test_check_unconfirmed_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            proc, data = run_dispatch(orch, "check", "S9")
            self.assertFalse(data["ready"])
            self.assertTrue(any("pool.confirmed" in r for r in data["reasons"]))

    def test_claim_moves_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            proc, data = run_dispatch(orch, "claim", "S1", "--session", "s-1", "--step", "dev")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["stories"]["S1"]["status"], "in-flight")
            self.assertNotIn("S1", ledger["pool"]["confirmed"])
            self.assertTrue((orch / "locks" / "S1.lock").is_file())

    def test_parallel_claims_allowed(self):
        # the whole point of per-key locks: two sessions, two stories, both run
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"])
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            proc, _ = run_dispatch(orch, "claim", "S2", "--session", "s-2")
            self.assertEqual(proc.returncode, 0)
            self.assertTrue((orch / "locks" / "S1.lock").is_file())
            self.assertTrue((orch / "locks" / "S2.lock").is_file())

    def test_check_survives_malformed_lock_ts(self):
        # a lock file with a garbage timestamp must produce a reason,
        # not a runtime crash on the age format
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            (Path(tmp) / ".env").write_text("STRIPE_KEY=x\n", encoding="utf-8")
            locks = orch / "locks"
            locks.mkdir()
            (locks / "S1.lock").write_text("s-9 garbage\n", encoding="utf-8")
            proc, data = run_dispatch(orch, "check", "S1",
                                      "--env-file", str(Path(tmp) / ".env"))
            self.assertEqual(proc.returncode, 1)
            self.assertFalse(data["ready"])
            self.assertTrue(any("lock" in r for r in data["reasons"]))

    def test_heartbeat_refreshes_legacy_lock_in_place(self):
        # a story claimed on the legacy dispatch.lock keeps that file
        # fresh — heartbeat must not mint a second locks/{key}.lock
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            (orch / "dispatch.lock").write_text(
                "s-old 2020-01-01T00:00 S1\n", encoding="utf-8")
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            ledger["stories"]["S1"] = {"status": "in-flight", "session": "s-old"}
            (orch / "flow-ledger.yaml").write_text(
                yaml.safe_dump(ledger), encoding="utf-8")
            proc, _ = run_dispatch(orch, "heartbeat", "S1",
                                   "--session", "s-old")
            self.assertEqual(proc.returncode, 0)
            self.assertFalse((orch / "locks" / "S1.lock").exists())
            self.assertIn("S1", (orch / "dispatch.lock").read_text())

    def test_release_removes_all_locks_for_key(self):
        # if a legacy lock AND a per-key lock both claim the same key,
        # release must clear both — a straggler would re-block dispatch
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            locks = orch / "locks"
            locks.mkdir()
            (locks / "S1.lock").write_text("s-1 2020-01-01T00:00 S1\n",
                                           encoding="utf-8")
            (orch / "dispatch.lock").write_text("s-1 2020-01-01T00:00 S1\n",
                                                encoding="utf-8")
            proc, _ = run_dispatch(orch, "release", "S1", "--force")
            self.assertEqual(proc.returncode, 0)
            self.assertFalse((locks / "S1.lock").exists())
            self.assertFalse((orch / "dispatch.lock").exists())

    def test_same_key_double_claim_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            proc, _ = run_dispatch(orch, "claim", "S1", "--session", "s-2")
            self.assertEqual(proc.returncode, 1)

    def test_one_story_per_session(self):
        # a session holding a fresh lock may not claim a second key
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"])
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            proc, data = run_dispatch(orch, "claim", "S2", "--session", "s-1")
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("one story per session" in e for e in data["errors"]))

    def test_stale_lock_breakable(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"])
            old = (datetime.now(timezone.utc) - timedelta(minutes=200)).strftime("%Y-%m-%dT%H:%M")
            (orch / "locks").mkdir(exist_ok=True)
            (orch / "locks" / "S1.lock").write_text(
                f"dead-session {old} S1", encoding="utf-8")
            # stale same-key lock doesn't block a reclaim
            proc, _ = run_dispatch(orch, "claim", "S1", "--session", "s-2")
            self.assertEqual(proc.returncode, 0)

    def test_legacy_dispatch_lock_honored(self):
        # a fresh pre-parallel dispatch.lock still blocks its embedded key only
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"])
            fresh = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            (orch / "dispatch.lock").write_text(f"s-1 {fresh} S1", encoding="utf-8")
            proc, _ = run_dispatch(orch, "claim", "S1", "--session", "s-2")
            self.assertEqual(proc.returncode, 1)
            proc, _ = run_dispatch(orch, "claim", "S2", "--session", "s-2")
            self.assertEqual(proc.returncode, 0)

    def test_claim_unconfirmed_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            proc, _ = run_dispatch(orch, "claim", "S7")
            self.assertEqual(proc.returncode, 1)

    def test_outcome_blocked_quarantines(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            proc, data = run_dispatch(
                orch, "outcome", "S1", "--status", "blocked", "--reason", "needs STRIPE_KEY",
            )
            self.assertEqual(proc.returncode, 0)
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["stories"]["S1"]["status"], "blocked")
            self.assertEqual(ledger["pool"]["quarantined"][0]["reason"], "needs STRIPE_KEY")

    def test_quarantine_flips_backlog(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S2"])
            proc, _ = run_dispatch(orch, "quarantine", "S2", "--reason", "conflict with S1")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("[-] S2 — conflict", (orch / "backlogs" / "code.md").read_text(encoding="utf-8"))

    def test_release_deletes_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            # session-less release is refused — the holder must name itself
            proc, _ = run_dispatch(orch, "release", "S1")
            self.assertEqual(proc.returncode, 1)
            self.assertTrue((orch / "locks" / "S1.lock").exists())
            proc, _ = run_dispatch(orch, "release", "S1", "--session", "s-1")
            self.assertEqual(proc.returncode, 0)
            self.assertFalse((orch / "locks" / "S1.lock").exists())

    def test_release_other_session_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            proc, _ = run_dispatch(orch, "release", "S1", "--session", "s-2")
            self.assertEqual(proc.returncode, 1)
            self.assertTrue((orch / "locks" / "S1.lock").exists())
            proc, _ = run_dispatch(orch, "release", "S1", "--session", "s-2", "--force")
            self.assertFalse((orch / "locks" / "S1.lock").exists())

    def test_release_only_touches_own_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1", "S2"])
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            run_dispatch(orch, "claim", "S2", "--session", "s-2")
            run_dispatch(orch, "release", "S1", "--session", "s-1")
            self.assertFalse((orch / "locks" / "S1.lock").exists())
            self.assertTrue((orch / "locks" / "S2.lock").exists())

    def test_heartbeat_refreshes_and_requires_inflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            proc, _ = run_dispatch(orch, "heartbeat", "S1")
            self.assertEqual(proc.returncode, 1)  # not in-flight
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            import time
            time.sleep(1)
            proc, data = run_dispatch(orch, "heartbeat", "S1", "--step", "qa")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["stories"]["S1"]["step"], "qa")

    def test_outcome_flips_backlog_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            run_dispatch(orch, "outcome", "S1", "--status", "blocked", "--reason", "stuck")
            backlog = (orch / "backlogs" / "code.md").read_text(encoding="utf-8")
            self.assertIn("[-] S1", backlog)

    def test_check_draft_is_not_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S2"])
            # remove the archived card — S2 only has a DRAFT now
            (orch / "alignment" / "2026" / "10" / "14" / "S2.md").unlink()
            (orch / "alignment" / "drafts").mkdir(parents=True)
            (orch / "alignment" / "drafts" / "S2.md").write_text("# draft", encoding="utf-8")
            proc, data = run_dispatch(orch, "check", "S2")
            self.assertFalse(data["ready"])
            self.assertTrue(any("alignment" in r for r in data["reasons"]))



    def test_reconfirm_restores_quarantined_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=[])
            run_dispatch(orch, "quarantine", "S5", "--reason", "stalled")
            proc, data = run_dispatch(orch, "reconfirm", "S5",
                                      "--reason", "repaired: flaky test fixed")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            import yaml
            l = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertIn("S5", l["pool"]["confirmed"])
            self.assertEqual(l["stories"]["S5"]["status"], "queued")
            self.assertEqual(l["pool"]["quarantined"], [])

    def test_outcome_burn_and_shipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), confirmed=["S1"])
            run_dispatch(orch, "claim", "S1", "--session", "s-1")
            run_dispatch(orch, "outcome", "S1", "--status", "done")
            run_dispatch(orch, "outcome", "S1", "--status", "verified")
            proc, data = run_dispatch(orch, "outcome", "S1", "--status", "shipped",
                                      "--burn", "2.5")
            self.assertEqual(proc.returncode, 0)
            import yaml
            l = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(l["stories"]["S1"]["status"], "shipped")
            self.assertEqual(l["cost"]["burned"], 2.5)


if __name__ == "__main__":
    unittest.main()
