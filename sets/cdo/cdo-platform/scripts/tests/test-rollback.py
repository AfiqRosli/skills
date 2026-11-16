"""Tests for rollback.py — run: python test-rollback.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROLLBACK = Path(__file__).parent.parent / "rollback.py"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True)


def run(*args):
    proc = subprocess.run([sys.executable, str(ROLLBACK), *args],
                          capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = None
    return proc, data


def init_repo(root: Path):
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")


def commit_file(root: Path, name: str, text: str, msg: str):
    (root / name).write_text(text, encoding="utf-8")
    git(root, "add", name)
    git(root, "commit", "-qm", msg)
    return git(root, "rev-parse", "HEAD").stdout.strip()


LEDGER = """\
stories:
  {key}:
    status: {status}
    lane_sha: {sha}
{pushed}
"""


class TestRollback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.orch = self.root / "docs" / "orchestration"
        self.orch.mkdir(parents=True)
        init_repo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def write_ledger(self, key, status, sha="", pushed=False):
        self.orch.joinpath("flow-ledger.yaml").write_text(
            LEDGER.format(key=key, status=status, sha=sha,
                          pushed=f"    pushed: true" if pushed else ""),
            encoding="utf-8")

    def args(self, key):
        return [key, "--orchestration-dir", str(self.orch),
                "--project-root", str(self.root)]

    def test_reverts_shipped_story(self):
        commit_file(self.root, "f.txt", "green\n", "chore: init")
        sha = commit_file(self.root, "f.txt", "red\n", "cdo 9-9: shipped")
        commit_file(self.root, "g.txt", "unrelated\n", "later: elsewhere")
        self.write_ledger("9-9", "shipped", sha, pushed=True)
        proc, data = run(*self.args("9-9"))
        self.assertEqual(proc.returncode, 0, data)
        self.assertEqual(data["status"], "reverted")
        self.assertEqual(data["lane_sha"], sha)
        self.assertTrue(data["pushed"])
        self.assertTrue(
            git(self.root, "log", "-1", "--format=%B").stdout
            .startswith("Revert"))
        # the shipped change is undone; the later commit stands
        self.assertEqual((self.root / "f.txt").read_text(), "green\n")
        self.assertEqual((self.root / "g.txt").read_text(), "unrelated\n")

    def test_refuses_unshipped_status(self):
        sha = commit_file(self.root, "f.txt", "v1\n", "cdo 1-2: shipped")
        self.write_ledger("1-2", "verified", sha)
        proc, data = run(*self.args("1-2"))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(data["status"], "refused")
        self.assertIn("verified", data["errors"][0])

    def test_refuses_when_no_commit_found(self):
        commit_file(self.root, "f.txt", "x\n", "chore: init")
        proc, data = run(*self.args("7-7"))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(data["status"], "refused")

    def test_log_grep_fallback(self):
        commit_file(self.root, "f.txt", "green\n", "chore: init")
        sha = commit_file(self.root, "f.txt", "red\n", "cdo 3-3: shipped")
        git(self.root, "update-ref", "refs/heads/cdo-lane", "HEAD")
        commit_file(self.root, "g.txt", "unrelated\n", "later: elsewhere")
        # no ledger entry at all — resolves via cdo-lane history
        proc, data = run(*self.args("3-3"))
        self.assertEqual(proc.returncode, 0, data)
        self.assertEqual(data["lane_sha"], sha)
        self.assertEqual(data["source"], "log-grep")
        self.assertEqual((self.root / "f.txt").read_text(), "green\n")

    def test_conflict_aborts_clean_and_names_paths(self):
        commit_file(self.root, "f.txt", "green\n", "chore: init")
        ship = commit_file(self.root, "f.txt", "red\n", "cdo 4-4: shipped")
        head = commit_file(self.root, "f.txt", "blue\n",
                           "later: repaints the same line")
        # both sides changed the same line → the revert conflicts
        self.write_ledger("4-4", "shipped", ship)
        proc, data = run(*self.args("4-4"))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(data["status"], "conflicts")
        self.assertIn("f.txt", data["conflicts"])
        # aborted clean — no revert in progress, tree untouched
        self.assertFalse((self.root / ".git" / "REVERT_HEAD").exists())
        self.assertEqual(git(self.root, "rev-parse", "HEAD").stdout.strip(),
                         head)
        self.assertEqual((self.root / "f.txt").read_text(), "blue\n")

    def test_dry_run_plans_without_reverting(self):
        sha = commit_file(self.root, "f.txt", "v1\n", "cdo 5-5: shipped")
        self.write_ledger("5-5", "shipped", sha)
        proc, data = run(*self.args("5-5"), "--dry-run")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(data["status"], "plan")
        self.assertEqual(data["lane_sha"], sha)
        self.assertEqual(git(self.root, "rev-parse", "HEAD").stdout.strip(),
                         sha)


if __name__ == "__main__":
    unittest.main()
