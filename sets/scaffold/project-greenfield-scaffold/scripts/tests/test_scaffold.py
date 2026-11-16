"""Tests for scaffold.py — flag filtering, token substitution, deps rendering."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scaffold.py"


def run_scaffold(target: Path, *extra: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(target), "--name", "Acme App",
         "--site-url", "https://acme.example.com", *extra],
        capture_output=True, text=True,
    )
    assert proc.returncode in (0, 1), f"exit {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


class TestScaffold(unittest.TestCase):
    def test_full_spine(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            report = run_scaffold(target)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["modules"]["disabled"], [])

            # tokens substituted
            pkg = json.loads((target / "package.json").read_text())
            self.assertEqual(pkg["name"], "acme-app")
            self.assertIn("nuxt", pkg["dependencies"])
            self.assertIn("vuetify", pkg["devDependencies"])
            self.assertIn("better-auth", pkg["dependencies"])

            # flag markers never emitted
            api = (target / "server/api.ts").read_text()
            self.assertNotIn("@flag", api)
            self.assertIn("authRouter", api)
            self.assertIn("emailRouter", api)

            nuxt = (target / "nuxt.config.ts").read_text()
            self.assertIn("Acme App", nuxt)
            self.assertIn("https://acme.example.com", nuxt)
            self.assertNotIn("@flag", nuxt)

            # rules copied to docs/rules as passive docs (no .devin/rules)
            self.assertTrue((target / "docs/rules/code-style-guide.md").exists())
            self.assertFalse((target / ".devin").exists())
            guide = (target / "docs/rules/code-style-guide.md").read_text()
            self.assertNotIn("trigger:", guide)

            # AGENTS.md emitted with the rules pointer
            agents = (target / "AGENTS.md").read_text()
            self.assertIn("docs/rules/code-style-guide.md", agents)
            self.assertNotIn("@flag", agents)

    def test_minimal(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            report = run_scaffold(target, "--minimal")
            self.assertEqual(report["status"], "pass")
            disabled = set(report["modules"]["disabled"])
            self.assertIn("auth", disabled)
            self.assertIn("db", disabled)

            self.assertFalse((target / "auth.ts").exists())
            self.assertFalse((target / "server/db").exists())
            self.assertFalse((target / "netlify.toml").exists())
            # docs site module off — but rules module stays on under --minimal,
            # so docs/ exists holding only the rules subtree
            self.assertFalse((target / "docs/index.md").exists())
            self.assertTrue((target / "docs/rules/code-style-guide.md").exists())
            self.assertTrue((target / "vitest.config.ts").exists())

            pkg = json.loads((target / "package.json").read_text())
            self.assertNotIn("better-auth", pkg["dependencies"])
            self.assertNotIn("drizzle-orm", pkg["dependencies"])
            self.assertNotIn("db:generate", pkg["scripts"])
            self.assertIn("test:run", pkg["scripts"])

            api = (target / "server/api.ts").read_text()
            self.assertNotIn("authRouter", api)
            self.assertNotIn("@flag", api)

    def test_skip_db_cascades_auth(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            report = run_scaffold(target, "--skip", "db")
            disabled = set(report["modules"]["disabled"])
            self.assertIn("db", disabled)
            self.assertIn("auth", disabled)     # auth requires db
            self.assertIn("billing", disabled)  # billing requires auth
            self.assertIn("auth", report["modules"]["auto_disabled"])

    def test_non_empty_target_refused(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            target.mkdir()
            (target / "existing.txt").write_text("x")
            report = run_scaffold(target)
            self.assertEqual(report["status"], "fail")

    def test_state_artifact_and_residue(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            report = run_scaffold(target)
            self.assertEqual(report["result"]["residue"], [])
            state = json.loads((target / ".scaffold-report.json").read_text())
            self.assertEqual(state["script"], "scaffold")

            status = run_scaffold(target, "--status")
            self.assertEqual(status["status"], "pass")
            self.assertTrue(status["key_files"]["package.json"])
            self.assertFalse(status["key_files"]["node_modules"])

    def test_skip_rules(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target, "--skip", "rules")
            self.assertFalse((target / "docs/rules").exists())
            agents = (target / "AGENTS.md").read_text()
            self.assertNotIn("docs/rules", agents)
            self.assertNotIn("@flag", agents)

    def test_skip_tests(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target, "--skip", "tests")
            self.assertFalse((target / "vitest.config.ts").exists())
            self.assertFalse((target / "playwright.config.ts").exists())
            self.assertFalse((target / "tests").exists())
            pkg = json.loads((target / "package.json").read_text())
            self.assertNotIn("vitest", pkg["devDependencies"])
            self.assertNotIn("test:run", pkg["scripts"])
            hook = (target / "scripts/pre-push-build-validation.sh").read_text()
            self.assertNotIn("test:run", hook)


if __name__ == "__main__":
    unittest.main()
