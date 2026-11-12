"""Tests for resolve-item.py — run: python test-resolve-item.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "resolve-item.py"

CARD = """# Alignment Card — {key}: title

- **Confidence:** 90%

## Visual Preview

- **Wireframe:** {wire}

## Execution Surface

- **Risk surface:** `{risk}`
"""


def run_resolve(orch: Path, key: str):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), key],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestResolveItem(unittest.TestCase):
    def make_orch(self, root: Path):
        orch = root / "docs" / "orchestration"
        (orch / "backlogs").mkdir(parents=True)
        (orch / "alignment" / "drafts").mkdir(parents=True)
        (orch / "alignment" / "2026" / "10" / "17").mkdir(parents=True)
        (orch / "backlogs" / "code.md").write_text(
            "- [x] S9 — 02-01 UTM + referral tracking | size: lite\n"
            "- [ ] S10 — internal refactor | size: full\n",
            encoding="utf-8",
        )
        (orch / "flow-ledger.yaml").write_text(
            "stories:\n  S9:\n    status: queued\n", encoding="utf-8")
        return orch

    def test_confirmed_card_status_and_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            (orch / "alignment" / "2026" / "10" / "17" / "S9.md").write_text(
                "<!-- confirm 2026-10-17 03:00 UTC -->\n\n" +
                CARD.format(key="S9", wire="https://wiretext.app/w/abc123",
                            risk="schema-migration"),
                encoding="utf-8")
            proc, data = run_resolve(orch, "S9")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["card_status"], "confirmed")
            self.assertEqual(data["card"]["declared"], ["schema-migration"])
            self.assertEqual(data["card"]["wireframe"],
                             "https://wiretext.app/w/abc123")

    def test_draft_is_not_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            (orch / "alignment" / "drafts" / "S10.md").write_text(
                CARD.format(key="S10", wire="n/a — no UI surface", risk="none"),
                encoding="utf-8")
            proc, data = run_resolve(orch, "S10")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["card_status"], "draft")
            self.assertEqual(data["card"]["declared"], [])
            self.assertEqual(data["card"]["wireframe_status"], "no-ui-surface")

    def test_rejected_archive_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            (orch / "alignment" / "2026" / "10" / "17" / "S9.md").write_text(
                "<!-- reject 2026-10-17 04:00 UTC — out of scope -->\n\n" +
                CARD.format(key="S9", wire="https://wiretext.app/w/x1",
                            risk="schema-migration"),
                encoding="utf-8")
            proc, data = run_resolve(orch, "S9")
            self.assertEqual(data["card_status"], "rejected")

    def test_story_slug_maps_to_item_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            (orch / "alignment" / "2026" / "10" / "17" / "S9.md").write_text(
                "<!-- confirm 2026-10-17 03:00 UTC -->\n\n" +
                CARD.format(key="S9", wire="n/a — no UI surface",
                            risk="deps-changed"),
                encoding="utf-8")
            proc, data = run_resolve(orch, "02-01-utm-parameter-tracking")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["resolved_key"], "S9")
            self.assertEqual(data["card_status"], "confirmed")
            self.assertEqual(data["card"]["declared"], ["deps-changed"])

    def test_unknown_token_reported_not_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            (orch / "alignment" / "drafts" / "S10.md").write_text(
                CARD.format(key="S10", wire="n/a — no UI surface",
                            risk="schema_migration"),
                encoding="utf-8")
            proc, data = run_resolve(orch, "S10")
            self.assertEqual(data["card"]["declared"], [])
            self.assertEqual(data["card"]["unknown_tokens"], ["schema_migration"])

    def test_token_mention_outside_section_not_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orch(Path(tmp))
            body = ("# card\n## Flags\n\n- this does NOT need a "
                    "schema-migration — resolves if design settles\n")
            (orch / "alignment" / "drafts" / "S10.md").write_text(
                body, encoding="utf-8")
            proc, data = run_resolve(orch, "S10")
            self.assertEqual(data["card"]["declared"], [])


if __name__ == "__main__":
    unittest.main()
