"""Tests for cdo-setup backlog-add.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "backlog-add.py"


def run_add(orch: Path, *extra):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), *extra],
        capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestBacklogAdd(unittest.TestCase):
    def test_prefix_mints_sequential_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            proc, data = run_add(orch, "--backlog", "product",
                                 "--key-prefix", "P", "--title", "First")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["key"], "P1")
            proc, data = run_add(orch, "--backlog", "product",
                                 "--key-prefix", "P", "--title", "Second")
            self.assertEqual(data["key"], "P2")
            body = (orch / "backlogs" / "product.md").read_text(
                encoding="utf-8")
            self.assertIn("- [ ] P1 — First", body)
            self.assertIn("- [ ] P2 — Second", body)

    def test_fields_append_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_add(Path(tmp), "--backlog", "code",
                                 "--key", "13-01-thing", "--title", "T",
                                 "--field", "size=lite", "--field", "deps=none")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("| size: lite | deps: none", data["line"])

    def test_retired_s_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_add(Path(tmp), "--backlog", "code",
                                 "--key", "S9", "--title", "T")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("S{n}", data["errors"][0])

    def test_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp)
            run_add(orch, "--backlog", "code", "--key", "13-01-x", "--title", "A")
            proc, data = run_add(orch, "--backlog", "code",
                                 "--key", "13-01-x", "--title", "B")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("already exists", data["errors"][0])

    def test_no_key_or_prefix_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_add(Path(tmp), "--backlog", "code", "--title", "T")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("--key or --key-prefix", data["errors"][0])

    def test_bad_field_pair_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_add(Path(tmp), "--backlog", "code",
                                 "--key", "k1", "--title", "T",
                                 "--field", "noequals")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("name=value", data["errors"][0])

    def test_dept_module_name_maps_to_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_add(Path(tmp), "--backlog", "cdo-growth",
                                 "--key-prefix", "CT", "--title", "Post")
            self.assertEqual(proc.returncode, 0)
            self.assertTrue((Path(tmp) / "backlogs" / "growth.md").is_file())


if __name__ == "__main__":
    unittest.main()
