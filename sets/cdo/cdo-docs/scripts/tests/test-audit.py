"""Tests for audit.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "audit.py"
DETECT = Path(__file__).parent.parent / "detect-docs.py"


def run(orch, root):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch),
         "--project-root", str(root)], capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def detect(root, orch):
    subprocess.run(
        [sys.executable, str(DETECT), "--project-root", str(root),
         "--orchestration-dir", str(orch)],
        capture_output=True, text=True)


def make_vitepress(root, links):
    docs = root / "docs"
    (docs / ".vitepress").mkdir(parents=True)
    cfg = "".join(f'{{ text: "x", link: "{l}" }},' for l in links)
    (docs / ".vitepress" / "config.ts").write_text(
        f"export default {{ themeConfig: {{ sidebar: {{ '/': [{cfg}] }} }} }};",
        encoding="utf-8")
    return docs


class TestAudit(unittest.TestCase):
    def test_orphans_and_broken_nav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "orch"
            orch.mkdir()
            docs = make_vitepress(root, ["/guide/intro", "/gone"])
            (docs / "guide").mkdir(parents=True)
            (docs / "guide" / "intro.md").write_text("# i", encoding="utf-8")
            (docs / "hidden.md").write_text("# h", encoding="utf-8")
            detect(root, orch)
            proc, data = run(orch, root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["orphans"], ["hidden.md"])
            self.assertEqual(data["broken_nav"], ["/gone"])

    def test_dir_link_covers_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "orch"
            orch.mkdir()
            docs = make_vitepress(root, ["/guide/"])
            (docs / "guide").mkdir(parents=True)
            (docs / "guide" / "index.md").write_text("# i", encoding="utf-8")
            detect(root, orch)
            proc, data = run(orch, root)
            self.assertEqual(data["orphans"], [])

    def test_auto_zone_pages_not_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "orch"
            orch.mkdir()
            docs = make_vitepress(root, [])
            (docs / ".vitepress" / "config.ts").write_text(
                'import { readdirSync } from "node:fs";\n'
                'const d = new URL("../devlog", import.meta.url);\n'
                "readdirSync(d);\n", encoding="utf-8")
            dl = docs / "devlog" / "x"
            dl.mkdir(parents=True)
            (dl / "index.md").write_text("# x", encoding="utf-8")
            detect(root, orch)
            proc, data = run(orch, root)
            self.assertIn("devlog", data["auto_zones"])
            self.assertEqual(data["orphans"], [])

    def test_mdx_page_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "orch"
            orch.mkdir()
            docs = make_vitepress(root, ["/visible"])
            (docs / "visible.md").write_text("# v", encoding="utf-8")
            (docs / "hidden.mdx").write_text("# h", encoding="utf-8")
            detect(root, orch)
            proc, data = run(orch, root)
            self.assertEqual(data["orphans"], ["hidden.mdx"])

    def test_missing_profile_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "orch"
            orch.mkdir()
            proc, data = run(orch, root)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(data["status"], "blocked")

    def test_plain_docs_all_covered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "orch"
            orch.mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "a.md").write_text("# a", encoding="utf-8")
            detect(root, orch)
            proc, data = run(orch, root)
            self.assertEqual(data["status"], "audited")
            self.assertEqual(data["orphans"], [])
            self.assertEqual(data["covered"], 1)


if __name__ == "__main__":
    unittest.main()
