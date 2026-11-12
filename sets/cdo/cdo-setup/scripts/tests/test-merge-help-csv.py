"""Smoke tests for merge-help-csv.py — run: uv run -m unittest discover -s tests"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "merge-help-csv.py"
SOURCE_CSV = Path(__file__).parent.parent.parent / "assets" / "module-help.csv"


def run_merge(target: Path, skills_dir: Path = None):
    cmd = [
        sys.executable, str(SCRIPT),
        "--target", str(target),
        "--source", str(SOURCE_CSV),
        "--legacy-dir", str(target.parent),
        "--module-code", "cdo",
    ]
    if skills_dir:
        cmd += ["--installed-dirs", str(skills_dir)]
    return subprocess.run(cmd, capture_output=True, text=True)


class TestMergeHelpCsv(unittest.TestCase):
    def test_registers_all_cdo_skills_unfiltered(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "module-help.csv"
            proc = run_merge(target)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = target.read_text(encoding="utf-8")
            for skill in ("cdo-orchestrator", "cdo-setup", "cdo-review", "cdo-align",
                          "cdo-batch", "cdo-watch", "cdo-handoff"):
                self.assertIn(skill, text)

    def test_installed_dirs_filters_missing_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / ".agents" / "skills"
            for s in ("cdo-setup", "cdo-orchestrator"):
                (skills / s).mkdir(parents=True)
                (skills / s / "SKILL.md").write_text("x", encoding="utf-8")
            target = Path(tmp) / "module-help.csv"
            proc = run_merge(target, skills_dir=skills)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = target.read_text(encoding="utf-8")
            self.assertIn("cdo-setup", text)
            self.assertIn("cdo-orchestrator", text)
            self.assertNotIn("cdo-review", text)
            self.assertNotIn("cdo-batch", text)

    def test_idempotent_no_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "module-help.csv"
            run_merge(target)
            proc = run_merge(target)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = target.read_text(encoding="utf-8")
            self.assertEqual(text.count("cdo-orchestrator"), 1)


if __name__ == "__main__":
    unittest.main()
