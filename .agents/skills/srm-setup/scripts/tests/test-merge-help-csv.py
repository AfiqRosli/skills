#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Tests for merge-help-csv.py."""

from __future__ import annotations

import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_script_path = Path(__file__).resolve().parent.parent / "merge-help-csv.py"
_spec = spec_from_file_location("merge_help_csv", _script_path)
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CSV = "module,skill,display-name\nSRM,srm-sync,Sync\nOther,other-x,Thing\n"


class TestCsvIo(unittest.TestCase):
    def test_read_csv_rows(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.csv"
            p.write_text(CSV, encoding="utf-8")
            header, rows = _mod.read_csv_rows(str(p))
            self.assertEqual(header[0], "module")
            self.assertEqual(len(rows), 2)

    def test_read_missing_returns_empty(self):
        header, rows = _mod.read_csv_rows("does/not/exist.csv")
        self.assertEqual((header, rows), ([], []))

    def test_extract_module_codes(self):
        codes = _mod.extract_module_codes([["SRM", "a"], ["Other", "b"], ["", "c"], ["SRM", "d"]])
        self.assertEqual(codes, {"SRM", "Other"})

    def test_filter_rows_removes_module(self):
        out = _mod.filter_rows([["SRM", "a"], ["Other", "b"], ["SRM", "c"]], "SRM")
        self.assertEqual(out, [["Other", "b"]])

    def test_write_then_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "out.csv"
            _mod.write_csv(str(p), ["h1", "h2"], [["a", "b"]])
            header, rows = _mod.read_csv_rows(str(p))
            self.assertEqual(header, ["h1", "h2"])
            self.assertEqual(rows, [["a", "b"]])


class TestLegacyCleanup(unittest.TestCase):
    def test_cleanup_legacy_csvs(self):
        with tempfile.TemporaryDirectory() as td:
            for sub in ("srm", "core", "other"):
                d = Path(td) / sub
                d.mkdir()
                (d / "module-help.csv").write_text("x\n", encoding="utf-8")
            deleted = _mod.cleanup_legacy_csvs(td, "srm")
            self.assertEqual(len(deleted), 2)
            self.assertTrue((Path(td) / "other" / "module-help.csv").exists())


class TestTokenGuard(unittest.TestCase):
    def test_rejects_unresolved_project_root(self):
        with self.assertRaises(SystemExit):
            _mod.reject_unresolved_paths([("--config-path", "{project-root}/_bmad/config.yaml")])

    def test_accepts_resolved_paths(self):
        _mod.reject_unresolved_paths([("--config-path", "C:/real/_bmad/config.yaml")])


if __name__ == "__main__":
    unittest.main()
