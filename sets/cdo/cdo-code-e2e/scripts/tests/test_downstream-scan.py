#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for downstream-scan.py — epic-doc stem matching."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixture import SCRIPTS, Fixture  # noqa: E402

EPIC = """# Epic

### Story 1.1: Current thing

**Story:** builds the FooStore.

### Story 1.2: Later thing

**Story:** extends `ThingStore` and adds a payout CSV.

### Story 1.3: Unrelated thing

**Story:** marketing copy pass.
"""


class TestDownstreamScan(Fixture):
    def setUp(self):
        super().setUp()
        self.epic = self.root / "epic.md"
        self.epic.write_text(EPIC, encoding="utf-8")

    def run_scan(self, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "downstream-scan.py"),
             "--epic", str(self.epic), *extra],
            capture_output=True, text=True)

    def test_flags_sections_by_stem(self):
        proc = self.run_scan("--files", " M stores/ThingStore.ts")
        data = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stories = [f["story"] for f in data["flagged_sections"]]
        self.assertEqual(stories, ["1.2"])
        self.assertIn("ThingStore", data["stems"])

    def test_doc_stems_and_short_stems_ignored(self):
        proc = self.run_scan("--files", "docs/guide.md", "src/ab.ts")
        data = json.loads(proc.stdout)
        self.assertEqual(data["stems"], [])
        self.assertEqual(data["flagged_sections"], [])

    def test_sprint_status_annotates_after_current(self):
        # --sprint-status + --story-key doesn't drop sections — it marks
        # flagged ones as downstream-of-current via `after_current`.
        sprint = self.root / "sprint.yaml"
        sprint.write_text(
            "development_status:\n  1-1-current: review\n"
            "  1-2-later: backlog\n  1-3-unrelated: backlog\n",
            encoding="utf-8")
        proc = self.run_scan("--files", " M x/ThingStore.ts",
                             "--sprint-status", str(sprint),
                             "--story-key", "1-2-later")
        data = json.loads(proc.stdout)
        # 1.2 is the current story itself → flagged but after_current False
        self.assertEqual(data["flagged_sections"],
                         [{"story": "1.2", "matched_stems": ["ThingStore"],
                           "after_current": False}])
        proc = self.run_scan("--files", " M x/ThingStore.ts",
                             "--sprint-status", str(sprint),
                             "--story-key", "1-1-current")
        data = json.loads(proc.stdout)
        # from 1-1-current, 1.2 IS downstream
        self.assertTrue(data["flagged_sections"][0]["after_current"])


if __name__ == "__main__":
    import unittest
    unittest.main()
