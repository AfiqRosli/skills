"""Tests for cdo-setup scaffold.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scaffold.py"
SEEDS = Path(__file__).parent.parent.parent / "assets" / "seeds"


def run_scaffold(root: Path, extra=()):
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--project-root", str(root),
            "--seeds", str(SEEDS), *extra,
        ],
        capture_output=True,
        text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestScaffold(unittest.TestCase):
    def test_creates_core_tree_dept_backlogs_conditional(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_scaffold(Path(tmp))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            orch = Path(tmp) / "docs" / "orchestration"
            for f in ("doctrine.md", "flow-ledger.yaml", "alignment-checklist.md",
                      "frago-inbox.md", "handover.md"):
                self.assertTrue((orch / f).is_file(), f)
            self.assertTrue((orch / "alignment").is_dir())
            self.assertTrue((orch / "backlogs" / "code.md").is_file())
            self.assertTrue((orch / "backlogs" / "README.md").is_file())
            # dept backlogs skipped without --dept-modules
            self.assertFalse((orch / "backlogs" / "content.md").exists())
            self.assertFalse((orch / "backlogs" / "curriculum.md").exists())
            self.assertIn("backlogs/content.md", data["skipped"])

    def test_dept_backlogs_seed_when_module_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_scaffold(Path(tmp), ["--dept-modules", "cdo-growth,cdo-academy"])
            self.assertEqual(proc.returncode, 0)
            orch = Path(tmp) / "docs" / "orchestration"
            self.assertTrue((orch / "backlogs" / "content.md").is_file())
            self.assertTrue((orch / "backlogs" / "curriculum.md").is_file())

    def test_unknown_dept_gets_bare_backlog(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_scaffold(Path(tmp), ["--dept-modules", "cdo-legal"])
            orch = Path(tmp) / "docs" / "orchestration"
            self.assertTrue((orch / "backlogs" / "legal.md").is_file())

    def test_idempotent_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_scaffold(Path(tmp))
            marker = Path(tmp) / "docs" / "orchestration" / "doctrine.md"
            marker.write_text("CUSTOMIZED", encoding="utf-8")

            proc, data = run_scaffold(Path(tmp))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "CUSTOMIZED")
            existing = [p.replace("\\", "/") for p in data["existing"]]
            self.assertIn("docs/orchestration/doctrine.md", existing)

    def test_reseed_overwrites_one_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_scaffold(Path(tmp))
            marker = Path(tmp) / "docs" / "orchestration" / "doctrine.md"
            marker.write_text("CORRUPTED", encoding="utf-8")

            proc, data = run_scaffold(Path(tmp), ["--reseed", "doctrine.md"])
            self.assertEqual(proc.returncode, 0)
            self.assertNotEqual(marker.read_text(encoding="utf-8"), "CORRUPTED")
            self.assertIn("Doctrine", marker.read_text(encoding="utf-8"))

    def test_setup_log_appends_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_scaffold(Path(tmp), ["--mode", "fresh-install", "--version", "0.1.0"])
            run_scaffold(Path(tmp), ["--mode", "upgrade", "--version", "0.2.0"])
            log = Path(tmp) / "docs" / "orchestration" / "setup-log.md"
            text = log.read_text(encoding="utf-8")
            self.assertIn("fresh-install", text)
            self.assertIn("upgrade", text)
            self.assertIn("0.2.0", text)

    def test_missing_seeds_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--project-root", tmp,
                    "--seeds", str(Path(tmp) / "nope"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)

    def test_unresolved_project_root_token_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--project-root", tmp,
                    "--seeds", str(SEEDS),
                    "--orchestration-dir", "{project-root}/docs/orchestration",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("project-root", proc.stdout)
            self.assertFalse((Path(tmp) / "{project-root}").exists())

    def _answers(self, tmp, **module):
        p = Path(tmp) / "answers.json"
        p.write_text(json.dumps({"core": {}, "module": module}),
                     encoding="utf-8")
        return str(p)

    def test_answers_drives_orch_dir_and_backlog_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers = self._answers(
                tmp,
                orchestration_dir="{project-root}/ops/orch",
                backlog_map={"code": "backlogs/code.md",
                             "growth": "backlogs/content.md"})
            proc, data = run_scaffold(Path(tmp), ["--answers", answers])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            orch = Path(tmp) / "ops" / "orch"
            self.assertTrue((orch / "doctrine.md").is_file())
            # backlog_map — not --dept-modules — decides dept backlogs
            self.assertTrue((orch / "backlogs" / "content.md").is_file())

    def test_answers_creates_configured_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers = self._answers(
                tmp,
                devlog_dir="{project-root}/logs/devlog",
                sprint_status_path="{project-root}/out/sprint.yaml")
            proc, data = run_scaffold(Path(tmp), ["--answers", answers])
            self.assertEqual(proc.returncode, 0)
            # dir-shaped values get created; file-shaped values do not
            self.assertTrue((Path(tmp) / "logs" / "devlog").is_dir())
            self.assertFalse((Path(tmp) / "out" / "sprint.yaml").exists())

    def test_report_copied_into_orch(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "answers.json.report.json"
            report.write_text('{"proposed": []}', encoding="utf-8")
            proc, data = run_scaffold(Path(tmp), ["--report", str(report)])
            self.assertEqual(proc.returncode, 0)
            out = Path(tmp) / "docs" / "orchestration" / "setup-report.json"
            self.assertTrue(out.is_file())
            log = (Path(tmp) / "docs" / "orchestration" / "setup-log.md") \
                .read_text(encoding="utf-8")
            self.assertIn("report=setup-report.json", log)

    def test_module_yaml_supplies_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            myaml = Path(tmp) / "module.yaml"
            myaml.write_text("module_version: 9.9.9\n", encoding="utf-8")
            proc, _ = run_scaffold(Path(tmp),
                                   ["--module-yaml", str(myaml),
                                    "--mode", "upgrade"])
            self.assertEqual(proc.returncode, 0)
            log = (Path(tmp) / "docs" / "orchestration" / "setup-log.md") \
                .read_text(encoding="utf-8")
            self.assertIn("version=9.9.9", log)


if __name__ == "__main__":
    unittest.main()
