"""Tests for file-cards.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "file-cards.py"

CHECKLIST = """# Alignment Checklist

## Needs Attention

## Routine Review

## Confirmations & Sign-offs

## Requisitions

## Doctrine
"""


def run_file(orch: Path, cards, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        cpath = Path(tmp) / "cards.json"
        cpath.write_text(json.dumps(cards), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch),
             "--cards", str(cpath), *extra],
            capture_output=True, text=True,
        )
        return proc, json.loads(proc.stdout) if proc.stdout else None


def card(key, conf, flags=None, backlog="code"):
    # a complete-enough contract body: Execution Surface + a None-sentinel
    # Questions section, so routing isn't tripped by missing sections
    body = (f"# card {key}\n\n## Execution Surface\n\n"
            "- **Risk surface:** `none`\n\n"
            "## Questions for the Operator\n\nNone — recommend confirm.\n")
    return {"key": key, "title": f"Story {key}", "backlog": backlog,
            "confidence": conf, "flags": flags or [], "body": body}


class TestFileCards(unittest.TestCase):
    def make_orch(self, root: Path):
        orch = root / "docs" / "orchestration"
        (orch / "backlogs").mkdir(parents=True)
        (orch / "alignment-checklist.md").write_text(CHECKLIST, encoding="utf-8")
        (orch / "backlogs" / "code.md").write_text(
            "- [ ] S1 — first\n- [ ] S2 — second\n- [ ] S3 — third\n",
            encoding="utf-8",
        )
        return orch

    def test_files_by_confidence_and_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            proc, data = run_file(orch, [
                card("S1", 95), card("S2", 40, ["scope-fuzzy"]), card("S3", 70),
            ])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # S1 routine, S2 attention (flag), S3 attention (conf<80)
            self.assertEqual(data["routine"], ["S1"])
            self.assertEqual(set(data["needs_attention"]), {"S2", "S3"})
            # draft files written
            for k in ("S1", "S2", "S3"):
                self.assertTrue((orch / "alignment" / "drafts" / f"{k}.md").is_file())
            # checklist lines contain link
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("S2 — Story S2 | conf 40% | flags: scope-fuzzy", text)

    def test_sorted_ascending_within_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            run_file(orch, [card("S3", 70)])
            run_file(orch, [card("S2", 40, ["x"])])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            s2_pos = text.index("conf 40%")
            s3_pos = text.index("conf 70%")
            self.assertLess(s2_pos, s3_pos)

    def test_idempotent_refile_replaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            run_file(orch, [card("S1", 95)])
            run_file(orch, [card("S1", 60, ["revised"])])  # re-draft lower conf
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertEqual(text.count("S1 — Story S1"), 1)
            self.assertIn("conf 60%", text)

    def test_asks_routes_to_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 95)
            c["asks"] = 2
            c["body"] = (c["body"] + "\n- q1? — recommended: a\n"
                         "- q2? — recommended: b\n")
            # body bullets must live in the Questions section — append won't
            # do; rebuild it inline
            c["body"] = ("# card\n## Questions for the Operator\n\n"
                         "- q1? — recommended: a\n- q2? — recommended: b\n\n"
                         "## Execution Surface\n\n- **Risk surface:** `none`\n")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # questions for the Operator are never Routine Review, even at 95%
            self.assertIn("S1", data["needs_attention"])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| asks: 2", text)

    def test_wireframe_url_on_checklist_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 90)
            c["wireframe"] = "https://wiretext.app/w/abc12345"
            run_file(orch, [c])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| wire: https://wiretext.app/w/abc12345", text)

    def test_wireframe_recovered_from_card_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 90)
            c["body"] = "# card\n## Visual Preview\n\n- **Wireframe:** https://wiretext.app/w/xyz987\n"
            run_file(orch, [c])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| wire: https://wiretext.app/w/xyz987", text)

    def test_no_wireframe_no_wire_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            run_file(orch, [card("S1", 90)])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertNotIn("| wire:", text)

    def test_wireframe_url_outside_preview_not_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 90)
            c["body"] = ("# card\n## Questions for the Operator\n\n"
                         "- reuse https://wiretext.app/w/old123 ?\n")
            run_file(orch, [c])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertNotIn("| wire:", text)

    def test_malformed_wireframe_field_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 90)
            c["wireframe"] = "see figma"
            proc, data = run_file(orch, [c])
            self.assertIn("warnings", data)
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertNotIn("see figma", text)

    def test_declared_risk_surface_routes_to_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 95)
            c["body"] = ("# card\n## Execution Surface\n\n"
                         "- **Risk surface:** `schema-migration`\n")
            proc, data = run_file(orch, [c])
            # declared risk surface is an Operator-eyeball item even at 95% unflagged
            self.assertIn("S1", data["needs_attention"])

    def test_unknown_risk_token_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 95)
            c["body"] = ("# card\n## Execution Surface\n\n"
                         "- **Risk surface:** `schema_migration`\n")
            proc, data = run_file(orch, [c])
            self.assertIn("warnings", data)
            # an unknown token isn't a declaration — no Needs Attention bump
            self.assertIn("S1", data["routine"])

    def test_attention_tokens_route_to_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            for key, tok in zip(("S1", "S2", "S3"),
                                ("env-changed", "api-contract", "data-backfill")):
                c = card(key, 95)
                c["body"] = (f"# card\n## Execution Surface\n\n"
                             f"- **Risk surface:** `{tok}`\n")
                proc, data = run_file(orch, [c])
                self.assertIn(key, data["needs_attention"], tok)
                self.assertNotIn("warnings", data, tok)

    def test_snapshot_on_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            run_file(orch, [card("S1", 95)])
            old = "# card S1 v1"
            c = card("S1", 60, ["revised"])
            c["body"] = "# card S1 v2"
            # seed the draft with a distinct old body, then refile
            draft = orch / "alignment" / "drafts" / "S1.md"
            draft.write_text(old, encoding="utf-8")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            snaps = list((orch / "alignment" / "superseded").glob("S1.*.md"))
            self.assertEqual(len(snaps), 1)
            self.assertEqual(snaps[0].read_text(encoding="utf-8"), old)
            self.assertEqual(draft.read_text(encoding="utf-8"), "# card S1 v2")

    def test_refile_supersedes_parked_card(self):
        """A fresh draft for a key whose card sits parked must not leave
        two live cards — the parked one snapshots to superseded/."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            parked = orch / "alignment" / "parked"
            parked.mkdir(parents=True)
            (parked / "S1.md").write_text("# parked card\n", encoding="utf-8")
            proc, data = run_file(orch, [card("S1", 90)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((parked / "S1.md").exists())
            snaps = list((orch / "alignment" / "superseded")
                         .glob("S1.*.parked.md"))
            self.assertEqual(len(snaps), 1)
            self.assertTrue(
                (orch / "alignment" / "drafts" / "S1.md").is_file())

    def test_no_snapshot_when_body_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            run_file(orch, [card("S1", 95)])
            run_file(orch, [card("S1", 95)])  # identical refile
            self.assertFalse((orch / "alignment" / "superseded").exists())

    def test_frontmatter_surface_mismatch_routes_to_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 95)
            c["body"] = ("---\ndeclared_surface: [deps-changed]\n---\n"
                         "# card\n## Execution Surface\n\n"
                         "- **Risk surface:** `schema-migration`\n")
            proc, data = run_file(orch, [c])
            self.assertIn("S1", data["needs_attention"])
            self.assertTrue(any("contract drift" in w
                                for w in data["warnings"]))

    def test_missing_execution_surface_warns_and_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 95)
            c["body"] = "# card S1 — no sections at all\n"
            proc, data = run_file(orch, [c])
            self.assertIn("S1", data["needs_attention"])
            self.assertTrue(any("Execution Surface" in w
                                for w in data["warnings"]))

    def test_asks_derived_not_supplied(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            c = card("S1", 95)
            c["asks"] = 0  # lies — the body holds two real questions
            c["body"] = ("# card\n## Questions for the Operator\n\n"
                         "- q1? — recommended: a\n- q2? — recommended: b\n")
            proc, data = run_file(orch, [c])
            self.assertIn("S1", data["needs_attention"])
            self.assertTrue(any("derived count" in w for w in data["warnings"]))
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| asks: 2", text)

    def test_validation_names_the_bad_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            bad = card("S1", 95)
            bad["confidence"] = "95%"  # string with % — classic LLM slip
            proc, data = run_file(orch, [bad, card("S2", 90)])
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("S1" in e and "confidence" in e
                                for e in data["errors"]))
            # validation is all-or-nothing — S2 must not have been filed
            self.assertFalse(
                (orch / "alignment" / "drafts" / "S2.md").exists())

    def test_duplicate_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            proc, data = run_file(orch, [card("S1", 95), card("S1", 60)])
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("duplicate" in e for e in data["errors"]))

    def test_filename_hostile_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            proc, data = run_file(orch, [card("../evil", 95)])
            self.assertEqual(proc.returncode, 1)

    def test_undraftable_flips_to_question_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            payload = {"cards": [card("S1", 90)],
                       "undraftable": [{"key": "S2", "backlog": "code",
                                        "reason": "no legible intent"}]}
            proc, data = run_file(orch, payload)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            backlog = (orch / "backlogs" / "code.md").read_text(encoding="utf-8")
            self.assertIn("- [?] S2", backlog)
            self.assertEqual(data["undraftable"][0]["reason"],
                             "no legible intent")

    def test_question_marker_flips_to_aligned_on_filing(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            b = orch / "backlogs" / "code.md"
            b.write_text(b.read_text(encoding="utf-8").replace(
                "- [ ] S2", "- [?] S2"), encoding="utf-8")
            proc, data = run_file(orch, [card("S2", 90)])
            self.assertIn("- [A] S2", b.read_text(encoding="utf-8"))

    def test_gaps_and_last_run_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            payload = {"cards": [card("S1", 90)],
                       "gaps": ["no card covers the registration gap"]}
            proc, data = run_file(orch, payload)
            self.assertIn("registration gap",
                          (orch / "alignment" / "gap-findings.md")
                          .read_text(encoding="utf-8"))
            last = json.loads((orch / "alignment" / "last-run.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(last["filed"], ["S1"])

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            proc, data = run_file(orch, [card("S1", 90)], ["--dry-run"])
            self.assertTrue(data["dry_run"])
            self.assertFalse((orch / "alignment" / "drafts").exists())
            self.assertIn("- [ ] S1",
                          (orch / "backlogs" / "code.md")
                          .read_text(encoding="utf-8"))

    def test_backlog_marker_flips(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            run_file(orch, [card("S1", 90)])
            backlog = (orch / "backlogs" / "code.md").read_text(encoding="utf-8")
            self.assertIn("- [A] S1", backlog)
            self.assertIn("- [ ] S2", backlog)


if __name__ == "__main__":
    unittest.main()
