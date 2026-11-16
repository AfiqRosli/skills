#!/usr/bin/env python3
"""Tests for backlog-add.py + resolve-item.py."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent


def run(script, *args):
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_orch(root: Path):
    orch = root / "docs" / "orchestration"
    (orch / "backlogs").mkdir(parents=True)
    return orch


class TestBacklogAdd(unittest.TestCase):
    def test_allocates_next_key_and_canonical_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "backlogs" / "product.md").write_text(
                "# Product\n\n- [ ] P1 — first\n", encoding="utf-8")
            proc, data = run("backlog-add.py", "--orchestration-dir", str(orch),
                             "--backlog", "product", "--key-prefix", "P",
                             "--title", "second", "--field", "size=lite",
                             "--field", "deps=P1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["key"], "P2")
            self.assertIn("size: lite", data["line"])
            self.assertIn("deps: P1", data["line"])

    def test_creates_missing_backlog(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run("backlog-add.py", "--orchestration-dir", str(orch),
                             "--backlog", "quality", "--key-prefix", "Q",
                             "--title", "write e2e suite")
            self.assertEqual(proc.returncode, 0)
            self.assertTrue((orch / "backlogs" / "quality.md").is_file())

    def test_dept_name_resolves_to_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run("backlog-add.py", "--orchestration-dir", str(orch),
                             "--backlog", "cdo-quality", "--key-prefix", "Q",
                             "--title", "x")
            self.assertEqual(data["backlog"], "backlogs/quality.md")


class TestResolveItem(unittest.TestCase):
    def test_resolves_across_state_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            (orch / "backlogs" / "code.md").write_text(
                "- [x] S1 — done thing\n- [ ] S12 — other\n", encoding="utf-8")
            (orch / "flow-ledger.yaml").write_text(
                "stories:\n  S1: {status: done}\nsignals:\n"
                "  - {type: stall, key: S1, at: '2026-01-01T00:00'}\n",
                encoding="utf-8")
            card_dir = orch / "alignment" / "2026" / "01" / "01"
            card_dir.mkdir(parents=True)
            (card_dir / "S1.md").write_text("# card", encoding="utf-8")
            proc, data = run("resolve-item.py",
                             "--orchestration-dir", str(orch), "S1")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["ledger"]["status"], "done")
            self.assertEqual(data["card_body"], "# card")
            # token-boundary: S1 must not match the S12 line
            self.assertIn("[x] S1", data["backlog"]["line"])
            self.assertEqual(len(data["signals"]), 1)

    def test_missing_key_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, _ = run("resolve-item.py",
                          "--orchestration-dir", str(orch), "ZZZ")
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
