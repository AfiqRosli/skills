"""Tests for delivery-note.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / "delivery-note.py"


def run_dn(orch: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), *args],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_orch(root: Path, stories=None, checklist_sections=("## Delivered",)):
    orch = root / "docs" / "orchestration"
    (orch / "alignment" / "2026" / "10" / "14").mkdir(parents=True)
    (orch / "backlogs").mkdir(parents=True)
    (orch / "sessions").mkdir()
    rows = ""
    if stories:
        for k, v in stories.items():
            if isinstance(v, dict):
                inner = ", ".join(f"{kk}: {vv}" for kk, vv in v.items())
                rows += f"  {k}: {{{inner}}}\n"
            else:
                rows += f"  {k}: {{status: {v}}}\n"
    (orch / "flow-ledger.yaml").write_text(
        "batch: {id: b1}\n"
        "pool:\n  confirmed: []\n  quarantined: []\n"
        + ("stories:\n" + rows if rows else "stories: {}\n"),
        encoding="utf-8")
    (orch / "alignment-checklist.md").write_text(
        "# Checklist\n\n## Needs Attention\n\n## Routine Review\n\n"
        + "\n\n".join(checklist_sections) + "\n\n## Escalations\n",
        encoding="utf-8")
    for k in stories or {}:
        (orch / "alignment" / "2026" / "10" / "14" / f"{k}.md").write_text(
            f"<!-- confirm 2026-10-14 -->\n\n# Card {k}\n- **Confidence:** 90%\n",
            encoding="utf-8")
    return orch


def write_review_doc(orch: Path, key: str, attempt: int = 1) -> Path:
    doc = orch / "alignment" / "2026" / "10" / "14" / f"{key}.review-{attempt}.md"
    doc.write_text(f"# Review {key} attempt {attempt}\n\n## Evidence walked\n"
                   "- card, ledger, diff\n", encoding="utf-8")
    return doc


def write_staged_review(orch: Path, key: str, attempt: int = 1) -> Path:
    """The canonical Operator-pending path — alignment/reviews/ staging."""
    d = orch / "alignment" / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    doc = d / f"{key}.review-{attempt}.md"
    doc.write_text(f"# Review {key} attempt {attempt}\n\n## Evidence walked\n"
                   "- card, ledger, diff\n", encoding="utf-8")
    return doc


class TestDeliveryNote(unittest.TestCase):
    def test_pending_lists_terminal_unbriefed(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={
                "S1": "shipped", "S2": "in-flight", "S3": "done",
                "S4": "blocked", "S5": "killed"})
            proc, data = run_dn(orch, "pending")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            keys = {p["key"] for p in data["pending"]}
            # shipped + blocked + killed are reviewable; done/in-flight aren't
            self.assertEqual(keys, {"S1", "S4", "S5"})
            s1 = next(p for p in data["pending"] if p["key"] == "S1")
            self.assertEqual(s1["session_report"], "sessions/S1.md")
            self.assertIn("alignment/", s1["card"])
            self.assertIn("S1.review-1.md", s1["review_doc"])

    def test_file_requires_doc_first(self):
        """The checklist line must point at reasoning — no doc, no filing."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            proc, data = run_dn(orch, "file", "S1", "--verdict", "sound",
                                "--note", "no doc written")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("doc missing", data["reason"])
            # now write the doc → files clean
            write_review_doc(orch, "S1")
            proc, data = run_dn(orch, "file", "S1", "--verdict", "sound",
                                "--note", "doc-backed now")
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_file_writes_line_stamp_and_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            write_review_doc(orch, "S1")
            proc, data = run_dn(orch, "file", "S1", "--verdict", "sound",
                                "--note", "matches card")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["section"], "## Delivered")
            checklist = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertIn("- [ ] S1 — matches card", checklist)
            self.assertIn("review: alignment/2026/10/14/S1.review-1.md",
                          checklist)
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            dv = ledger["stories"]["S1"]["delivery_review"]
            self.assertEqual(dv["verdict"], "sound")
            self.assertEqual(dv["attempt"], 1)

    def test_file_keeps_staged_doc_pending(self):
        """reviews/ is the Operator-pending staging dir — filing does NOT
        move the doc; the line and ledger stamp point at the staged path,
        and apply-decisions graduates it on the Operator's verdict."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            staged = write_staged_review(orch, "S1")
            proc, data = run_dn(orch, "file", "S1", "--verdict", "sound",
                                "--note", "staged read")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(staged.is_file())  # still staged
            self.assertFalse(
                (orch / "alignment" / "2026" / "10" / "14"
                 / "S1.review-1.md").exists())
            self.assertEqual(data["doc"],
                             "alignment/reviews/S1.review-1.md")
            self.assertNotIn("moved", data)
            self.assertIn(
                "review: alignment/reviews/S1.review-1.md",
                (orch / "alignment-checklist.md").read_text(
                    encoding="utf-8"))
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(
                ledger["stories"]["S1"]["delivery_review"]["doc"],
                "alignment/reviews/S1.review-1.md")

    def test_file_accepts_beside_card_doc_in_place(self):
        """A doc already beside the card (legacy/hand-filed) files where it
        sits — the dated archive is already its final home."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            write_review_doc(orch, "S1")  # beside card, not staged
            proc, data = run_dn(orch, "file", "S1", "--verdict", "sound",
                                "--note", "already final")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["doc"],
                             "alignment/2026/10/14/S1.review-1.md")

    def test_file_external_doc_refused_not_relocated(self):
        """--doc outside the orchestration dir is refused BEFORE any move —
        a refused filing must never relocate files into the archive."""
        with tempfile.TemporaryDirectory() as tmp, \
                tempfile.TemporaryDirectory() as outside:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            ext = Path(outside) / "review.md"
            ext.write_text("# outside review\n", encoding="utf-8")
            proc, data = run_dn(orch, "file", "S1", "--verdict", "sound",
                                "--note", "x", "--doc", str(ext))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("orchestration dir", data["reason"])
            self.assertTrue(ext.is_file())  # untouched
            self.assertFalse(list(
                (orch / "alignment" / "2026").glob("**/S1.review-1.md")))

    def test_failed_story_lands_under_escalations(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S9": "blocked"})
            write_review_doc(orch, "S9")
            proc, data = run_dn(orch, "file", "S9",
                                "--verdict", "postmortem:hollow",
                                "--note", "died claiming env missing, .env fine")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["section"], "## Escalations")
            checklist = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            esc_idx = checklist.index("## Escalations")
            self.assertIn("- [ ] S9 —", checklist[esc_idx:])

    def test_versioned_rereview_on_new_attempt(self):
        """Attempt-1 reviewed, story re-shipped at attempt 2 → pending again,
        files review-2.md, stamp advances."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={
                "S1": {"status": "shipped", "attempts": 2}})
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            ledger["stories"]["S1"]["delivery_review"] = {
                "verdict": "flagged:x", "attempt": 1, "at": "2026-10-14"}
            (orch / "flow-ledger.yaml").write_text(
                yaml.safe_dump(ledger), encoding="utf-8")
            _, data = run_dn(orch, "pending")
            self.assertIn("S1.review-2.md",
                          next(p["review_doc"] for p in data["pending"]))
            write_review_doc(orch, "S1", attempt=2)
            proc, data = run_dn(orch, "file", "S1", "--verdict", "sound",
                                "--note", "fixed attempt")
            self.assertEqual(proc.returncode, 0)
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(
                ledger["stories"]["S1"]["delivery_review"]["attempt"], 2)

    def test_file_dedupes_same_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            write_review_doc(orch, "S1")
            run_dn(orch, "file", "S1", "--verdict", "sound", "--note", "ok")
            proc, data = run_dn(orch, "file", "S1", "--verdict",
                                "flagged:x", "--note", "again")
            self.assertEqual(proc.returncode, 1)
            checklist = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertEqual(checklist.count("- [ ] S1"), 1)

    def test_pending_skips_key_already_on_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"},
                             checklist_sections=(
                                 "## Delivered\n\n- [ ] S1 — old line",))
            _, data = run_dn(orch, "pending")
            self.assertEqual(data["pending"], [])

    def test_pending_excludes_live_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            (orch / "sessions" / "S1.review.json").write_text(json.dumps(
                {"key": "S1", "kind": "review", "session_name": "r-S1-x",
                 "started": "2999-01-01T00:00"}), encoding="utf-8")
            _, data = run_dn(orch, "pending")
            self.assertEqual(data["pending"], [])

    def test_spawn_review_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            proc, data = run_dn(orch, "spawn-review", "S1", "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["kind"], "review")
            self.assertIn("r-S1", data["spawn"]["session_name"])
            self.assertIn(".review.prompt.md", data["spawn"]["prompt_file"])

    def test_spawn_review_refuses_when_in_flight(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            (orch / "sessions" / "S1.review.json").write_text(json.dumps(
                {"key": "S1", "started": "2999-01-01T00:00"}), encoding="utf-8")
            proc, data = run_dn(orch, "spawn-review", "S1", "--dry-run")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("in-flight", data["reason"])

    def test_spawn_review_refuses_reviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            write_review_doc(orch, "S1")
            run_dn(orch, "file", "S1", "--verdict", "sound", "--note", "ok")
            proc, _ = run_dn(orch, "spawn-review", "S1", "--dry-run")
            self.assertEqual(proc.returncode, 1)

    def test_file_wave_stamps_batch_and_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            wave_doc = orch / "alignment" / "2026" / "10" / "14" / "wave-b1.md"
            wave_doc.write_text("# Wave b1\n", encoding="utf-8")
            proc, data = run_dn(orch, "file-wave", "--batch", "b1",
                                "--doc", str(wave_doc),
                                "--note", "wave coherent, one cross-miss")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            checklist = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertIn("- [ ] wave-b1", checklist)
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["batch"]["wave_review"]["doc"],
                             "alignment/2026/10/14/wave-b1.md")
            # second filing refuses
            proc, _ = run_dn(orch, "file-wave", "--batch", "b1",
                             "--doc", str(wave_doc), "--note", "again")
            self.assertEqual(proc.returncode, 1)

    def test_file_wave_keeps_staged_doc_pending(self):
        """Wave docs share the reviews/ staging convention — filing points
        the line at the staged doc; the Operator's verdict lands it in the
        dated archive."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={"S1": "shipped"})
            staging = orch / "alignment" / "reviews"
            staging.mkdir(parents=True, exist_ok=True)
            wave_doc = staging / "wave-b1.md"
            wave_doc.write_text("# Wave b1\n", encoding="utf-8")
            proc, data = run_dn(orch, "file-wave", "--batch", "b1",
                                "--note", "wave coherent")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["doc"], "alignment/reviews/wave-b1.md")
            self.assertTrue(wave_doc.exists())  # still staged
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["batch"]["wave_review"]["doc"],
                             "alignment/reviews/wave-b1.md")

    def test_pending_extract_carries_delivered_state(self):
        """The manual extraction surface separates Operator-confirmed
        work from still-awaiting-review work."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), stories={
                "S1": "shipped",
                "S2": {"status": "shipped",
                       "delivery_review": {"attempt": 1,
                                           "verdict": "sound"}},
                "S3": {"status": "shipped",
                       "delivery_review": {"attempt": 1,
                                           "verdict": "sound"},
                       "pre_deploy": {"marked_at": "2026-11-04T10:00"}},
                "S4": {"status": "shipped",
                       "extract": {"attempt": 1}},
                "S5": "done"})
            proc, data = run_dn(orch, "pending-extract")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            by_key = {p["key"]: p for p in data["pending_extract"]}
            self.assertEqual(set(by_key), {"S1", "S2", "S3"})
            self.assertEqual(by_key["S1"]["delivered"], "awaiting-review")
            self.assertIsNone(by_key["S1"]["review_verdict"])
            self.assertEqual(by_key["S2"]["delivered"], "review-filed")
            self.assertEqual(by_key["S2"]["review_verdict"], "sound")
            self.assertEqual(by_key["S3"]["delivered"], "confirmed")
            # extracted + non-shipped stories stay off the list
            self.assertNotIn("S4", by_key)
            self.assertNotIn("S5", by_key)


if __name__ == "__main__":
    unittest.main()
