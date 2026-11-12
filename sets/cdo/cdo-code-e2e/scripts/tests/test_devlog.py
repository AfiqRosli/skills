#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for devlog.py."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixture import SCRIPTS, Fixture  # noqa: E402


class TestDevlog(Fixture):
    def setUp(self):
        super().setUp()
        self.d = self.root / "docs" / "devlog" / "Beta" / "2026-09-14.2" / "1-2-bar-story"

    def run_cli(self, *cli_args):
        return subprocess.run([sys.executable, str(SCRIPTS / "devlog.py"), *cli_args],
                              capture_output=True, text=True)

    def test_init_set_get_append(self):
        proc = self.run_cli("init", str(self.d), "--story-key", "1-2-bar-story",
                            "--release", "Beta-2026.09.14.2", "--sprint-status",
                            "x/sprint.yaml", "--story-file", "x/story.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        index = (self.d / "index.md").read_text(encoding="utf-8")
        self.assertIn("1-2-bar-story", index)
        self.assertIn("create-story: pending", index)
        self.assertTrue((self.root / "docs" / "devlog" / "index.md").exists())

        proc = self.run_cli("set", str(self.d), "create-story", "done")
        self.assertEqual(proc.returncode, 0, proc.stderr)

        state = json.loads(self.run_cli("get", str(self.d)).stdout)
        self.assertEqual(state["steps"]["create-story"], "done")
        self.assertEqual(state["steps"]["wireframe"], "pending")

        proc = self.run_cli("append", str(self.d), "--title", "test entry", "--text", "body")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("test entry", (self.d / "index.md").read_text(encoding="utf-8"))

    def test_set_rejects_bad_step(self):
        self.run_cli("init", str(self.d), "--story-key", "s", "--release", "r",
                     "--sprint-status", "x", "--story-file", "y")
        proc = self.run_cli("set", str(self.d), "nonexistent-step", "done")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
