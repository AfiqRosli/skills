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

    def test_record_merges_state(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target)
            run_scaffold(target, "--record", '{"adaptations": ["shimmed nuxt-elysia"]}')
            run_scaffold(target, "--record",
                         '{"adaptations": ["bumped vitest major"], "run_status": "blocked", "reason": "no compatible release"}')
            state = json.loads((target / ".scaffold-report.json").read_text())
            self.assertEqual(state["adaptations"],
                             ["shimmed nuxt-elysia", "bumped vitest major"])
            self.assertEqual(state["run_status"], "blocked")
            self.assertEqual(state["reason"], "no compatible release")
            self.assertEqual(state["script"], "scaffold")  # original report preserved

    def test_render_preserves_recorded_state(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            # record before render — --record must create the target
            result = run_scaffold(target, "--record",
                                  '{"assumptions": ["name defaulted to dir"]}')
            self.assertEqual(result["status"], "pass")
            state = json.loads((target / ".scaffold-report.json").read_text())
            self.assertEqual(state["assumptions"], ["name defaulted to dir"])

            # render over the recorded state — assumptions must survive
            target2 = Path(td) / "proj2"
            run_scaffold(target2)
            run_scaffold(target2, "--record",
                         '{"adaptations": ["shimmed x"], "verify": {"status": "pass"}, "run_status": "complete"}')
            run_scaffold(target2, "--force")
            state = json.loads((target2 / ".scaffold-report.json").read_text())
            self.assertEqual(state["adaptations"], ["shimmed x"])
            self.assertEqual(state["verify"], {"status": "pass"})
            self.assertEqual(state["run_status"], "complete")
            self.assertIsInstance(state["result"]["files_written"], list)

    def test_record_warns_unknown_keys(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target)
            result = run_scaffold(target, "--record",
                                  '{"assumptions": ["a"], "runstatus": "blocked"}')
            self.assertEqual(result["status"], "pass")
            self.assertTrue(any("runstatus" in w for w in result["warnings"]))

    def test_record_verify_is_a_known_key(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target)
            result = run_scaffold(target, "--record",
                                  '{"verify": {"status": "pass"}}')
            self.assertFalse(any("verify" in w for w in result.get("warnings", [])))
            state = json.loads((target / ".scaffold-report.json").read_text())
            self.assertEqual(state["verify"]["status"], "pass")

    def test_record_pasted_report_self_filters(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target)
            # a full pasted report drops its render keys and keeps only
            # the classifier-read ones — no hand-extraction needed
            run_scaffold(target, "--record",
                         '{"script": "scaffold", "timestamp": "2020-01-01",'
                         ' "result": {"files_written": ["bogus"]},'
                         ' "verify": {"status": "pass"}, "run_status": "complete"}')
            state = json.loads((target / ".scaffold-report.json").read_text())
            self.assertEqual(state["verify"]["status"], "pass")
            self.assertEqual(state["run_status"], "complete")
            self.assertIsInstance(state["result"]["files_written"], list)
            self.assertNotEqual(state["result"]["files_written"], ["bogus"])

    def test_stale_verify_after_rerender(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target)
            run_scaffold(target, "--record",
                         '{"verify": {"status": "pass", "timestamp": "2020-01-01T00:00:00+00:00"}}')
            run_scaffold(target, "--force")
            status = run_scaffold(target, "--status")
            self.assertEqual(status["resume_hint"],
                             "verify passed before last re-render — re-run verify")

    def test_status_prior_report_is_compact(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target)
            status = run_scaffold(target, "--status")
            result = status["prior_report"]["result"]
            self.assertIsInstance(result["files_written"], int)
            self.assertIsInstance(result["files_excluded"], int)

    def test_resume_hint_run_status_complete(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target)
            run_scaffold(target, "--record", '{"run_status": "complete"}')
            status = run_scaffold(target, "--status")
            self.assertEqual(status["resume_hint"], "run complete — done")

    def test_resume_hint_prefers_persisted_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target)
            state_file = target / ".scaffold-report.json"
            state = json.loads(state_file.read_text())
            state["verify"] = {"status": "pass"}
            state_file.write_text(json.dumps(state))
            # node_modules absent — the file-state ladder alone would say
            # "scaffold rendered"; the persisted verify outcome must win
            status = run_scaffold(target, "--status")
            self.assertEqual(status["resume_hint"], "verify passed — done")

    def test_init_env_secret_honesty(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target)
            result = run_scaffold(target, "--init-env")
            self.assertTrue(result["secret_generated"])
            self.assertNotIn("generate-a-long-random-string",
                             (target / ".env").read_text())

    def test_init_env_no_secret_when_auth_off(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            run_scaffold(target, "--skip", "db")  # cascades auth off
            result = run_scaffold(target, "--init-env")
            self.assertEqual(result["status"], "pass")
            self.assertFalse(result["secret_generated"])
            self.assertNotIn("BETTER_AUTH_SECRET", (target / ".env").read_text())

    def test_check_drift_requires_package_json(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "proj"
            result = run_scaffold(target, "--check-drift")
            self.assertEqual(result["status"], "fail")

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
