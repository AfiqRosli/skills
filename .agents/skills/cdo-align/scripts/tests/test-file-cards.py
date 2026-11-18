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

# Every ## section the template requires — filing validates presence and
# non-empty, so every fixture body carries the full set.
SECTIONS = {
    "Marshal's Read": "- position\n",
    "System Context": "- ctx\n",
    "Visual Preview": "- **Wireframe:** n/a — no UI surface\n"
                      "- **Mock:** n/a — no UI surface\n",
    "Questions for the Operator": "None — recommend confirm.\n",
    "Acceptance Criteria": "- [ ] ok\n",
    "Scope Boundary": "- **In:** scope\n",
    "Externals Needed": "- none\n",
    "Execution Surface": "- **Risk surface:** `none`\n",
    "Flags": "- none\n",
    "Doctrine Grounding": "- none\n",
}

# >=200 chars + a frame token, so mock fixtures don't trip the
# doesn't-look-like-HTML / no-environment-frame warnings on unrelated tests.
MOCK_HTML = ("<!-- phone:bare -->\n<html><body>" + "x" * 300
             + "</body></html>")


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


def card(key, conf, flags=None, backlog="code", sections=None, fm="",
         header="", risk=None, grounded="deadbeef"):
    """A contract-complete card. `sections` replaces a required section's
    content wholesale; `risk` sets the Execution Surface token and
    declared_surface together (the honest state — pass a divergent `fm`
    line for drift); `fm` appends raw frontmatter lines (later yaml keys
    win); `header` inserts lines after the title; `grounded=None` drops
    grounded_against entirely."""
    secs = dict(SECTIONS)
    if risk is not None:
        secs["Execution Surface"] = f"- **Risk surface:** `{risk}`\n"
    secs.update(sections or {})
    fm_lines = f"declared_surface: [{risk or 'none'}]"
    if grounded is not None:
        fm_lines += (f"\ngrounded_against: {{commit: "
                     f"{grounded!r}, drafted: 2026-01-01}}")
    if fm:
        fm_lines += "\n" + fm
    body = (f"---\n{fm_lines}\n---\n# card\n{header}\n"
            + "".join(f"## {k}\n\n{v}\n" for k, v in secs.items()))
    return {"key": key, "title": f"Story {key}", "backlog": backlog,
            "confidence": conf, "flags": flags or [], "body": body}


def make_orch(root: Path):
    orch = root / "docs" / "orchestration"
    (orch / "backlogs").mkdir(parents=True)
    (orch / "alignment-checklist.md").write_text(CHECKLIST, encoding="utf-8")
    (orch / "backlogs" / "code.md").write_text(
        "- [ ] S1 — first\n- [ ] S2 — second\n- [ ] S3 — third\n",
        encoding="utf-8",
    )
    return orch


def install_product(orch: Path):
    """Simulate the cdo-product dept — its SKILL.md is the existence
    check the co-sign gate reads (project_root falls back to orch)."""
    p = orch / ".agents" / "skills" / "cdo-product"
    p.mkdir(parents=True)
    (p / "SKILL.md").write_text("---\nname: cdo-product\n---\n",
                                encoding="utf-8")


class TestFileCards(unittest.TestCase):
    def test_files_by_confidence_and_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
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
            orch = make_orch(Path(tmp))
            run_file(orch, [card("S3", 70)])
            run_file(orch, [card("S2", 40, ["x"])])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            s2_pos = text.index("conf 40%")
            s3_pos = text.index("conf 70%")
            self.assertLess(s2_pos, s3_pos)

    def test_idempotent_refile_replaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_file(orch, [card("S1", 95)])
            run_file(orch, [card("S1", 60, ["revised"])])  # re-draft lower conf
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertEqual(text.count("S1 — Story S1"), 1)
            self.assertIn("conf 60%", text)

    def test_asks_routes_to_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95, sections={
                "Questions for the Operator":
                    "- q1? — recommended: a\n- q2? — recommended: b\n"})
            c["asks"] = 2
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # questions for the Operator are never Routine Review, even at 95%
            self.assertIn("S1", data["needs_attention"])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| asks: 2", text)

    def test_wireframe_url_on_checklist_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 90)
            c["wireframe"] = "https://wiretext.app/w/abc12345"
            c["mock"] = str(mock_src)  # a claimed wire needs its mock
            run_file(orch, [c])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| wire: https://wiretext.app/w/abc12345", text)

    def test_wireframe_recovered_from_card_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 90, sections={
                "Visual Preview":
                    "- **Wireframe:** https://wiretext.app/w/xyz987\n"
                    "- **Mock:** n/a — no UI surface\n"})
            c["mock"] = str(mock_src)  # a claimed wire needs its mock
            run_file(orch, [c])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| wire: https://wiretext.app/w/xyz987", text)

    def test_no_wireframe_no_wire_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_file(orch, [card("S1", 90)])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertNotIn("| wire:", text)

    def test_wireframe_url_outside_preview_not_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 90, sections={
                "Questions for the Operator":
                    "- reuse https://wiretext.app/w/old123 ?\n"})
            run_file(orch, [c])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertNotIn("| wire:", text)

    def test_malformed_wireframe_field_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 90)
            c["wireframe"] = "see figma"
            proc, data = run_file(orch, [c])
            self.assertIn("warnings", data)
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertNotIn("see figma", text)

    def test_declared_risk_surface_routes_to_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_file(orch, [card("S1", 95, risk="schema-migration")])
            # declared risk surface is an Operator-eyeball item even at 95% unflagged
            self.assertIn("S1", data["needs_attention"])

    def test_unknown_risk_token_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95, sections={
                "Execution Surface":
                    "- **Risk surface:** `schema_migration`\n"})
            proc, data = run_file(orch, [c])
            self.assertIn("warnings", data)
            # an unknown token isn't a declaration — no Needs Attention bump
            self.assertIn("S1", data["routine"])

    def test_attention_tokens_route_to_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            for key, tok in zip(("S1", "S2", "S3"),
                                ("env-changed", "api-contract", "data-backfill")):
                proc, data = run_file(orch, [card(key, 95, risk=tok)])
                self.assertIn(key, data["needs_attention"], tok)
                self.assertNotIn("warnings", data, tok)

    def test_snapshot_on_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_file(orch, [card("S1", 95)])
            old = "# card S1 v1"
            # seed the draft with a distinct old body, then refile
            draft = orch / "alignment" / "drafts" / "S1.md"
            draft.write_text(old, encoding="utf-8")
            c = card("S1", 60, ["revised"],
                     sections={"Marshal's Read": "- v2\n"})
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            snaps = list((orch / "alignment" / "superseded").glob("S1.*.md"))
            self.assertEqual(len(snaps), 1)
            self.assertEqual(snaps[0].read_text(encoding="utf-8"), old)
            self.assertIn("- v2", draft.read_text(encoding="utf-8"))

    def test_refile_supersedes_parked_card(self):
        """A fresh draft for a key whose card sits parked must not leave
        two live cards — the parked one snapshots to superseded/."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
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
            orch = make_orch(Path(tmp))
            run_file(orch, [card("S1", 95)])
            run_file(orch, [card("S1", 95)])  # identical refile
            self.assertFalse((orch / "alignment" / "superseded").exists())

    def test_frontmatter_surface_mismatch_routes_to_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95, risk="schema-migration",
                     fm="declared_surface: [deps-changed]")
            proc, data = run_file(orch, [c])
            self.assertIn("S1", data["needs_attention"])
            self.assertTrue(any("contract drift" in w
                                for w in data["warnings"]))

    def test_missing_required_section_is_batch_error(self):
        """A section-less card isn't draftable — the template's section
        list is the completeness contract, enforced at validation."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95)
            c["body"] = c["body"].replace(
                "## Execution Surface\n\n- **Risk surface:** `none`\n\n",
                "")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("S1" in e and "Execution Surface" in e
                                for e in data["errors"]))
            # batch-wide: the section-less card blocks everything
            self.assertFalse(
                (orch / "alignment" / "drafts").exists())

    def test_grounded_commit_empty_routes_to_attention(self):
        """grounded_against.commit `''` goes dark to staleness detection —
        a contract break, not a free pass."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95, grounded="")
            proc, data = run_file(orch, [c])
            self.assertIn("S1", data["needs_attention"])
            self.assertTrue(any("grounded_against.commit" in w
                                for w in data["warnings"]))

    def test_asks_derived_not_supplied(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95, sections={
                "Questions for the Operator":
                    "- q1? — recommended: a\n- q2? — recommended: b\n"})
            c["asks"] = 0  # lies — the body holds two real questions
            proc, data = run_file(orch, [c])
            self.assertIn("S1", data["needs_attention"])
            self.assertTrue(any("derived count" in w for w in data["warnings"]))
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| asks: 2", text)

    def test_none_prefixed_question_counts(self):
        """The `None —` sentinel is a shape, not a first word — a real
        question starting 'None of the …' still counts as an ask."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95, sections={
                "Questions for the Operator":
                    "- None of the existing endpoints cover X — "
                    "recommend: build new\n"})
            proc, data = run_file(orch, [c])
            self.assertIn("S1", data["needs_attention"])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| asks: 1", text)

    def test_validation_names_the_bad_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
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
            orch = make_orch(Path(tmp))
            proc, data = run_file(orch, [card("S1", 95), card("S1", 60)])
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("duplicate" in e for e in data["errors"]))

    def test_filename_hostile_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_file(orch, [card("../evil", 95)])
            self.assertEqual(proc.returncode, 1)

    def test_undraftable_flips_to_question_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
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
            orch = make_orch(Path(tmp))
            b = orch / "backlogs" / "code.md"
            b.write_text(b.read_text(encoding="utf-8").replace(
                "- [ ] S2", "- [?] S2"), encoding="utf-8")
            proc, data = run_file(orch, [card("S2", 90)])
            self.assertIn("- [A] S2", b.read_text(encoding="utf-8"))

    def test_gaps_and_last_run_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            payload = {"cards": [card("S1", 90)],
                       "gaps": ["no card covers the registration gap"]}
            proc, data = run_file(orch, payload)
            self.assertIn("registration gap",
                          (orch / "alignment" / "gap-findings.md")
                          .read_text(encoding="utf-8"))
            last = json.loads((orch / "alignment" / "last-run.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(last["filed"], ["S1"])
            # advisory next-leg pointer — filed cards mean a checklist to review
            self.assertEqual(data["suggest"], "cdo-review")
            self.assertEqual(last["suggest"], "cdo-review")

    def test_receipt_carries_counts(self):
        """stdout + last-run.json emit the count split — a caller or
        report shouldn't recount the lists."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_file(orch, [
                card("S1", 95), card("S2", 40, ["x"])])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["filed_count"], 2)
            self.assertEqual(data["attention_count"], 1)
            self.assertEqual(data["routine_count"], 1)
            last = json.loads((orch / "alignment" / "last-run.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(last["filed_count"], 2)
            self.assertEqual(last["attention_count"], 1)
            self.assertEqual(last["routine_count"], 1)

    def test_no_suggest_when_nothing_filed(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            payload = {"cards": [], "undraftable": [
                {"key": "S2", "reason": "no legible intent",
                 "backlog": "code"}]}
            proc, data = run_file(orch, payload)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("suggest", data)
            last = json.loads((orch / "alignment" / "last-run.json")
                              .read_text(encoding="utf-8"))
            self.assertNotIn("suggest", last)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_file(orch, [card("S1", 90)], ["--dry-run"])
            self.assertTrue(data["dry_run"])
            self.assertFalse((orch / "alignment" / "drafts").exists())
            self.assertIn("- [ ] S1",
                          (orch / "backlogs" / "code.md")
                          .read_text(encoding="utf-8"))

    def test_mock_staged_and_mock_line_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 90, sections={
                "Visual Preview": "- **Wireframe:** n/a — no UI surface\n"})
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            staged = (orch / "alignment" / "drafts" / "assets" / "S1"
                      / "mock.html")
            self.assertTrue(staged.is_file())
            body = (orch / "alignment" / "drafts" / "S1.md") \
                .read_text(encoding="utf-8")
            self.assertIn("- **Mock:** alignment/drafts/assets/S1/mock.html",
                          body)
            # Mock line lands after the Wireframe line
            self.assertLess(body.index("**Wireframe:**"),
                            body.index("**Mock:**"))
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertIn("| mock: alignment/drafts/assets/S1/mock.html", text)

    def test_mock_replaces_existing_mock_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 90, sections={
                "Visual Preview":
                    "- **Wireframe:** https://wiretext.app/w/abc\n"
                    "- **Mock:** stale/path.html\n"})
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            body = (orch / "alignment" / "drafts" / "S1.md") \
                .read_text(encoding="utf-8")
            self.assertNotIn("stale/path.html", body)
            self.assertEqual(body.count("**Mock:**"), 1)

    def test_mock_missing_file_warns_and_marks_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 90, sections={
                "Visual Preview": "- **Wireframe:** n/a — no UI surface\n"})
            c["mock"] = str(Path(tmp) / "nope.html")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(any("mock" in w for w in data["warnings"]))
            body = (orch / "alignment" / "drafts" / "S1.md") \
                .read_text(encoding="utf-8")
            self.assertIn("unavailable — mock file missing", body)
            self.assertFalse(
                (orch / "alignment" / "drafts" / "assets").exists())
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertNotIn("| mock:", text)

    def test_no_mock_no_mock_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_file(orch, [card("S1", 90)])
            text = (orch / "alignment-checklist.md").read_text(encoding="utf-8")
            self.assertNotIn("| mock:", text)

    def test_mock_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 90)
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c], ["--dry-run"])
            self.assertTrue(data["dry_run"])
            self.assertFalse((orch / "alignment" / "drafts").exists())

    def test_mock_without_frame_token_warns(self):
        """The file contract's frame declaration is the mechanical floor
        — a mock naming no browser:/phone: environment warns."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(
                "<html><body>" + "x" * 300 + "</body></html>",
                encoding="utf-8")
            c = card("S1", 95, sections={
                "Visual Preview":
                    "- **Wireframe:** unavailable — wiretext absent\n"})
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(any("environment frame" in w
                                for w in data["warnings"]))

    def test_mock_frame_token_no_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 95, sections={
                "Visual Preview":
                    "- **Wireframe:** unavailable — wiretext absent\n"})
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(any("environment frame" in w
                                 for w in data.get("warnings", [])))

    def test_supersede_moves_mock_assets_with_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 95, sections={"Marshal's Read": "- v1\n"})
            c["mock"] = str(mock_src)
            run_file(orch, [c])
            # refile with a changed body and changed mock
            mock_src.write_text(MOCK_HTML + "v2", encoding="utf-8")
            c2 = card("S1", 60, ["revised"],
                      sections={"Marshal's Read": "- v2\n"})
            c2["mock"] = str(mock_src)
            proc, data = run_file(orch, [c2])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            snaps = list((orch / "alignment" / "superseded").glob("*.assets"))
            self.assertEqual(len(snaps), 1)
            self.assertEqual(
                (snaps[0] / "mock.html").read_text(encoding="utf-8"),
                MOCK_HTML)
            staged = (orch / "alignment" / "drafts" / "assets" / "S1"
                      / "mock.html")
            self.assertEqual(staged.read_text(encoding="utf-8"),
                             MOCK_HTML + "v2")

    def test_backlog_marker_flips(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            run_file(orch, [card("S1", 90)])
            backlog = (orch / "backlogs" / "code.md").read_text(encoding="utf-8")
            self.assertIn("- [A] S1", backlog)
            self.assertIn("- [ ] S2", backlog)

    def test_backlog_map_resolves_mapped_file(self):
        """--backlog-map carries the cdo:backlog_map config — a mapped
        backlog lives outside {orch}/backlogs and still gets flipped."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "alt").mkdir()
            (orch / "alt" / "code.md").write_text(
                "- [ ] S1 — first\n", encoding="utf-8")
            proc, data = run_file(
                orch, [card("S1", 90)],
                ["--backlog-map", json.dumps({"code": "alt/code.md"})])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("- [A] S1",
                          (orch / "alt" / "code.md").read_text(encoding="utf-8"))
            # the default dir's same-named file is untouched
            self.assertIn("- [ ] S1",
                          (orch / "backlogs" / "code.md")
                          .read_text(encoding="utf-8"))

    def test_backlog_map_unmapped_stem_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "alt").mkdir()
            (orch / "alt" / "ops.md").write_text(
                "- [ ] S9 — other\n", encoding="utf-8")
            proc, data = run_file(
                orch, [card("S1", 90)],
                ["--backlog-map", json.dumps({"ops": "alt/ops.md"})])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("- [A] S1",
                          (orch / "backlogs" / "code.md")
                          .read_text(encoding="utf-8"))

    def test_backlog_map_malformed_is_named_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_file(orch, [card("S1", 90)],
                                  ["--backlog-map", "not json"])
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("backlog-map" in e for e in data["errors"]))

    def test_cosign_stamp_files_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            install_product(orch)
            c = card("S1", 95,
                     header="- **P&D co-sign:** sign — reads clean")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("S1", data["routine"])
            self.assertFalse(any("unsigned" in w
                                 for w in data.get("warnings", [])))

    def test_cosign_placeholder_is_not_a_stamp(self):
        """The template's literal `{sign|revise|reject — rationale}`
        placeholder satisfies the old substring check — it must not
        pass as a signature."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            install_product(orch)
            c = card("S1", 95, header=(
                "- **P&D co-sign:** {sign|revise|reject — rationale}"))
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("S1", data["needs_attention"])
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertIn("unsigned-cosign", text)

    def test_cosign_prose_mention_is_not_a_stamp(self):
        """A body mention of `P&D co-sign:` isn't the contracted stamp
        line — column-0 anchored like the other contract lines."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            install_product(orch)
            c = card("S1", 95, sections={
                "Marshal's Read": "- the P&D co-sign: gate held\n"})
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("S1", data["needs_attention"])
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertIn("unsigned-cosign", text)

    def test_cosign_disputed_verdict_counts_as_stamped(self):
        """A non-sign verdict means the co-sign ran — the Operator
        adjudicates the dispute, not the gate."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            install_product(orch)
            c = card("S1", 95, ["P&D disputed"],
                     header="- **P&D co-sign:** revise — scope contested")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(any("unsigned" in w
                                 for w in data.get("warnings", [])))
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertNotIn("unsigned-cosign", text)


class TestMockStagingEdges(unittest.TestCase):
    """Hostile-environment edges on the mock staging contract — the
    script owns the Mock line, so every divergent input must degrade
    deterministically rather than desync card, checklist, and disk."""

    def _vp_card(self, key, conf, mock_line=None, terminal=False):
        """card() with the Visual Preview section moved to LAST position
        — section order is free, and a trailing section exercises the
        terminal-line insert path. `terminal` drops the final newline."""
        secs = dict(SECTIONS)
        del secs["Visual Preview"]
        secs["Visual Preview"] = (
            "- **Wireframe:** https://wiretext.app/w/abc\n"
            + (f"- **Mock:** {mock_line}\n"
               if mock_line is not None else ""))
        c = card(key, conf, sections=secs)
        if terminal:
            c["body"] = c["body"].rstrip("\n")
        return c

    def test_mock_directory_stages_as_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mockdir = Path(tmp) / "mocks"
            mockdir.mkdir()
            (mockdir / "list.html").write_text(
                "<html><body>list</body></html>", encoding="utf-8")
            (mockdir / "detail.html").write_text(
                "<html><body>detail</body></html>", encoding="utf-8")
            c = self._vp_card("S1", 95)
            c["mock"] = str(mockdir)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            staged = (orch / "alignment" / "drafts" / "assets" / "S1"
                      / "mock")
            self.assertTrue((staged / "list.html").is_file())
            self.assertTrue((staged / "detail.html").is_file())
            body = (orch / "alignment" / "drafts" / "S1.md").read_text(
                encoding="utf-8")
            self.assertIn(
                "- **Mock:** alignment/drafts/assets/S1/mock/", body)

    def test_mock_self_copy_doesnt_crash(self):
        """Prompt layer stages the mock at the dest path itself and passes
        it — self-copy must be a no-op, never a mid-drain crash."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            dest = (orch / "alignment" / "drafts" / "assets" / "S1"
                    / "mock.html")
            dest.parent.mkdir(parents=True)
            dest.write_text(MOCK_HTML, encoding="utf-8")
            c = self._vp_card("S1", 95)
            c["mock"] = str(dest)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            body = (orch / "alignment" / "drafts" / "S1.md").read_text(
                encoding="utf-8")
            self.assertIn(
                "- **Mock:** alignment/drafts/assets/S1/mock.html", body)

    def test_relative_mock_anchors_to_cards_dir(self):
        """A relative `mock` resolves against the cards.json directory —
        not the process CWD the script happened to launch from."""
        with tempfile.TemporaryDirectory() as tmp, \
                tempfile.TemporaryDirectory() as cdir:
            orch = make_orch(Path(tmp))
            mock_file = Path(cdir) / "mock.html"
            mock_file.write_text(MOCK_HTML, encoding="utf-8")
            c = self._vp_card("S1", 95)
            c["mock"] = "mock.html"
            cpath = Path(cdir) / "cards.json"
            cpath.write_text(json.dumps([c]), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--orchestration-dir",
                 str(orch), "--cards", str(cpath)],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(
                (orch / "alignment" / "drafts" / "assets" / "S1"
                 / "mock.html").is_file())

    def test_declared_mock_not_staged_degrades(self):
        """Card claims a mock path but the payload supplies none — the
        claim is existence-checked and degraded, never trusted."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = self._vp_card(
                "S1", 95,
                mock_line="alignment/drafts/assets/S1/mock.html")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(any("no mock was staged" in w
                                for w in data["warnings"]))
            body = (orch / "alignment" / "drafts" / "S1.md").read_text(
                encoding="utf-8")
            self.assertIn(
                "unavailable — mock declared but not staged", body)

    def test_declared_mock_already_staged_passes(self):
        """Claim + real file on disk (pre-staged) → line kept, no warn."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            dest = (orch / "alignment" / "drafts" / "assets" / "S1"
                    / "mock.html")
            dest.parent.mkdir(parents=True)
            dest.write_text("<html></html>", encoding="utf-8")
            c = self._vp_card(
                "S1", 95,
                mock_line="alignment/drafts/assets/S1/mock.html")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(any("declared but not staged" in w
                                 for w in data.get("warnings", [])))
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertIn(
                "| mock: alignment/drafts/assets/S1/mock.html", text)

    def test_placeholder_mock_flags_ungrounded(self):
        """Placeholder styling must surface as a flag — a quiet
        placeholder that routes Routine defeats the flag's purpose."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(
                "<!-- phone:bare -->\n"
                "<!-- placeholder styling — no design tokens found -->\n"
                + "<html><body>" + "x" * 300 + "</body></html>",
                encoding="utf-8")
            c = self._vp_card("S1", 95)
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(any("ungrounded:design-tokens" in w
                                for w in data["warnings"]))
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertIn("ungrounded:design-tokens", text)

    def test_external_refs_warn(self):
        """A mock full of CDN links violates the file contract — warn,
        never block."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(
                "<!-- browser:/dash -->\n<html><head>"
                '<link href="https://cdn.example.com/x.css" '
                'rel="stylesheet"></head><body>'
                + "x" * 300 + "</body></html>",
                encoding="utf-8")
            c = self._vp_card("S1", 95)
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(any("external assets" in w
                                for w in data["warnings"]))

    def test_terminal_wireframe_line_no_crash(self):
        """Wireframe as the body's last line with no trailing newline —
        the Mock insert must not crash mid-drain."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = self._vp_card("S1", 95, terminal=True)
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            body = (orch / "alignment" / "drafts" / "S1.md").read_text(
                encoding="utf-8")
            self.assertIn(
                "- **Mock:** alignment/drafts/assets/S1/mock.html", body)

    def test_wire_with_na_mock_fails_filing(self):
        """Wire produced + Mock `n/a` is a contract break — a wire proves
        a UI surface; named error, nothing files."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = self._vp_card("S1", 95, mock_line="n/a — no UI surface")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("n/a" in e and "S1" in e
                                for e in data["errors"]))
            self.assertFalse(
                (orch / "alignment" / "drafts" / "S1.md").exists())
            self.assertIn("- [ ] S1",
                          (orch / "backlogs" / "code.md")
                          .read_text(encoding="utf-8"))

    def test_wire_with_no_mock_line_fails_filing(self):
        """Wire produced + no Mock line at all — the drafter filed before
        finishing Visual Preview; named error, nothing files."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = self._vp_card("S1", 95)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("`absent`" in e for e in data["errors"]))
            self.assertFalse(
                (orch / "alignment" / "drafts" / "S1.md").exists())

    def test_gate_fails_batch_before_any_writes(self):
        """A wire-only card in a multi-card batch aborts the whole
        payload — the clean card files nothing either (no half-filed
        run)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            good = card("S2", 95)  # n/a both — honest non-UI
            bad = self._vp_card("S1", 95)
            proc, data = run_file(orch, [good, bad])
            self.assertEqual(proc.returncode, 1)
            self.assertFalse(
                (orch / "alignment" / "drafts" / "S2.md").exists())
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertNotIn("S2 — Story S2", text)
            self.assertIn("- [ ] S2",
                          (orch / "backlogs" / "code.md")
                          .read_text(encoding="utf-8"))

    def test_wire_with_unavailable_mock_no_flag(self):
        """`unavailable — {reason}` beside a wire is an honest claim —
        files clean at high confidence, no mock-missing flag."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = self._vp_card(
                "S1", 95,
                mock_line="unavailable — editor crashed mid-write")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("S1", data["routine"])
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertNotIn("mock-missing", text)

    def test_wireframe_payload_without_preview_is_batch_error(self):
        """A card with no Visual Preview content fails required-section
        validation — a `wireframe` payload field doesn't rescue it."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95, sections={"Visual Preview": ""})
            c["wireframe"] = "https://wiretext.app/w/abc123"
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("Visual Preview" in e
                                for e in data["errors"]))

    def test_no_wire_na_mock_no_flag(self):
        """Honest non-UI card — both sentinels n/a, nothing produced —
        nothing to flag."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_file(orch, [card("S1", 95)])
            self.assertIn("S1", data["routine"])

    def test_mock_with_na_wire_flags_missing(self):
        """Mirror direction: a staged mock beside Wireframe `n/a` — the
        mock proves a UI surface; flag wire-missing."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 95, sections={
                "Visual Preview": "- **Wireframe:** n/a — no UI surface\n"})
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(any("wire-missing" in w or "mock produced"
                                in w for w in data["warnings"]))
            self.assertIn("S1", data["needs_attention"])
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertIn("wire-missing", text)

    def test_mock_with_absent_wire_flags_missing(self):
        """Staged mock on a card with no Wireframe line at all — the
        wire was skipped, not declined; flag wire-missing."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 95, sections={
                "Visual Preview": "- **Mock:** pending\n"})
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("S1", data["needs_attention"])
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertIn("wire-missing", text)

    def test_unavailable_wire_na_mock_fails_filing(self):
        """An `unavailable` wire was *attempted* — attempting presupposes
        a surface, so Mock `n/a` beside it is still a contract break."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95, sections={
                "Visual Preview":
                    "- **Wireframe:** unavailable — wiretext MCP absent\n"
                    "- **Mock:** n/a — no UI surface\n"})
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("n/a" in e and "S1" in e
                                for e in data["errors"]))
            self.assertFalse(
                (orch / "alignment" / "drafts" / "S1.md").exists())

    def test_unavailable_wire_real_mock_no_flag(self):
        """Wire failed honestly, mock produced — the consistent state:
        no flag either direction."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            mock_src = Path(tmp) / "mock.html"
            mock_src.write_text(MOCK_HTML, encoding="utf-8")
            c = card("S1", 95, sections={
                "Visual Preview":
                    "- **Wireframe:** unavailable — wiretext MCP absent\n"})
            c["mock"] = str(mock_src)
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("S1", data["routine"])
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertNotIn("-missing", text)

    def test_oversized_signal_auto_flagged(self):
        """size `full` + ≥3 distinct touches dirs trips `oversized`
        deterministically — an undeclared card gets flagged."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95,
                     fm="touches: [server/, stores/, components/]",
                     header="- **Sizing:** full")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(any("oversized" in w
                                for w in data["warnings"]))
            self.assertIn("S1", data["needs_attention"])
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertIn("oversized", text)

    def test_oversized_declared_no_double_flag(self):
        """A card that already carries `oversized` gets no warning and
        no duplicate flag."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            c = card("S1", 95, ["oversized"],
                     fm="touches: [server/, stores/, components/]",
                     header="- **Sizing:** full")
            proc, data = run_file(orch, [c])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(any("trips" in w
                                 for w in data.get("warnings", [])))
            text = (orch / "alignment-checklist.md").read_text(
                encoding="utf-8")
            self.assertEqual(text.count("oversized"), 1)

    def test_lite_sizing_and_few_touches_no_flag(self):
        """`lite` sizing (or `full` with <3 touches) doesn't trip the
        countable signal — interpretive cases stay prompt-side."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            lite = card("S1", 95,
                        fm="touches: [server/, stores/, components/]",
                        header="- **Sizing:** lite")
            small = card("S2", 95, fm="touches: [server/, stores/]",
                         header="- **Sizing:** full")
            proc, data = run_file(orch, [lite, small])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(any("oversized" in w
                                 for w in data.get("warnings", [])))
            self.assertIn("S1", data["routine"])
            self.assertIn("S2", data["routine"])

    def test_parked_assets_supersede_with_card(self):
        """A fresh draft supersedes a parked card — its parked mock
        assets ride along, and the superseded card's Mock line is
        retargeted instead of left citing parked/."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            pdir = orch / "alignment" / "parked"
            (pdir / "assets" / "S2").mkdir(parents=True)
            (pdir / "assets" / "S2" / "mock.html").write_text(
                "<html>parked</html>", encoding="utf-8")
            (pdir / "S2.md").write_text(
                "# card\n## Visual Preview\n\n"
                "- **Wireframe:** https://wiretext.app/w/abc\n"
                "- **Mock:** alignment/parked/assets/S2/mock.html\n",
                encoding="utf-8")
            proc, data = run_file(orch, [card("S2", 90)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            snaps = list((orch / "alignment" / "superseded")
                         .glob("S2.*.parked.assets/mock.html"))
            self.assertEqual(len(snaps), 1)
            card_snap = next((orch / "alignment" / "superseded")
                             .glob("S2.*.parked.md"))
            self.assertIn("superseded/S2.", card_snap.read_text(
                encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
