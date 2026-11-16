"""Tests for detect-docs.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "detect-docs.py"


def run(root, orch=None):
    cmd = [sys.executable, str(SCRIPT), "--project-root", str(root)]
    if orch:
        cmd += ["--orchestration-dir", str(orch)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_vitepress(root, sidebar_links=None):
    docs = root / "docs"
    cfg_dir = docs / ".vitepress"
    cfg_dir.mkdir(parents=True)
    links = "".join(
        f'{{ text: "{t}", link: "{l}" }},' for t, l in (sidebar_links or []))
    (cfg_dir / "config.ts").write_text(
        'import { defineConfig } from "vitepress";\n'
        "export default defineConfig({ themeConfig: {\n"
        f"  sidebar: {{ '/a/': [ {links} ] }},\n"
        "}});\n", encoding="utf-8")
    (root / "package.json").write_text(json.dumps({
        "scripts": {"docs:dev": "vitepress dev docs",
                    "docs:build": "vitepress build docs"},
        "devDependencies": {"vitepress": "^1.0.0"}}), encoding="utf-8")
    (root / "bun.lock").write_text("", encoding="utf-8")
    return docs


class TestDetect(unittest.TestCase):
    def test_vitepress_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_vitepress(root)
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            p = data["profile"]
            self.assertEqual(p["framework"], "vitepress")
            self.assertEqual(p["docs_root"], "docs")
            self.assertEqual(p["nav_config"], "docs/.vitepress/config.ts")
            self.assertEqual(p["nav_kind"], "config")
            self.assertEqual(p["dev_command"], "bun run docs:dev")
            self.assertEqual(p["build_command"], "bun run docs:build")
            self.assertEqual(p["package_manager"], "bun")

    def test_vitepress_auto_zones_from_fs_sidebar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = make_vitepress(root)
            (docs / ".vitepress" / "config.ts").write_text(
                'import { readdirSync } from "node:fs";\n'
                'const devlog = new URL("../orchestration/devlog", '
                "import.meta.url);\nreaddirSync(devlog);\n",
                encoding="utf-8")
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("orchestration/devlog",
                          data["profile"]["auto_zones"])

    def test_mkdocs_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mkdocs.yml").write_text(
                "site_name: T\ndocs_dir: documentation\n", encoding="utf-8")
            (root / "documentation").mkdir()
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            p = data["profile"]
            self.assertEqual(p["framework"], "mkdocs")
            self.assertEqual(p["docs_root"], "documentation")
            self.assertEqual(p["nav_kind"], "yaml-nav")
            self.assertEqual(p["build_command"], "mkdocs build")

    def test_docusaurus_filesystem_nav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docusaurus.config.ts").write_text("export default {};",
                                                      encoding="utf-8")
            (root / "package.json").write_text(json.dumps(
                {"dependencies": {"@docusaurus/core": "^3.0.0"}}),
                encoding="utf-8")
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            p = data["profile"]
            self.assertEqual(p["framework"], "docusaurus")
            self.assertEqual(p["nav_kind"], "filesystem")

    def test_plain_docs_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "readme.md").write_text("# x", encoding="utf-8")
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["profile"]["framework"], "plain")

    def test_none_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run(Path(tmp))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["profile"]["framework"], "none")

    def test_multiple_vitepress_roots_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_vitepress(root)
            other = root / "packages" / "web" / "docs" / ".vitepress"
            other.mkdir(parents=True)
            (other / "config.ts").write_text("export default {};",
                                           encoding="utf-8")
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            extra = data["profile"]["additional_roots"]
            self.assertEqual(len(extra), 1)
            self.assertIn("docs", extra[0])

    def test_mdx_counts_as_plain_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "page.mdx").write_text("# x", encoding="utf-8")
            proc, data = run(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["profile"]["framework"], "plain")

    def test_profile_written_to_orchestration_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            make_vitepress(root)
            proc, data = run(root, orch)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((orch / "docs-profile.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
