"""Tests for sweep-worktrees.py — run: uv run -m unittest discover -s tests

The shared dead-worktree implementation — lock liveness rules, TTL
gating, and --skip-key retention, against real linked worktrees.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "sweep-worktrees.py"


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)


def run_sweep(root: Path, orch: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root),
         "--orchestration-dir", str(orch), *args],
        capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_repo(tmp: Path):
    root = tmp / "repo"
    root.mkdir(parents=True)
    git(root, "init", "-b", "preview")
    (root / "f.txt").write_text("base")
    git(root, "add", ".")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-qm", "init")
    orch = root / "docs" / "orchestration"
    (orch / "locks").mkdir(parents=True)
    (root / ".cdo-work").mkdir()
    return root, orch


def add_wt(root: Path, name: str) -> Path:
    wt = root / ".cdo-work" / name
    git(root, "worktree", "add", "-b", f"wt-{name[:8]}", str(wt))
    return wt


class TestSweep(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sweep-test-"))
        self.root, self.orch = make_repo(self.tmp)

    def test_lockless_worktree_removed(self):
        add_wt(self.root, "w-01-25-20261023")
        _, res = run_sweep(self.root, self.orch)
        self.assertIn("w-01-25-20261023", res["removed"])
        self.assertFalse(
            (self.root / ".cdo-work" / "w-01-25-20261023").exists())

    def test_stem_lock_keeps_worktree(self):
        wt = add_wt(self.root, "g-batch-20261023")
        (self.orch / "locks" / "g-batch-20261023.lock").write_text("1")
        _, res = run_sweep(self.root, self.orch)
        self.assertEqual(res["removed"], [])
        self.assertTrue(wt.exists())

    def test_story_key_lock_keeps_worker(self):
        add_wt(self.root, "w-01-25-20261023")
        (self.orch / "locks" / "01-25.lock").write_text("1")
        _, res = run_sweep(self.root, self.orch)
        self.assertEqual(res["removed"], [])

    def test_skip_key_retains_rejected_tree(self):
        wt = add_wt(self.root, "w-01-25-20261023")
        _, res = run_sweep(self.root, self.orch, "--skip-key", "01-25")
        self.assertEqual(res["removed"], [])
        self.assertTrue(wt.exists())

    def test_ttl_blocks_young_dead_tree(self):
        wt = add_wt(self.root, "w-01-25-20261023")
        _, res = run_sweep(self.root, self.orch, "--older-than", "60")
        self.assertEqual(res["removed"], [])
        self.assertTrue(wt.exists())

    def test_ttl_passes_aged_dead_tree(self):
        wt = add_wt(self.root, "w-01-25-20261023")
        # idle clock is the newest of {gitdir reflog, dir mtime} —
        # backdate both past the TTL
        gitfile = (wt / ".git").read_text()
        reflog = Path(gitfile.split("gitdir:")[1].strip()) / \
            "logs" / "HEAD"
        old = reflog.stat().st_atime
        os.utime(reflog, (old, old - 7200))
        os.utime(wt, (old, old - 7200))
        _, res = run_sweep(self.root, self.orch, "--older-than", "60")
        self.assertIn("w-01-25-20261023", res["removed"])

    def test_skip_key_retains_group_worktree(self):
        """g-* trees can't be key-matched (name embeds only the queue's
        first key) — any skip keeps them while the escalation is live."""
        wt = add_wt(self.root, "g-01-25-20261023")
        _, res = run_sweep(self.root, self.orch, "--skip-key", "02-99")
        self.assertEqual(res["removed"], [])
        self.assertTrue(wt.exists())
        # without a skip, the same dead g-* tree is removable
        _, res = run_sweep(self.root, self.orch)
        self.assertIn("g-01-25-20261023", res["removed"])

    def test_busy_gitdir_marker_keeps_tree(self):
        """A worktree mid-rebase (MERGE_HEAD present) is live even with
        no session lock — the lock may have been broken wrongly."""
        wt = add_wt(self.root, "w-01-25-20261023")
        gitfile = (wt / ".git").read_text()
        gitdir = Path(gitfile.split("gitdir:")[1].strip())
        (gitdir / "MERGE_HEAD").write_text("f" * 40)
        _, res = run_sweep(self.root, self.orch)
        self.assertEqual(res["removed"], [])
        self.assertTrue(wt.exists())

    def test_main_checkout_never_swept(self):
        _, res = run_sweep(self.root, self.orch)
        self.assertTrue(self.root.exists())
        self.assertNotIn(self.root.name, res["removed"])


if __name__ == "__main__":
    unittest.main()
