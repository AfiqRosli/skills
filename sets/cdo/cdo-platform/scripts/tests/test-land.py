"""Tests for land.py — run: uv run -m unittest discover -s tests

Exercises the landing chain against real repos + linked worktrees: the
FF-check→rebase→CAS→advance sequence workers used to replay by hand.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "land.py"
ADVANCE = Path(__file__).parent.parent / "advance-lane.py"


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)


def run_land(cwd: Path, root: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root), *args],
        capture_output=True, text=True, cwd=str(cwd))
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_repo(tmp: Path):
    """Repo on `preview` at c1; a worktree on a sibling `ship` branch
    whose commits get CAS'd onto refs/heads/cdo-lane by land.py."""
    root = tmp / "repo"
    root.mkdir(parents=True)
    git(root, "init", "-b", "preview")
    (root / "app.ts").write_text("v1\n")
    (root / "docs").mkdir()
    (root / "docs" / "orchestration").mkdir()
    (root / "docs" / "orchestration" / "ledger.yaml").write_text("v1\n")
    git(root, "add", ".")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-qm", "c1")
    # land.py's advance step resolves the script under {root}/.agents —
    # give the scratch repo the real one
    adv_dir = root / ".agents" / "skills" / "cdo-platform" / "scripts"
    adv_dir.mkdir(parents=True)
    shutil.copy(ADVANCE, adv_dir)
    wt = tmp / "wt"
    git(root, "worktree", "add", "-b", "ship", str(wt))
    return root, wt


def commit(wt: Path, name: str, content: str, msg: str):
    (wt / name).write_text(content)
    git(wt, "add", ".")
    git(wt, "-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-qm", msg)


class TestLand(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="land-test-"))

    def test_clean_land_ff(self):
        root, wt = make_repo(self.tmp)
        commit(wt, "story.ts", "code\n", "cdo story: shipped")
        _, res = run_land(wt, root, "--lane", "preview")
        self.assertEqual(res["status"], "landed")
        self.assertFalse(res["rebased"])
        lane_tip = git(root, "rev-parse", "cdo-lane").stdout.strip()
        self.assertEqual(res["lane_sha"], lane_tip)
        # advance ran too — preview now holds the ship commit
        self.assertTrue((root / "story.ts").exists())

    def test_stale_base_rebases_then_lands(self):
        root, wt = make_repo(self.tmp)
        # sibling ship lands first (lane tip moves past the worktree base)
        commit(wt, "sibling.ts", "sib\n", "cdo sib: shipped")
        sib_sha = git(wt, "rev-parse", "HEAD").stdout.strip()
        git(root, "update-ref", "refs/heads/cdo-lane", sib_sha)
        # our commit was made on the OLD base
        git(wt, "reset", "--hard", "HEAD~1")
        commit(wt, "story.ts", "code\n", "cdo story: shipped")
        _, res = run_land(wt, root, "--lane", "preview")
        self.assertEqual(res["status"], "landed")
        self.assertTrue(res["rebased"])
        # both commits survive on the lane
        self.assertEqual(git(root, "merge-base", "--is-ancestor",
                             "cdo-lane~1", sib_sha).returncode, 0)

    def test_rebase_conflict_blocks(self):
        root, wt = make_repo(self.tmp)
        # sibling changes app.ts and lands
        (wt / "app.ts").write_text("sibling change\n")
        git(wt, "add", ".")
        git(wt, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "sib")
        git(root, "update-ref", "refs/heads/cdo-lane",
            git(wt, "rev-parse", "HEAD").stdout.strip())
        # our commit touches the same lines on the old base
        git(wt, "reset", "--hard", "HEAD~1")
        (wt / "app.ts").write_text("my conflicting change\n")
        git(wt, "add", ".")
        git(wt, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "mine")
        proc, res = run_land(wt, root, "--lane", "preview")
        self.assertEqual(res["status"], "blocked")
        self.assertEqual(proc.returncode, 1)
        # lane untouched — never moved sideways
        self.assertNotEqual(
            git(root, "rev-parse", "cdo-lane").stdout.strip(),
            git(wt, "rev-parse", "HEAD").stdout.strip())

    def test_already_abreast(self):
        root, wt = make_repo(self.tmp)
        commit(wt, "story.ts", "code\n", "cdo story: shipped")
        run_land(wt, root, "--lane", "preview")
        _, res = run_land(wt, root, "--lane", "preview")
        self.assertEqual(res["status"], "already-abreast")

    def test_dry_run_touches_nothing(self):
        root, wt = make_repo(self.tmp)
        commit(wt, "story.ts", "code\n", "cdo story: shipped")
        _, res = run_land(wt, root, "--lane", "preview", "--dry-run")
        self.assertEqual(res["status"], "dry-run")
        self.assertNotEqual(
            git(root, "rev-parse", "cdo-lane").returncode, 0)


if __name__ == "__main__":
    unittest.main()
