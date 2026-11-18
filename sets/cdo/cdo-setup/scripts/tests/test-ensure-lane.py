"""Tests for cdo-setup ensure-lane.py — run: uv run -m unittest discover -s tests
Requires git on PATH."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "ensure-lane.py"
GIT = shutil.which("git")


def git(root: Path, *args):
    r = subprocess.run([GIT, "-C", str(root), *args],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"git {' '.join(args)}: {r.stderr}"
    return r


def init_repo(root: Path, commit=True):
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-b", "main")
    if commit:
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "--allow-empty", "-m", "init")


def run_lane(root: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root), *args],
        capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


@unittest.skipUnless(GIT, "git not on PATH")
class TestEnsureLane(unittest.TestCase):
    def test_zero_commit_repo_defers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "r"
            init_repo(root, commit=False)
            proc, data = run_lane(root, "--lane", "preview")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "deferred")

    def test_default_branch_creates_and_switches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "r"
            init_repo(root)
            proc, data = run_lane(root, "--lane", "preview")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "created_and_switched")
            self.assertEqual(git(root, "branch", "--show-current").stdout.strip(),
                             "preview")

    def test_mid_feature_creates_not_switched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "r"
            init_repo(root)
            git(root, "switch", "-c", "feat-x")
            proc, data = run_lane(root, "--lane", "preview")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "created_not_switched")
            self.assertEqual(git(root, "branch", "--show-current").stdout.strip(),
                             "feat-x")

    def test_existing_lane_reports_not_checked_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "r"
            init_repo(root)
            git(root, "branch", "preview")
            proc, data = run_lane(root, "--lane", "preview")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "exists_not_checked_out")
            self.assertEqual(git(root, "branch", "--show-current").stdout.strip(),
                             "main")

    def test_answers_supplies_lane(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "r"
            init_repo(root)
            answers = Path(tmp) / "answers.json"
            answers.write_text(json.dumps(
                {"module": {"ship_target": "ship-x"}}))
            proc, data = run_lane(root, "--answers", str(answers))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["lane"], "ship-x")

    def test_lane_flag_wins_over_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "r"
            init_repo(root)
            answers = Path(tmp) / "answers.json"
            answers.write_text(json.dumps(
                {"module": {"ship_target": "ship-x"}}))
            proc, data = run_lane(root, "--lane", "preview",
                                  "--answers", str(answers))
            self.assertEqual(data["lane"], "preview")


if __name__ == "__main__":
    unittest.main()
