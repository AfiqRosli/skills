"""Tests for push-state.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "push-state.py"


def run_ps(root: Path, orch: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root),
         "--orchestration-dir", str(orch), *args],
        capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)


class TestPushState(unittest.TestCase):
    def test_not_a_repo_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            proc, data = run_ps(root, orch)
            self.assertEqual(proc.returncode, 2)
            self.assertTrue(any("git" in e for e in data["errors"]))

    def test_orch_outside_repo_refuses(self):
        with tempfile.TemporaryDirectory() as tmp, \
                tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            git(root, "init")
            git(root, "remote", "add", "origin", "git@x:y/z.git")
            orch = Path(other) / "orchestration"
            orch.mkdir(parents=True)
            proc, data = run_ps(root, orch)
            self.assertEqual(proc.returncode, 2)
            self.assertTrue(any("outside" in e for e in data["errors"]))

    def test_dry_run_reports_dirty_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init")
            git(root, "remote", "add", "origin", "git@x:y/z.git")
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            (orch / "flow-ledger.yaml").write_text("pool: {}\n")
            git(root, "add", ".")
            git(root, "-c", "user.email=t@t", "-c", "user.name=t",
                "commit", "-m", "init")
            # dirty orchestration state → would_commit
            (orch / "flow-ledger.yaml").write_text("pool: {confirmed: [S1]}\n")
            proc, data = run_ps(root, orch, "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(data["would_commit"])
            self.assertEqual(data["would_push"], "HEAD:preview")
            self.assertIn("flow-ledger.yaml", data["dirty_paths"][0])

    def test_real_commit_and_push_to_local_remote(self):
        with tempfile.TemporaryDirectory() as tmp, \
                tempfile.TemporaryDirectory() as remote_tmp:
            remote = Path(remote_tmp)
            git(remote, "init", "--bare")
            root = Path(tmp)
            git(root, "init")
            git(root, "remote", "add", "origin", str(remote))
            orch = root / "docs" / "orchestration"
            orch.mkdir(parents=True)
            (orch / "flow-ledger.yaml").write_text("pool: {}\n")
            git(root, "add", ".")
            git(root, "-c", "user.email=t@t", "-c", "user.name=t",
                "commit", "-m", "init")
            proc, data = run_ps(root, orch)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["status"], "pushed")
            self.assertFalse(data["committed"])  # nothing dirty
            # preview lane now exists on the remote
            heads = git(remote, "for-each-ref").stdout
            self.assertIn("refs/heads/preview", heads)
            # dirty state → commits it, then pushes
            (orch / "flow-ledger.yaml").write_text(
                "pool: {confirmed: [S1]}\n")
            proc, data = run_ps(root, orch, "--message", "dispatch pool: S1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(data["committed"])
            log = git(remote, "log", "preview", "--format=%s", "-1").stdout
            self.assertIn("dispatch pool: S1", log)


if __name__ == "__main__":
    unittest.main()
