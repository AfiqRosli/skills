"""Tests for cdo-setup shape-story.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "shape-story.py"


def fixture(tmp: str):
    """Minimal project: newest sprint yaml with an epic-13 block + orch dir."""
    root = Path(tmp)
    impl = root / "_bmad-output" / "implementation-artifacts"
    impl.mkdir(parents=True)
    (impl / "sprint-status-Beta-2026.01.01.yaml").write_text(
        "development_status:\n"
        "  epic-13: in-progress\n"
        "  13-00-placeholder: done\n"
        "retrospective: pending\n", encoding="utf-8")
    orch = root / "docs" / "orchestration"
    (orch / "backlogs").mkdir(parents=True)
    return root, orch


def run_shape(root: Path, orch: Path, *extra):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project-root", str(root), "--orchestration-dir", str(orch),
         *extra],
        capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestShapeStory(unittest.TestCase):
    def test_mints_key_and_writes_four_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = fixture(tmp)
            proc, data = run_shape(root, orch, "--title", "Unify db layer")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["key"], "13-01-unify-db-layer")
            self.assertEqual(data["status"], "shaped")
            yaml_text = (root / "_bmad-output" / "implementation-artifacts"
                         / "sprint-status-Beta-2026.01.01.yaml").read_text()
            self.assertIn("13-01-unify-db-layer: proposed", yaml_text)
            self.assertTrue(Path(data["story_file"]).is_file())
            backlog = (orch / "backlogs" / "code.md").read_text(
                encoding="utf-8")
            self.assertIn("- [ ] 13-01-unify-db-layer — Unify db layer", backlog)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = fixture(tmp)
            yaml_path = (root / "_bmad-output" / "implementation-artifacts"
                         / "sprint-status-Beta-2026.01.01.yaml")
            before = yaml_path.read_text()
            proc, data = run_shape(root, orch, "--title", "Dry run thing",
                                   "--dry-run")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "dry-run")
            self.assertEqual(yaml_path.read_text(), before)
            self.assertFalse((orch / "backlogs" / "code.md").exists())

    def test_missing_epic_refuses_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = fixture(tmp)
            proc, data = run_shape(root, orch, "--title", "Thing",
                                   "--epic", "99")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("epic-99", data["errors"][0])
            self.assertFalse((orch / "backlogs" / "code.md").exists())

    def test_split_from_parent_annotates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = fixture(tmp)
            proc, _ = run_shape(root, orch, "--title", "Parent work")
            self.assertEqual(proc.returncode, 0)
            proc, data = run_shape(root, orch, "--title", "Child slice",
                                   "--split-from", "13-01-parent-work")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["split_from"], "13-01-parent-work")
            yaml_text = (root / "_bmad-output" / "implementation-artifacts"
                         / "sprint-status-Beta-2026.01.01.yaml") \
                .read_text(encoding="utf-8")
            self.assertIn("split →", yaml_text)

    def test_explicit_duplicate_key_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = fixture(tmp)
            run_shape(root, orch, "--title", "Same thing",
                      "--key", "13-05-fixed-key")
            proc, data = run_shape(root, orch, "--title", "Same thing",
                                   "--key", "13-05-fixed-key")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("already exists", data["errors"][0])


if __name__ == "__main__":
    unittest.main()
