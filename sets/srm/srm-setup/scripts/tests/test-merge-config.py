#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Tests for merge-config.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import yaml

_script_path = Path(__file__).resolve().parent.parent / "merge-config.py"
_spec = spec_from_file_location("merge_config", _script_path)
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)


class TestLoaders(unittest.TestCase):
    def test_load_yaml_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.yaml"
            p.write_text("a: 1\nb: [x, y]\n", encoding="utf-8")
            self.assertEqual(_mod.load_yaml_file(str(p)), {"a": 1, "b": ["x", "y"]})

    def test_load_yaml_empty_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.yaml"
            p.write_text("", encoding="utf-8")
            self.assertEqual(_mod.load_yaml_file(str(p)), {})

    def test_load_json_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.json"
            p.write_text(json.dumps({"k": "v"}), encoding="utf-8")
            self.assertEqual(_mod.load_json_file(str(p)), {"k": "v"})


class TestLegacyDefaults(unittest.TestCase):
    def test_answers_win_over_legacy(self):
        answers = {"core": {"user_name": "Afiq"}, "module": {"x": "new"}}
        merged = _mod.apply_legacy_defaults(answers, {"user_name": "Old"}, {"x": "old", "y": 1})
        self.assertEqual(merged["core"]["user_name"], "Afiq")
        self.assertEqual(merged["module"]["x"], "new")

    def test_legacy_fills_missing(self):
        answers = {"core": {}, "module": {}}
        merged = _mod.apply_legacy_defaults(answers, {"user_name": "Old"}, {"x": "old"})
        self.assertEqual(merged["core"]["user_name"], "Old")
        self.assertEqual(merged["module"]["x"], "old")


class TestMetadata(unittest.TestCase):
    def test_extract_module_metadata(self):
        mod = yaml.safe_load(
            "code: srm\nname: Skills Repo Manager\nmodule_version: 1.0.0\ndefault_selected: false\n"
        )
        meta = _mod.extract_module_metadata(mod)
        self.assertEqual(meta.get("name"), "Skills Repo Manager")
        self.assertEqual(meta.get("version"), "1.0.0")
        self.assertNotIn("code", meta)


if __name__ == "__main__":
    unittest.main()
