#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Tests for sync.py."""

from __future__ import annotations

import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_script_path = Path(__file__).resolve().parent.parent / "sync.py"
_spec = spec_from_file_location("srm_sync", _script_path)
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)


class TestNaming(unittest.TestCase):
    def test_slug_basic(self):
        self.assertEqual(_mod.slug("Hello World"), "hello-world")

    def test_slug_underscores_and_case(self):
        self.assertEqual(_mod.slug("Foo_Bar BAZ"), "foo-bar-baz")

    def test_slug_strips_non_alnum(self):
        self.assertEqual(_mod.slug("--a--b--"), "a-b")
        self.assertEqual(_mod.slug("!!!"), "")

    def test_resolve_tokens(self):
        out = _mod.resolve("{skills_repo_root}/x/{project-root}", {
            "skills_repo_root": "/repos", "project-root": "/proj"})
        self.assertEqual(out, "/repos/x//proj")

    def test_registry_get_case_insensitive(self):
        data = {"repos": [{"name": "BMAD-CYBERSEC"}, {"name": "wondelai"}]}
        self.assertEqual(_mod.registry_get(data, "bmad-cybersec")["name"], "BMAD-CYBERSEC")
        self.assertIsNone(_mod.registry_get(data, "nope"))


class TestFrontmatter(unittest.TestCase):
    def test_parse_and_dump_roundtrip(self):
        text = "---\nname: foo\ndescription: bar\n---\n\n# Body\n"
        fm, body = _mod.parse_frontmatter(text)
        self.assertEqual(fm["name"], "foo")
        self.assertIn("# Body", body)
        out = _mod.dump_frontmatter(fm, body)
        fm2, body2 = _mod.parse_frontmatter(out)
        self.assertEqual(fm2, fm)
        self.assertIn("# Body", body2)

    def test_parse_no_frontmatter(self):
        fm, body = _mod.parse_frontmatter("# just md\n")
        self.assertEqual(fm, {})
        self.assertEqual(body, "# just md\n")

    def test_first_line_skips_headers_and_fm(self):
        self.assertEqual(_mod.first_line("---\nx: 1\n---\n\nReal title here\n"), "Real title here")
        self.assertEqual(_mod.first_line(""), "")


class TestDeref(unittest.TestCase):
    def test_deref_dir_passthrough(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "real"
            d.mkdir()
            self.assertEqual(_mod.deref(d, td), d)

    def test_deref_windows_symlink_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "target-dir").mkdir()
            link = root / ".agents" / "skills"
            link.mkdir(parents=True)
            f = link / "target-dir"
            f.write_text("../../target-dir", encoding="utf-8")
            self.assertEqual(_mod.deref(f, root), (root / "target-dir").resolve())

    def test_deref_real_file_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "README.md"
            f.write_text("# docs\n" * 100, encoding="utf-8")
            self.assertEqual(_mod.deref(f, td), f)


class TestOriginMarkers(unittest.TestCase):
    def test_write_read_origin_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            _mod.write_origin(td, "repo-x", "src/core", "abc1234")
            m = _mod.read_origin(td)
            self.assertEqual(m["repo"], "repo-x")
            self.assertEqual(m["source"], "src/core")
            self.assertEqual(m["commit"], "abc1234")
            self.assertIn("synced_at", m)

    def test_read_origin_missing_and_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(_mod.read_origin(td))
            (Path(td) / _mod.ORIGIN).write_text("{not json", encoding="utf-8")
            self.assertIsNone(_mod.read_origin(td))

    def test_origin_marker_name(self):
        self.assertEqual(_mod.ORIGIN, ".srm-origin")


class TestClaimable(unittest.TestCase):
    def test_claimable_states(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "nope"
            self.assertTrue(_mod.claimable(missing))
            foreign = Path(td) / "foreign-skill"
            foreign.mkdir()
            self.assertFalse(_mod.claimable(foreign))
            managed = Path(td) / "managed-skill"
            managed.mkdir()
            (managed / _mod.ORIGIN).write_text("{}", encoding="utf-8")
            self.assertTrue(_mod.claimable(managed))


if __name__ == "__main__":
    unittest.main()
