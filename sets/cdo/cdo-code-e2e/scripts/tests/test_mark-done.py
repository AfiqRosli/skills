#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for mark-done.py."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixture import SCRIPTS, Fixture  # noqa: E402


class TestMarkDone(Fixture):
    def test_done_surgery(self):
        impl = self.root / "_bmad-output" / "implementation-artifacts"
        story = impl / "Beta-2026.09.14.2" / "1-2-bar-story.md"
        sprint = impl / "sprint-status-Beta-2026.09.14.2.yaml"
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "mark-done.py"),
             "--story-file", str(story), "--sprint-status", str(sprint),
             "--story-key", "1-2-bar-story", "--summary", "shipped the thing",
             "--date", "2026-09-16"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        s = sprint.read_text(encoding="utf-8")
        self.assertIn("1-2-bar-story: done", s)
        self.assertIn("DONE 2026-09-16", s)
        self.assertIn("# NEW -- second story", s)   # existing comment preserved
        self.assertIn("1-1-foo-story: review", s)   # other entries untouched
        self.assertIn("last_updated: 2026-09-16", s)

        st = story.read_text(encoding="utf-8")
        self.assertIn("Status: done", st)
        self.assertIn("Pipeline complete (cdo-code-e2e)", st)

    def test_missing_key_fails(self):
        impl = self.root / "_bmad-output" / "implementation-artifacts"
        story = impl / "Beta-2026.09.14.2" / "1-2-bar-story.md"
        sprint = impl / "sprint-status-Beta-2026.09.14.2.yaml"
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "mark-done.py"),
             "--story-file", str(story), "--sprint-status", str(sprint),
             "--story-key", "9-9-nope", "--summary", "x"],
            capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    import unittest
    unittest.main()
