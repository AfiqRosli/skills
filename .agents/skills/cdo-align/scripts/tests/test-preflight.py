"""Tests for preflight.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "preflight.py"

CHECKLIST = "# Alignment Checklist\n\n## Needs Attention\n\n## Routine Review\n"

DOCTRINE = """# Doctrine

## Standing Policies

- P1: naming rule
- P2: dep rule

## Decision Log

- 2026-10-20 — newest decision
- 2026-10-19 — second newest
"""

CARD = """---
key: "S9"
declared_surface: ["env-changed"]
grounded_against:
  commit: "aaaa1111"
  drafted: "2026-10-20"
---

# Alignment Card — S9
"""


def run_preflight(orch: Path, extra=()):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), *extra],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_orch(root: Path) -> Path:
    orch = root / "docs" / "orchestration"
    (orch / "backlogs").mkdir(parents=True)
    (orch / "alignment" / "drafts").mkdir(parents=True)
    (orch / "alignment-checklist.md").write_text(CHECKLIST, encoding="utf-8")
    (orch / "doctrine.md").write_text(DOCTRINE, encoding="utf-8")
    (orch / "intent.md").write_text(
        "# Intent\nRefreshed: 2026-10-21\n\nThrust: ship the funnel.\n",
        encoding="utf-8")
    (orch / "backlogs" / "code.md").write_text(
        "- [ ] S1 — first\n- [A] S2 — aligned\n- [?] S3 — undraftable\n"
        "- [ ] S4 — fourth\n",
        encoding="utf-8")
    return orch


class TestPreflight(unittest.TestCase):
    def test_worklist_selects_unaligned_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_preflight(make_orch(Path(tmp)))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual([w["key"] for w in data["worklist"]],
                             ["S1", "S4"])
            skipped = {s["key"]: s["reason"] for s in data["skipped"]}
            self.assertEqual(skipped, {"S2": "draft filed",
                                       "S3": "undraftable"})

    def test_story_overrides_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_preflight(make_orch(Path(tmp)),
                                       ["--story", "S3"])
            self.assertEqual([w["key"] for w in data["worklist"]], ["S3"])

    def test_limit_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_preflight(make_orch(Path(tmp)), ["--limit", "1"])
            self.assertEqual(len(data["worklist"]), 1)

    def test_doctrine_slice_and_intent_staleness(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_preflight(make_orch(Path(tmp)))
            self.assertIn("P1", data["doctrine"]["standing_policies"])
            self.assertEqual(data["doctrine"]["newest_log_date"],
                             "2026-10-20")
            # intent refreshed 10-21 >= newest log 10-20 → not stale
            self.assertFalse(data["intent"]["stale"])

    def test_stale_intent_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "intent.md").write_text(
                "# Intent\nRefreshed: 2026-10-15\n", encoding="utf-8")
            proc, data = run_preflight(orch)
            self.assertTrue(data["intent"]["stale"])

    def test_corpus_index_reads_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "alignment" / "drafts" / "S9.md").write_text(
                CARD, encoding="utf-8")
            proc, data = run_preflight(orch)
            d = data["corpus"]["drafts"][0]
            self.assertEqual(d["key"], "S9")
            self.assertEqual(d["declared_surface"], ["env-changed"])
            self.assertEqual(d["grounded_commit"], "aaaa1111")

    def test_missing_stores_warn_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "docs" / "orchestration"
            (orch / "backlogs").mkdir(parents=True)
            proc, data = run_preflight(orch)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(data["scaffold"]["checklist"])
            self.assertTrue(data["warnings"])


if __name__ == "__main__":
    unittest.main()
