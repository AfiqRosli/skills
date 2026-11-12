"""Tests for apply-decisions.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml  # PEP 723 dep is present in the test env via the script's env

SCRIPT = Path(__file__).parent.parent / "apply-decisions.py"


def make_orch(root: Path):
    orch = root / "docs" / "orchestration"
    (orch / "alignment" / "drafts").mkdir(parents=True)
    (orch / "backlogs").mkdir(parents=True)
    (orch / "flow-ledger.yaml").write_text(
        "pool:\n  confirmed: []\n  quarantined: []\n"
        "autonomy:\n  enabled: false\n  streak: 3\n  threshold: 10\n",
        encoding="utf-8",
    )
    (orch / "doctrine.md").write_text(
        "# Doctrine\n\n## Standing Policies\n\n## Decision Log\n\n<!-- comment -->\n\n",
        encoding="utf-8",
    )
    (orch / "alignment-checklist.md").write_text(
        "## Needs Attention\n\n- [ ] S1 — Story one | conf 60% | draft: x\n\n"
        "## Routine Review\n\n- [ ] S2 — Story two | conf 97% | draft: x\n",
        encoding="utf-8",
    )
    (orch / "backlogs" / "code.md").write_text(
        "- [A] S1\n- [A] S2\n", encoding="utf-8"
    )
    for key, conf in (("S1", 60), ("S2", 97)):
        (orch / "alignment" / "drafts" / f"{key}.md").write_text(
            f"# Alignment Card — {key}\n- **Source:** `backlogs/code.md`\n"
            f"- **Confidence:** {conf}%\n", encoding="utf-8"
        )
    return orch


def run_apply(orch: Path, decisions):
    with tempfile.TemporaryDirectory() as tmp:
        dpath = Path(tmp) / "d.json"
        dpath.write_text(json.dumps(decisions), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch),
             "--decisions", str(dpath)],
            capture_output=True, text=True,
        )
        return proc, json.loads(proc.stdout) if proc.stdout else None


def run_apply_raw(orch: Path, raw: str):
    """Write `raw` verbatim as the decisions file — exercises every parser
    surface (JSON array, JSONL, single-line JSONL, bare object)."""
    with tempfile.TemporaryDirectory() as tmp:
        dpath = Path(tmp) / "d.jsonl"
        dpath.write_text(raw, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch),
             "--decisions", str(dpath)],
            capture_output=True, text=True,
        )
        return proc, json.loads(proc.stdout) if proc.stdout else None


class TestApplyDecisions(unittest.TestCase):
    def test_confirm_high_conf_increments_streak(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply(orch, [{"key": "S2", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["autonomy"]["streak"], 4)  # 3 + 1
            self.assertIn("S2", data["confirmed_pool"])
            self.assertIn("S2", data["newly_confirmed"])
            # archived + checklist checked
            archived = list((orch / "alignment").glob("**/S2.md"))
            self.assertEqual(len(archived), 1)
            self.assertIn("[x] S2", (orch / "alignment-checklist.md").read_text())
            self.assertIn("- [x] S2", (orch / "backlogs" / "code.md").read_text())

    def test_confirm_flips_sprint_proposed_to_backlog(self):
        """A key shaped into the current sprint yaml at `proposed` flips to
        `backlog` on confirm — Operator confirmation is what makes a shaped
        story real sprint work."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            impl = Path(tmp) / "_bmad-output" / "implementation-artifacts"
            impl.mkdir(parents=True)
            yml = impl / "sprint-status-Beta-2026.10.11.yaml"
            yml.write_text(
                "development_status:\n"
                "  epic-13: in-progress\n"
                "  13-19-older-story: done\n"
                "  S2: proposed  # NEW — shaped at intake\n"
                "  epic-13-retrospective: optional\n",
                encoding="utf-8")
            proc, data = run_apply(orch, [{"key": "S2", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = yml.read_text(encoding="utf-8")
            self.assertIn("S2: backlog", text)
            self.assertNotIn("S2: proposed", text)
            applied = next(a for a in data["applied"] if a["key"] == "S2")
            self.assertIn("proposed→backlog", applied.get("sprint_status", ""))

    def test_confirm_without_sprint_entry_still_works(self):
        """Non-code keys (CT1, C2) have no sprint yaml line — the flip is a
        no-op, not a failure."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply(orch, [{"key": "S2", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("S2", data["newly_confirmed"])

    def test_confirm_low_conf_no_increment(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply(orch, [{"key": "S1", "verdict": "confirm"}])
            self.assertEqual(data["autonomy"]["streak"], 3)  # unchanged — conf 60 < 95

    def test_confirm_edited_resets_and_journals(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply(orch, [{
                "key": "S2", "verdict": "confirm-edited",
                "note": "scope dropped mobile", "lesson": "always responsive-only",
            }])
            self.assertEqual(data["autonomy"]["streak"], 0)
            doctrine = (orch / "doctrine.md").read_text(encoding="utf-8")
            self.assertIn("approved-with-edits", doctrine)
            self.assertIn("responsive-only", doctrine)

    def test_reject_quarantines_and_resets(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply(orch, [{
                "key": "S1", "verdict": "reject", "note": "not this quarter",
            }])
            self.assertEqual(data["autonomy"]["streak"], 0)
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text())
            self.assertEqual(ledger["pool"]["quarantined"][0]["key"], "S1")
            self.assertIn("[-] S1", (orch / "backlogs" / "code.md").read_text())

    def test_reject_unpools_already_confirmed_key(self):
        """A key confirmed earlier sits in pool.confirmed; if its re-drafted
        card is then rejected, the reject must strip the pool entry — with
        auto-dispatch, a pooled reject would fire rejected work."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text())
            ledger["pool"]["confirmed"].append("S1")  # previously confirmed
            (orch / "flow-ledger.yaml").write_text(
                yaml.safe_dump(ledger), encoding="utf-8")
            proc, data = run_apply(orch, [{
                "key": "S1", "verdict": "reject", "note": "scope changed",
            }])
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text())
            self.assertNotIn("S1", ledger["pool"]["confirmed"])
            self.assertIn("S1", [q["key"] for q in ledger["pool"]["quarantined"]])

    def test_rejected_card_does_not_authorize_dispatch(self):
        """The archived card carries `<!-- reject` — downstream gates
        (dispatch.py check, ready-set.py) must not count it as confirmed."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_apply(orch, [{"key": "S1", "verdict": "reject",
                              "note": "no"}])
            archived = list((orch / "alignment").glob("**/S1.md"))
            self.assertEqual(len(archived), 1)
            head = archived[0].read_text(encoding="utf-8")[:200]
            self.assertIn("<!-- reject", head)

    def test_reject_delivered_files_rollback_escalation(self):
        """Rejecting a `## Delivered` item must leave an OPEN escalation —
        inserting it before checklist_apply would mark the fresh line
        resolved in the same pass (ordering regression test)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            ledger.setdefault("stories", {})["S9"] = {
                "status": "shipped",
                "delivery_review": {"verdict": "sound", "at": "2026-10-15"},
            }
            (orch / "flow-ledger.yaml").write_text(
                yaml.safe_dump(ledger), encoding="utf-8")
            cl = orch / "alignment-checklist.md"
            cl.write_text(cl.read_text() +
                          "\n## Delivered\n\n- [ ] S9 — shipped, verdict sound\n",
                          encoding="utf-8")
            proc, data = run_apply(orch, [{
                "key": "S9", "verdict": "reject", "note": "wrong approach",
            }])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            checklist = cl.read_text(encoding="utf-8")
            self.assertIn("- [x] S9 — shipped", checklist)  # delivered resolved
            self.assertIn("- [ ] S9 — delivered work rejected", checklist)
            self.assertTrue(any("rollback" in a.get("escalated", "")
                                for a in data["applied"]))

    def test_reject_card_flagged_files_reshape_escalation(self):
        """flagged:card-* means the alignment was wrong, not the delivery —
        an Operator reject escalates reshape/re-align, not rollback."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            ledger.setdefault("stories", {})["S8"] = {
                "status": "shipped",
                "delivery_review": {"verdict": "flagged:card-scope",
                                    "attempt": 1, "at": "2026-10-15"},
            }
            (orch / "flow-ledger.yaml").write_text(
                yaml.safe_dump(ledger), encoding="utf-8")
            cl = orch / "alignment-checklist.md"
            cl.write_text(cl.read_text() +
                          "\n## Delivered\n\n- [ ] S8 — shipped clean but card was wrong\n",
                          encoding="utf-8")
            proc, data = run_apply(orch, [{
                "key": "S8", "verdict": "reject", "note": "shouldn't exist",
            }])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            checklist = cl.read_text(encoding="utf-8")
            self.assertIn("- [ ] S8 — card judged wrong", checklist)
            self.assertIn("reshape", checklist)
            self.assertNotIn("rollback via", checklist.split("S8 —")[1])

    def test_reject_delivered_without_review_files_triage(self):
        """A shipped story whose review stamp is missing still must escalate —
        no delivery_review verdict to steer reshape/rollback, so a generic
        triage escalation files instead of nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            ledger.setdefault("stories", {})["S7"] = {"status": "shipped"}
            (orch / "flow-ledger.yaml").write_text(
                yaml.safe_dump(ledger), encoding="utf-8")
            cl = orch / "alignment-checklist.md"
            cl.write_text(cl.read_text() +
                          "\n## Delivered\n\n- [ ] S7 — shipped\n",
                          encoding="utf-8")
            proc, data = run_apply(orch, [{
                "key": "S7", "verdict": "reject", "note": "wrong work",
            }])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            applied = next(a for a in data["applied"] if a["key"] == "S7")
            self.assertEqual(applied["escalated"], "triage")
            self.assertIn("review record missing",
                          (cl.read_text(encoding="utf-8")))

    def test_missing_doctrine_is_scaffolded(self):
        """No doctrine.md → corrections scaffold the file and still journal,
        with a warning — never silently dropped."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "doctrine.md").unlink()
            proc, data = run_apply(orch, [{
                "key": "S1", "verdict": "reject", "note": "wrong scope",
            }])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doctrine = (orch / "doctrine.md")
            self.assertTrue(doctrine.is_file())
            self.assertIn("rejected", doctrine.read_text(encoding="utf-8"))
            applied = next(a for a in data["applied"] if a["key"] == "S1")
            self.assertTrue(applied.get("journaled"))
            self.assertIn("scaffolded", applied.get("warning", ""))

    def test_jsonl_staging_and_consume(self):
        """Staged verdicts (one JSON object per line) apply like the array
        form; --consume removes the staging file on full success."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            staged = orch / "pending-decisions.jsonl"
            staged.write_text(
                json.dumps({"key": "S2", "verdict": "confirm"}) + "\n"
                + json.dumps({"key": "S1", "verdict": "defer"}) + "\n",
                encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch),
                 "--decisions", str(staged), "--consume"],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertIn("S2", data["newly_confirmed"])
            self.assertFalse(staged.exists())

    def test_defer_parks_card_and_resolves_line(self):
        """defer = 'looked at, not now' — the card leaves drafts/ for
        alignment/parked/ and the checklist line resolves; the backlog
        marker stays [A] (still alignment-pending, dormant)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply(orch, [{
                "key": "S1", "verdict": "defer", "note": "not this week",
            }])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            parked = orch / "alignment" / "parked" / "S1.md"
            self.assertTrue(parked.is_file())
            self.assertFalse(
                (orch / "alignment" / "drafts" / "S1.md").exists())
            self.assertIn("<!-- deferred",
                          parked.read_text(encoding="utf-8"))
            cl = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("- [x] S1", cl)
            self.assertIn("deferred", cl)
            self.assertIn(
                "- [A] S1",
                (orch / "backlogs" / "code.md").read_text(encoding="utf-8"))
            applied = next(a for a in data["applied"] if a["key"] == "S1")
            self.assertIn("parked", applied)

    def test_defer_non_card_stays_pending(self):
        """No parked concept for non-card items — defer stays a no-op."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            cl = orch / "alignment-checklist.md"
            cl.write_text(cl.read_text(encoding="utf-8") +
                          "\n## Escalations\n\n- [ ] S9 — fix it\n",
                          encoding="utf-8")
            proc, _ = run_apply(orch, [{"key": "S9", "verdict": "defer"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("- [ ] S9 — fix it",
                          cl.read_text(encoding="utf-8"))
            self.assertFalse(
                (orch / "alignment" / "parked" / "S9.md").exists())

    def test_resurface_revives_parked_card(self):
        """resurface = revive as-is — the parked card returns to drafts/
        and a re-pended checklist line lands where the deferred one sits."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_apply(orch, [{"key": "S1", "verdict": "defer"}])
            proc, data = run_apply(orch,
                                   [{"key": "S1", "verdict": "resurface"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(
                (orch / "alignment" / "drafts" / "S1.md").is_file())
            self.assertFalse(
                (orch / "alignment" / "parked" / "S1.md").exists())
            cl = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("- [ ] S1 — Story one", cl)
            self.assertIn("resurfaced", cl)
            # the deferred line stays resolved — history, not a rewrite
            self.assertIn("- [x] S1", cl)

    def test_resurface_without_parked_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply(orch,
                                   [{"key": "S1", "verdict": "resurface"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            applied = next(a for a in data["applied"] if a["key"] == "S1")
            self.assertIn("no parked card", applied.get("warning", ""))

    def test_resurface_live_draft_supersedes_parked(self):
        """A live draft outranks the parked copy — resurface snapshots the
        parked card to superseded/ instead of overwriting the draft."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_apply(orch, [{"key": "S1", "verdict": "defer"}])
            draft = orch / "alignment" / "drafts" / "S1.md"
            draft.write_text("# fresh draft v2\n", encoding="utf-8")
            proc, data = run_apply(orch,
                                   [{"key": "S1", "verdict": "resurface"}])
            self.assertEqual(draft.read_text(encoding="utf-8"),
                             "# fresh draft v2\n")
            snaps = list(
                (orch / "alignment" / "superseded").glob("S1.*.md"))
            self.assertEqual(len(snaps), 1)
            applied = next(a for a in data["applied"] if a["key"] == "S1")
            self.assertIn("superseded", applied.get("warning", ""))

    def test_parked_card_preserves_frontmatter(self):
        """The deferred stamp must land INSIDE the card — frontmatter on
        line 1, or grounded_against becomes unparseable and the resurface
        staleness warning is dead code."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "alignment" / "drafts" / "S1.md").write_text(
                "---\ngrounded_against:\n  commit: abc12345dead\n"
                "  drafted: 2026-10-20\n---\n\n"
                "# Alignment Card — S1\n- **Confidence:** 60%\n",
                encoding="utf-8")
            run_apply(orch, [{"key": "S1", "verdict": "defer"}])
            parked = (orch / "alignment" / "parked" / "S1.md").read_text(
                encoding="utf-8")
            self.assertTrue(parked.startswith("---\n"),
                            "frontmatter must stay on line 1")
            self.assertIn("<!-- deferred", parked)

    def test_resurface_no_duplicate_pending_with_live_draft(self):
        """A live draft already owns a pending line — resurface must not
        add a second one when the parked card goes to superseded/."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_apply(orch, [{"key": "S1", "verdict": "defer"}])
            (orch / "alignment" / "drafts" / "S1.md").write_text(
                "# fresh draft v2\n", encoding="utf-8")
            cl = orch / "alignment-checklist.md"
            cl.write_text(cl.read_text(encoding="utf-8") +
                          "\n- [ ] S1 — fresh draft | conf 80%\n",
                          encoding="utf-8")
            run_apply(orch, [{"key": "S1", "verdict": "resurface"}])
            text = cl.read_text(encoding="utf-8")
            self.assertEqual(text.count("- [ ] S1"), 1)

    def test_defer_only_resolves_card_sections(self):
        """A same-key Delivered line is a different item — defer must
        never sweep it to '→ deferred'."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            cl = orch / "alignment-checklist.md"
            cl.write_text(cl.read_text(encoding="utf-8") +
                          "\n## Delivered\n\n- [ ] S1 — shipped\n",
                          encoding="utf-8")
            run_apply(orch, [{"key": "S1", "verdict": "defer"}])
            text = cl.read_text(encoding="utf-8")
            self.assertIn("- [x] S1 — Story one", text)  # card line resolved
            self.assertIn("- [ ] S1 — shipped", text)   # delivered intact
            self.assertNotIn("shipped → deferred", text)

    def test_card_verdict_on_parked_key_warns(self):
        """confirm can't land on a parked card — archive/pool/sprint
        branches would all skip while zombies remained. Refuse loudly."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_apply(orch, [{"key": "S1", "verdict": "defer"}])
            proc, data = run_apply(orch, [{"key": "S1", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            applied = next(a for a in data["applied"] if a["key"] == "S1")
            self.assertIn("parked", applied.get("warning", ""))
            self.assertNotIn("S1", data["newly_confirmed"])
            self.assertTrue(
                (orch / "alignment" / "parked" / "S1.md").is_file())
            self.assertFalse(
                list((orch / "alignment").glob("2026/**/S1.md")))

    def test_repend_lands_after_section_comment(self):
        """Re-pends belong at the top of the ITEM list — not above the
        section's own <!-- --> blurb."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            cl = orch / "alignment-checklist.md"
            cl.write_text(
                cl.read_text(encoding="utf-8").replace(
                    "## Needs Attention\n\n",
                    "## Needs Attention\n\n<!-- flagged items -->\n\n"),
                encoding="utf-8")
            run_apply(orch, [{"key": "S1", "verdict": "defer"}])
            run_apply(orch, [{"key": "S1", "verdict": "resurface"}])
            text = cl.read_text(encoding="utf-8")
            self.assertLess(text.index("<!-- flagged items -->"),
                            text.index("| resurfaced"))

    def test_unpark_supersedes_and_reopens_backlog(self):
        """unpark = the rethink path — parked card → superseded/, backlog
        [A]→[ ] so the next align run redrafts against current code."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_apply(orch, [{"key": "S1", "verdict": "defer"}])
            proc, data = run_apply(orch,
                                   [{"key": "S1", "verdict": "unpark"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(
                (orch / "alignment" / "parked" / "S1.md").exists())
            snaps = list(
                (orch / "alignment" / "superseded").glob("S1.*.md"))
            self.assertEqual(len(snaps), 1)
            self.assertIn(
                "- [ ] S1",
                (orch / "backlogs" / "code.md").read_text(encoding="utf-8"))
            applied = next(a for a in data["applied"] if a["key"] == "S1")
            self.assertIn("[A]→[ ]", applied.get("backlog", ""))

    def _ship_story(self, orch: Path, key: str, **story):
        """Ledger surgery: a shipped story with a lane sha — the state the
        pre-deploy gate reads."""
        ledger = yaml.safe_load(
            (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
        st = {"status": "shipped", "lane_sha": "a1b2c3d4"}
        st.update(story)
        ledger.setdefault("stories", {})[key] = st
        (orch / "flow-ledger.yaml").write_text(
            yaml.safe_dump(ledger), encoding="utf-8")

    def _delivered_item(self, orch: Path, key: str):
        cl = orch / "alignment-checklist.md"
        cl.write_text(cl.read_text(encoding="utf-8") +
                      f"\n## Delivered\n\n- [ ] {key} — shipped\n",
                      encoding="utf-8")
        return cl

    def _predeploy_item(self, orch: Path, key: str):
        cl = orch / "alignment-checklist.md"
        cl.write_text(cl.read_text(encoding="utf-8") +
                      f"\n## Pre-deploy Sign-offs\n\n"
                      f"- [ ] {key} — push to origin/preview\n",
                      encoding="utf-8")
        return cl

    def test_delivered_confirm_marks_pre_deploy(self):
        """Accepting a Delivered item queues the push sign-off — the
        Operator's second gate before origin sees anything."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            self._ship_story(orch, "S9")
            cl = self._delivered_item(orch, "S9")
            proc, data = run_apply(orch, [{"key": "S9", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            checklist = cl.read_text(encoding="utf-8")
            self.assertIn("## Pre-deploy Sign-offs", checklist)
            self.assertIn("- [ ] S9 — push to origin/preview", checklist)
            self.assertIn("a1b2c3d4", checklist)
            self.assertIn("- [x] S9 — shipped", checklist)
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            pd = ledger["stories"]["S9"]["pre_deploy"]
            self.assertTrue(pd.get("marked_at"))
            self.assertEqual(pd.get("sha"), "a1b2c3d4")
            applied = next(a for a in data["applied"] if a["key"] == "S9")
            self.assertTrue(applied.get("pre_deploy_marked"))
            # marking is not signing — nothing is pushable yet
            self.assertEqual(data["push_approved"], [])

    def test_predeploy_confirm_signs_and_approves_push(self):
        """A Pre-deploy Sign-offs confirm stamps signed_at and lands the
        key in push_approved — the push leg's only authorization."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            self._ship_story(orch, "S9",
                             pre_deploy={"marked_at": "2026-10-18 10:00"})
            cl = self._predeploy_item(orch, "S9")
            proc, data = run_apply(orch, [{"key": "S9", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("S9", data["push_approved"])
            self.assertIn("- [x] S9 — push to origin/preview",
                          cl.read_text(encoding="utf-8"))
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertTrue(
                ledger["stories"]["S9"]["pre_deploy"].get("signed_at"))
            applied = next(a for a in data["applied"] if a["key"] == "S9")
            self.assertTrue(applied.get("pre_deploy_signed"))

    def test_predeploy_reject_stays_local_no_escalation(self):
        """Rejecting a pre-deploy item is 'don't push', not 'the work is
        wrong' — no rollback escalation, work stays on the local lane."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            self._ship_story(orch, "S9",
                             delivery_review={"verdict": "sound"},
                             pre_deploy={"marked_at": "2026-10-18 10:00"})
            cl = self._predeploy_item(orch, "S9")
            proc, data = run_apply(orch, [{
                "key": "S9", "verdict": "reject", "note": "not yet",
            }])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            pd = ledger["stories"]["S9"]["pre_deploy"]
            self.assertTrue(pd.get("rejected"))
            self.assertNotIn("signed_at", pd)
            self.assertEqual(data["push_approved"], [])
            applied = next(a for a in data["applied"] if a["key"] == "S9")
            self.assertTrue(applied.get("pre_deploy_rejected"))
            self.assertNotIn("escalated", applied)
            checklist = cl.read_text(encoding="utf-8")
            self.assertNotIn("delivered work rejected", checklist)
            self.assertNotIn("rollback via", checklist)

    def test_pushed_story_skips_marking(self):
        """Work already on origin (pushed.sha == lane_sha) doesn't
        re-queue for sign-off."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            self._ship_story(
                orch, "S9",
                pushed={"at": "2026-10-18", "sha": "a1b2c3d4"})
            cl = self._delivered_item(orch, "S9")
            proc, data = run_apply(orch, [{"key": "S9", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("push to origin",
                             cl.read_text(encoding="utf-8"))
            applied = next(a for a in data["applied"] if a["key"] == "S9")
            self.assertEqual(applied.get("pre_deploy_skipped"),
                             "already on origin")

    def test_reship_after_sign_remarks_new_sha(self):
        """A re-ship moves lane_sha past the signed mark — the stale ask
        is superseded and a fresh sign-off queues for the new sha."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            self._ship_story(
                orch, "S9", lane_sha="e5f6a7b8",
                pre_deploy={"marked_at": "2026-10-18 10:00",
                            "sha": "a1b2c3d4",
                            "signed_at": "2026-10-18 11:00"})
            cl = orch / "alignment-checklist.md"
            cl.write_text(
                cl.read_text(encoding="utf-8") +
                "\n## Delivered\n\n- [ ] S9 — reshipped\n"
                "\n## Pre-deploy Sign-offs\n\n"
                "- [ ] S9 — push to origin/preview | lane a1b2c3d4\n",
                encoding="utf-8")
            proc, data = run_apply(orch, [{"key": "S9", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            checklist = cl.read_text(encoding="utf-8")
            self.assertIn("superseded", checklist)
            self.assertIn("- [ ] S9 — push to origin/preview | lane e5f6a7b8",
                          checklist)
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            pd = ledger["stories"]["S9"]["pre_deploy"]
            self.assertEqual(pd.get("sha"), "e5f6a7b8")
            self.assertNotIn("signed_at", pd)  # new sha was never signed

    def _delivered_review(self, orch: Path, key: str, card_date="2026/10/20"):
        """A filed Delivered review: confirmed card in a dated dir, staged
        doc under alignment/reviews/, ledger stamp + checklist line both
        pointing at the staged path — the Operator-pending state."""
        card_dir = orch / "alignment" / Path(card_date)
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / f"{key}.md").write_text(
            f"<!-- confirm 2026-10-20 -->\n\n# Card {key}\n"
            "- **Confidence:** 90%\n", encoding="utf-8")
        rev_dir = orch / "alignment" / "reviews"
        rev_dir.mkdir(parents=True, exist_ok=True)
        staged = rev_dir / f"{key}.review-1.md"
        staged.write_text(f"# Review {key}\n", encoding="utf-8")
        rel = f"alignment/reviews/{key}.review-1.md"
        ledger = yaml.safe_load(
            (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
        st = {"status": "shipped",
              "delivery_review": {"verdict": "sound", "attempt": 1,
                                  "at": "2026-10-21", "doc": rel}}
        ledger.setdefault("stories", {})[key] = st
        (orch / "flow-ledger.yaml").write_text(
            yaml.safe_dump(ledger), encoding="utf-8")
        cl = orch / "alignment-checklist.md"
        cl.write_text(
            cl.read_text(encoding="utf-8") +
            f"\n## Delivered\n\n- [ ] {key} — shipped | verdict: sound"
            f" | review: {rel} | filed 2026-10-21\n", encoding="utf-8")
        return staged, rel, card_dir

    def test_delivered_confirm_graduates_review_doc(self):
        """Confirm on a Delivered line graduates the staged doc out of
        reviews/ beside the confirmed card — reviews/ reads as
        'shipped, awaiting Operator' only while the line is pending."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            staged, rel, card_dir = self._delivered_review(orch, "S9")
            proc, data = run_apply(orch, [{"key": "S9", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            final = card_dir / "S9.review-1.md"
            self.assertTrue(final.is_file())
            self.assertFalse(staged.exists())
            cl = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("review: alignment/2026/10/20/S9.review-1.md", cl)
            self.assertNotIn("review: alignment/reviews/", cl)
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(
                ledger["stories"]["S9"]["delivery_review"]["doc"],
                "alignment/2026/10/20/S9.review-1.md")
            applied = next(a for a in data["applied"] if a["key"] == "S9")
            self.assertIn("review_graduated", applied)

    def test_delivered_reject_also_graduates(self):
        """A reject verdict closes the review too — the doc is the
        escalation's evidence and joins the card the same way."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            staged, rel, card_dir = self._delivered_review(orch, "S9")
            proc, data = run_apply(orch, [{
                "key": "S9", "verdict": "reject", "note": "wrong work",
            }])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((card_dir / "S9.review-1.md").is_file())
            self.assertFalse(staged.exists())

    def test_wave_confirm_graduates_wave_doc(self):
        """Wave docs share the convention — a wave-* line's verdict lands
        the doc in today's dated archive and refreshes wave_review.doc."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            rev_dir = orch / "alignment" / "reviews"
            rev_dir.mkdir(parents=True, exist_ok=True)
            (rev_dir / "wave-b1.md").write_text("# Wave\n", encoding="utf-8")
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            ledger["batch"] = {
                "id": "b1",
                "wave_review": {"doc": "alignment/reviews/wave-b1.md"}}
            (orch / "flow-ledger.yaml").write_text(
                yaml.safe_dump(ledger), encoding="utf-8")
            cl = orch / "alignment-checklist.md"
            cl.write_text(
                cl.read_text(encoding="utf-8") +
                "\n## Delivered\n\n- [ ] wave-b1 — wave read"
                " | review: alignment/reviews/wave-b1.md | filed x\n",
                encoding="utf-8")
            proc, data = run_apply(orch, [{"key": "wave-b1",
                                           "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            moved = list((orch / "alignment").glob("20*/*/*/wave-b1.md"))
            self.assertEqual(len(moved), 1)
            self.assertFalse((rev_dir / "wave-b1.md").exists())
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertIn("alignment/20",
                        ledger["batch"]["wave_review"]["doc"])

    def test_delivered_no_card_graduates_to_today_warns(self):
        """A Delivered verdict with no confirmed card (hand-archived /
        legacy gap) still graduates the doc — today's dated dir, plus a
        warning naming the unpaired landing. The review queue must drain
        even when the contract is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            rev_dir = orch / "alignment" / "reviews"
            rev_dir.mkdir(parents=True, exist_ok=True)
            (rev_dir / "S9.review-1.md").write_text("# Review\n",
                                                  encoding="utf-8")
            rel = "alignment/reviews/S9.review-1.md"
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            ledger.setdefault("stories", {})["S9"] = {
                "status": "shipped",
                "delivery_review": {"verdict": "sound", "attempt": 1,
                                    "doc": rel}}
            (orch / "flow-ledger.yaml").write_text(
                yaml.safe_dump(ledger), encoding="utf-8")
            cl = orch / "alignment-checklist.md"
            cl.write_text(
                cl.read_text(encoding="utf-8") +
                f"\n## Delivered\n\n- [ ] S9 — shipped | review: {rel}\n",
                encoding="utf-8")
            proc, data = run_apply(orch, [{"key": "S9",
                                           "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            moved = list((orch / "alignment").glob("20*/*/*/S9.review-1.md"))
            self.assertEqual(len(moved), 1)
            self.assertFalse((rev_dir / "S9.review-1.md").exists())
            applied = next(a for a in data["applied"] if a["key"] == "S9")
            self.assertIn("no confirmed card",
                          applied.get("warning", ""))

    def test_pending_review_line_stays_staged(self):
        """A `| review:` line still pending keeps its doc staged — only a
        resolved line graduates (verdict is the graduation trigger)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            staged, rel, card_dir = self._delivered_review(orch, "S9")
            # verdict lands on a different key — S9's line stays pending
            proc, data = run_apply(orch, [{"key": "S2", "verdict": "confirm"}])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(staged.exists())
            self.assertFalse((card_dir / "S9.review-1.md").exists())

    def test_defer_leaves_ledger_untouched(self):
        """Defer parks the card but is no streak/quarantine event — the
        autonomy ledger is the part that stays untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply(orch, [{"key": "S1", "verdict": "defer"}])
            self.assertEqual(data["autonomy"]["streak"], 3)
            ledger = yaml.safe_load(
                (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertNotIn("S1", ledger["pool"]["confirmed"])
            self.assertNotIn("S1", [q.get("key") for q in
                                    ledger["pool"]["quarantined"]
                                    if isinstance(q, dict)])

    def test_bad_verdict_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, _ = run_apply(orch, [{"key": "S1", "verdict": "maybe"}])
            self.assertEqual(proc.returncode, 1)

    def test_nonstring_verdict_isolates_not_crashes(self):
        """A malformed verdict (unhashable/non-string) must isolate as an
        invalid line — `x not in {set}` on a list raises TypeError and
        would kill the entire verdict pass."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply(orch, [
                {"key": "S1", "verdict": ["confirm"]},
                {"key": "S2", "verdict": "confirm"},
            ])
            # rc 1 signals partial failure — but the valid verdict applied
            # and the malformed line isolated, no crash
            self.assertEqual(proc.returncode, 1)
            self.assertIn("S2", data["newly_confirmed"])
            self.assertEqual(len(data["invalid"]), 1)


class TestDecisionsFileFormats(unittest.TestCase):
    """The decisions-file parse path accepts JSON array, JSONL, and a
    single bare object — the one-line staging file is the common case
    after an interrupted review pass (13-32 regression: json.loads on
    one line returns a dict, iterating it crashed the verdict filter)."""

    def test_single_line_jsonl_applies(self):
        """One JSON object + trailing newline — the staging shape that
        crashed apply-decisions with 'str' object has no attribute 'get'."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            raw = json.dumps({"key": "S1", "verdict": "confirm"}) + "\n"
            proc, data = run_apply_raw(orch, raw)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("S1", data["newly_confirmed"])
            self.assertEqual(data["invalid"], [])

    def test_bare_object_applies(self):
        """A single JSON object with no array wrapper and no newline —
        same dict-wrap path as single-line JSONL."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            raw = json.dumps({"key": "S1", "verdict": "defer"})
            proc, data = run_apply_raw(orch, raw)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            applied = next(a for a in data["applied"] if a["key"] == "S1")
            self.assertEqual(applied["verdict"], "deferred")

    def test_multi_line_jsonl_still_applies(self):
        """Two objects, one per line — the JSONL fallback path is
        untouched by the dict-wrap."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            raw = (json.dumps({"key": "S2", "verdict": "confirm"}) + "\n"
                   + json.dumps({"key": "S1", "verdict": "defer"}) + "\n")
            proc, data = run_apply_raw(orch, raw)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("S2", data["newly_confirmed"])

    def test_json_array_still_applies(self):
        """The documented array form is unchanged."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            raw = json.dumps([{"key": "S1", "verdict": "defer"}])
            proc, data = run_apply_raw(orch, raw)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(data["invalid"], [])

    def test_mixed_file_isolates_invalid(self):
        """Partial-apply contract: a bad verdict in a multi-decision file
        isolates — the valid decision still applies, the bad one reports."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            raw = (json.dumps({"key": "S2", "verdict": "confirm"}) + "\n"
                   + json.dumps({"key": "S1", "verdict": "bogus"}) + "\n")
            proc, data = run_apply_raw(orch, raw)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("S2", data["newly_confirmed"])
            self.assertEqual([d["key"] for d in data["invalid"]], ["S1"])

    def test_scalar_file_isolates_as_invalid_not_crash(self):
        """A file that is valid JSON but not a decision object (null,
        a bare string) must not AttributeError — it lands in invalid."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_apply_raw(orch, "null\n")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(data["applied"], [])
            self.assertEqual(data["invalid"], [None])


if __name__ == "__main__":
    unittest.main()
