#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for gitpaths.py — porcelain line parsing and path normalization."""
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixture import SCRIPTS  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGitpaths(unittest.TestCase):
    def setUp(self):
        self.gp = load("gitpaths")

    def test_parse_status_prefixes(self):
        self.assertEqual(self.gp.parse_porcelain_line(" M server/areas.ts"),
                         "server/areas.ts")
        self.assertEqual(self.gp.parse_porcelain_line("?? src/new.vue"),
                         "src/new.vue")
        self.assertEqual(self.gp.parse_porcelain_line("M  staged.ts"), "staged.ts")

    def test_parse_rename_keeps_destination(self):
        self.assertEqual(
            self.gp.parse_porcelain_line("R  old/name.ts -> new/name.ts"),
            "new/name.ts")

    def test_parse_quoted_and_plain(self):
        self.assertEqual(self.gp.parse_porcelain_line('"src/spaced file.ts"'),
                         "src/spaced file.ts")
        self.assertEqual(self.gp.parse_porcelain_line("stores/ThingStore.ts"),
                         "stores/ThingStore.ts")

    def test_parse_blank_returns_none(self):
        self.assertIsNone(self.gp.parse_porcelain_line(""))
        self.assertIsNone(self.gp.parse_porcelain_line("   "))

    def test_normalize_returns_paths_and_unparsed(self):
        paths, unparsed = self.gp.normalize_changed_paths(
            [" M a.ts", "?? b.vue", "M c.ts"])
        self.assertEqual(paths, ["a.ts", "b.vue"])
        # "M c.ts" is only 6 chars — its residual status prefix can't be
        # normalized away, so it lands in unparsed rather than as a path.
        self.assertIn("M c.ts", unparsed)


if __name__ == "__main__":
    unittest.main()
