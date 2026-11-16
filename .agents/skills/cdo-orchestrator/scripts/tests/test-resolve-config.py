"""Tests for resolve-config.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "resolve-config.py"


def run_resolve(root: Path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root)],
        capture_output=True, text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestResolveConfig(unittest.TestCase):
    def test_no_cdo_section_reports_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_resolve(Path(tmp))
            self.assertEqual(proc.returncode, 0)
            self.assertFalse(data["installed"])
            # defaults still resolve
            self.assertEqual(data["config"]["ship_target"], "preview")
            orch = data["resolved_paths"]["orchestration_dir"].replace("\\", "/")
            self.assertIn("docs/orchestration", orch)

    def test_cdo_section_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_bmad").mkdir()
            (root / "_bmad" / "config.yaml").write_text(
                "cdo:\n  orchestration_dir: docs/ops\n  stall_timeout_minutes: 90\n"
                "  backlog_map:\n    code: backlogs/code.md\n",
                encoding="utf-8",
            )
            (root / "_bmad" / "config.user.yaml").write_text(
                "user_name: Afiq\ncommunication_language: English\n", encoding="utf-8"
            )
            proc, data = run_resolve(root)
            self.assertTrue(data["installed"])
            self.assertEqual(data["config"]["stall_timeout_minutes"], 90)
            self.assertEqual(data["config"]["user_name"], "Afiq")
            # resolved path points at real project dir
            self.assertTrue(data["resolved_paths"]["orchestration_dir"].endswith("docs\\ops")
                            or data["resolved_paths"]["orchestration_dir"].endswith("docs/ops"))
            self.assertEqual(data["config"]["backlog_map"]["code"], "backlogs/code.md")

    def test_missing_root_errors(self):
        proc, _ = run_resolve(Path("/nonexistent-xyz"))
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
