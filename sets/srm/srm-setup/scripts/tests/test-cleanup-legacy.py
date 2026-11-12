#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Tests for cleanup-legacy.py."""

from __future__ import annotations

import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_script_path = Path(__file__).resolve().parent.parent / "cleanup-legacy.py"
_spec = spec_from_file_location("cleanup_legacy", _script_path)
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)


class TestFindSkillDirs(unittest.TestCase):
    def test_finds_dirs_with_skill_md(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "skill-a").mkdir()
            (root / "skill-a" / "SKILL.md").write_text("x", encoding="utf-8")
            (root / "nested" / "skill-b").mkdir(parents=True)
            (root / "nested" / "skill-b" / "SKILL.md").write_text("x", encoding="utf-8")
            (root / "not-a-skill").mkdir()
            self.assertEqual(_mod.find_skill_dirs(td), ["skill-a", "skill-b"])

    def test_missing_root_returns_empty(self):
        self.assertEqual(_mod.find_skill_dirs("does/not/exist"), [])


class TestCountFiles(unittest.TestCase):
    def test_counts_recursively(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("x", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_text("x", encoding="utf-8")
            self.assertEqual(_mod.count_files(root), 2)


class TestCleanupDirectories(unittest.TestCase):
    def test_removes_dirs_and_reports(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "mod-a").mkdir()
            (root / "mod-a" / "f.txt").write_text("x", encoding="utf-8")
            removed, not_found, total = _mod.cleanup_directories(td, ["mod-a", "ghost"])
            self.assertEqual(removed, ["mod-a"])
            self.assertEqual(not_found, ["ghost"])
            self.assertEqual(total, 1)
            self.assertFalse((root / "mod-a").exists())


class TestTokenGuard(unittest.TestCase):
    def test_rejects_unresolved_project_root(self):
        with self.assertRaises(SystemExit):
            _mod.reject_unresolved_paths([("--bmad-dir", "{project-root}/_bmad")])


if __name__ == "__main__":
    unittest.main()
