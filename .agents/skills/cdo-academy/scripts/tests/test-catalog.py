"""Tests for catalog.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / "catalog.py"


def run(*args):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def add(academy, **kw):
    args = ["--academy-dir", str(academy), "add",
            "--track", kw.get("track", "frontend-engineering"),
            "--course", kw.get("course", "typescript"),
            "--module-id", kw.get("module_id", "basic-types"),
            "--title", kw.get("title", "Basic Types"),
            "--level", kw.get("level", "fundamentals")]
    if kw.get("source_story"):
        args += ["--source-story", kw["source_story"]]
    return run(*args)


class TestCatalog(unittest.TestCase):
    def test_add_registers_nested_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            academy = Path(tmp) / "docs" / "academy"
            proc, data = add(academy, source_story="S1")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "added")
            cat = yaml.safe_load((academy / "catalog.yaml").read_text())
            mod = cat["tracks"]["frontend-engineering"]["courses"]["typescript"]["modules"]["basic-types"]
            self.assertEqual(mod["level"], "fundamentals")
            self.assertEqual(mod["source_stories"], ["S1"])

    def test_add_merges_source_stories(self):
        with tempfile.TemporaryDirectory() as tmp:
            academy = Path(tmp) / "docs" / "academy"
            add(academy, source_story="S1")
            add(academy, source_story="S4")
            cat = yaml.safe_load((academy / "catalog.yaml").read_text())
            mod = cat["tracks"]["frontend-engineering"]["courses"]["typescript"]["modules"]["basic-types"]
            self.assertEqual(mod["source_stories"], ["S1", "S4"])

    def test_list_emits_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            academy = Path(tmp) / "docs" / "academy"
            add(academy)
            proc, data = run("--academy-dir", str(academy), "list")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("frontend-engineering",
                          data["catalog"]["tracks"])

    def test_file_gap_writes_backlog_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "docs" / "orchestration"
            orch.mkdir(parents=True)
            proc, data = run("--orchestration-dir", str(orch), "file-gap",
                             "--concept-id", "ssr-hydration",
                             "--title", "SSR hydration",
                             "--track", "frontend-engineering",
                             "--course", "nuxt", "--level", "advanced",
                             "--sources", "S12,S13")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "filed")
            self.assertEqual(data["key"], "C1")
            backlog = (orch / "backlogs" / "curriculum.md").read_text()
            self.assertIn("teach: SSR hydration", backlog)
            self.assertIn("concept-id: ssr-hydration", backlog)
            self.assertIn("course: nuxt", backlog)
            self.assertIn("level: advanced", backlog)

    def test_file_gap_dedupes_and_allocates_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "docs" / "orchestration"
            orch.mkdir(parents=True)
            run("--orchestration-dir", str(orch), "file-gap",
                "--concept-id", "api", "--title", "API",
                "--track", "t", "--course", "c")
            proc, data = run("--orchestration-dir", str(orch), "file-gap",
                             "--concept-id", "api", "--title", "API",
                             "--track", "t", "--course", "c")
            self.assertEqual(data["status"], "already-filed")
            # 'graphql-api' must not be swallowed by the existing 'api' line
            proc, data = run("--orchestration-dir", str(orch), "file-gap",
                             "--concept-id", "graphql-api", "--title", "GQL",
                             "--track", "t", "--course", "c")
            self.assertEqual(data["status"], "filed")
            self.assertEqual(data["key"], "C2")

    def test_missing_required_flags_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run("--academy-dir", str(Path(tmp) / "a"), "add",
                             "--track", "t")
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(data["errors"])


if __name__ == "__main__":
    unittest.main()
