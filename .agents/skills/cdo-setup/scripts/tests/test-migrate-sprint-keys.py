"""Tests for cdo-setup migrate-sprint-keys.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "migrate-sprint-keys.py"


def fixture(tmp: str):
    """Minimal project: sprint yaml with epic-13 block + a code backlog
    carrying two legacy S{n} keys."""
    root = Path(tmp)
    impl = root / "_bmad-output" / "implementation-artifacts"
    impl.mkdir(parents=True)
    (impl / "sprint-status-Beta-2026.01.01.yaml").write_text(
        "development_status:\n"
        "  epic-13: in-progress\n"
        "retrospective: pending\n", encoding="utf-8")
    orch = root / "docs" / "orchestration"
    (orch / "backlogs").mkdir(parents=True)
    (orch / "backlogs" / "code.md").write_text(
        "# Code Backlog\n\n## Items\n\n"
        "- [ ] S1 — 13-01 Unify the db script prod semantics | size: lite\n"
        "- [x] S2 — Migrate all data | size: full\n", encoding="utf-8")
    return root, orch


def run_migrate(root: Path, orch: Path, mode: str):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--orchestration-dir", str(orch), "--project-root", str(root), mode],
        capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestMigrateSprintKeys(unittest.TestCase):
    def test_dry_run_plans_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = fixture(tmp)
            before = (orch / "backlogs" / "code.md").read_text()
            proc, data = run_migrate(root, orch, "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(data["keymap"]["S1"].startswith("13-01-"))
            self.assertTrue(data["keymap"]["S2"].startswith("13-"))
            self.assertEqual((orch / "backlogs" / "code.md").read_text(), before)

    def test_apply_rekeys_backlog_and_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = fixture(tmp)
            proc, data = run_migrate(root, orch, "--apply")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            backlog = (orch / "backlogs" / "code.md").read_text(
                encoding="utf-8")
            s1, s2 = data["keymap"]["S1"], data["keymap"]["S2"]
            self.assertIn(f"- [ ] {s1} — Unify the db script prod semantics",
                          backlog)
            yaml_text = (root / "_bmad-output" / "implementation-artifacts"
                         / "sprint-status-Beta-2026.01.01.yaml").read_text()
            self.assertIn(f"{s1}: proposed", yaml_text)
            # S2 was [x] → done under its minted key
            self.assertIn(f"{s2}: done", yaml_text)
            # story files minted under the release dir
            self.assertTrue((root / "_bmad-output" / "implementation-artifacts"
                             / "Beta-2026.01.01" / f"{s1}.md").is_file())

    def test_missing_sprint_yaml_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            (orch / "backlogs").mkdir(parents=True)
            (orch / "backlogs" / "code.md").write_text(
                "- [ ] S1 — Thing\n", encoding="utf-8")
            proc, data = run_migrate(root, orch, "--dry-run")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("sprint-status", data["errors"][0])


if __name__ == "__main__":
    unittest.main()
