"""Tests for ship-artifacts.py — run: python tests/test-ship-artifacts.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "ship-artifacts.py"


def run_sweep(root: Path, orch: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch),
         "--project-root", str(root), *args],
        capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_orch(root: Path):
    orch = root / "docs" / "orchestration"
    orch.mkdir(parents=True)
    return orch


def seed_artifacts(orch: Path, root: Path, key: str):
    """A full artifact set for one story."""
    (orch / "devlog" / "Beta" / "2026-10-18" / key).mkdir(parents=True)
    (orch / "devlog" / "Beta" / "2026-10-18" / key / "index.md").write_text("devlog")
    (orch / "alignment" / "2026" / "10" / "18").mkdir(parents=True)
    (orch / "alignment" / "2026" / "10" / "18" / f"{key}.md").write_text("card")
    (orch / "alignment" / "2026" / "10" / "18" / f"{key}.review-1.md").write_text("review")
    (orch / "sessions").mkdir(exist_ok=True)
    (orch / "sessions" / f"{key}.md").write_text("report")
    (orch / "sessions" / f"{key}.acp.json").write_text("{}")
    (orch / "learning" / "knowledge").mkdir(parents=True)
    (orch / "learning" / "knowledge" / f"{key}.yaml").write_text("k: v")
    (root / "_bmad-output" / "implementation-artifacts").mkdir(parents=True)
    (root / "_bmad-output" / "implementation-artifacts" / f"{key}.md").write_text("story")


class TestShipArtifacts(unittest.TestCase):
    def test_worktree_sweep_copies_full_artifact_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            orch = make_orch(root)
            seed_artifacts(orch, root, "S1")
            wt = root / ".cdo-work" / "g-s1-x"
            wt.mkdir(parents=True)
            proc, data = run_sweep(
                root, orch, "--worktree", str(wt), "--keys", "S1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            swept = data["swept"]["S1"]
            self.assertEqual(len(swept), 7)
            # every artifact mirrored into the worktree at its repo path
            for rel in swept:
                self.assertTrue((wt / rel).is_file(), rel)
                self.assertEqual((wt / rel).read_text(),
                                 (root / rel).read_text())
            self.assertEqual(data["copied"], 7)

    def test_shared_checkout_reports_without_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = make_orch(root)
            seed_artifacts(orch, root, "S1")
            proc, data = run_sweep(root, orch, "--keys", "S1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIsNone(data["worktree"])
            self.assertEqual(len(data["swept"]["S1"]), 7)
            self.assertEqual(data["copied"], 0)

    def test_key_boundary_blocks_prefix_collisions(self):
        """S1 must not sweep S10-* or S1x* files — only S1-keyed names."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = make_orch(root)
            (orch / "sessions").mkdir(parents=True)
            (orch / "sessions" / "S1.md").write_text("s1")
            (orch / "sessions" / "S10-other.md").write_text("other")
            (orch / "sessions" / "S1x.md").write_text("s1x")
            proc, data = run_sweep(root, orch, "--keys", "S1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            swept = data["swept"]["S1"]
            self.assertEqual(len(swept), 1)
            self.assertTrue(swept[0].endswith("S1.md"))

    def test_missing_artifacts_are_reported_not_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = make_orch(root)
            proc, data = run_sweep(root, orch, "--keys", "S9")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["swept"]["S9"], [])

    def test_shared_state_never_swept(self):
        """flow-ledger.yaml, locks, checklists — org state, not artifacts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = make_orch(root)
            (orch / "flow-ledger.yaml").write_text("stories: {S1: {}}")
            (orch / "alignment-checklist.md").write_text("- [ ] S1 — x")
            (orch / "locks").mkdir()
            (orch / "locks" / "S1.lock").write_text("lock")
            proc, data = run_sweep(root, orch, "--keys", "S1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            swept = data["swept"]["S1"]
            for rel in swept:
                self.assertNotIn("flow-ledger", rel)
                self.assertNotIn("checklist", rel)
                self.assertNotIn("locks", rel)
            # the lock file shares the key name — sessions-style match only
            self.assertNotIn("docs/orchestration/locks/S1.lock",
                             [r.replace("\\", "/") for r in swept])

    def test_multiple_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = make_orch(root)
            for k in ("S1", "S2"):
                (orch / "learning" / "knowledge").mkdir(
                    parents=True, exist_ok=True)
                (orch / "learning" / "knowledge" / f"{k}.yaml").write_text(k)
            proc, data = run_sweep(root, orch, "--keys", "S1,S2")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(len(data["swept"]["S1"]), 1)
            self.assertEqual(len(data["swept"]["S2"]), 1)


if __name__ == "__main__":
    unittest.main()
