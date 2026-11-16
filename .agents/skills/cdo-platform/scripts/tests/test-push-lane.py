"""Tests for push-lane.py — run: uv run -m unittest discover -s tests

The push leg is exercised against a real bare repo on disk — pushes to a
local `git init --bare` remote actually transfer, so the run path is
covered end-to-end without network.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml  # PEP 723 dep is present via the script's env

SCRIPT = Path(__file__).parent.parent / "push-lane.py"


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)


def run_pl(root: Path, orch: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root),
         "--orchestration-dir", str(orch), "--lane", "preview", *args],
        capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_lane(tmp: Path):
    """A repo on `preview` tracking a bare origin, with an orchestration
    dir + ledger. Commits land on the cdo-lane ref like the ship leg does."""
    root = tmp / "repo"
    remote = tmp / "remote.git"
    root.mkdir(parents=True)
    git(root, "init", "-b", "preview")
    subprocess.run(["git", "init", "--bare", str(remote)],
                   capture_output=True)
    git(root, "remote", "add", "origin", str(remote))
    (root / "f.txt").write_text("base")
    git(root, "add", ".")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-m", "init")
    git(root, "push", "-u", "origin", "preview")
    orch = root / "docs" / "orchestration"
    orch.mkdir(parents=True)
    (orch / "flow-ledger.yaml").write_text(
        "pool:\n  confirmed: []\n  quarantined: []\nstories: {}\n",
        encoding="utf-8")
    return root, orch


def lane_commit(root: Path, name: str) -> str:
    """Land a commit on cdo-lane exactly like a worktree ship leg:
    commit on HEAD (detached-capable), then advance the ref."""
    (root / f"{name}.txt").write_text(name)
    git(root, "add", ".")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-m", f"cdo {name}: shipped")
    sha = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "update-ref", "refs/heads/cdo-lane", "HEAD")
    return sha


def ledger_story(orch: Path, key: str, **kw):
    lp = orch / "flow-ledger.yaml"
    ledger = yaml.safe_load(lp.read_text(encoding="utf-8"))
    st = ledger.setdefault("stories", {}).setdefault(key,
                                                     {"status": "shipped"})
    st.update(kw)
    lp.write_text(yaml.safe_dump(ledger), encoding="utf-8")


def read_ledger(orch: Path):
    return yaml.safe_load(
        (orch / "flow-ledger.yaml").read_text(encoding="utf-8"))


class TestPushLane(unittest.TestCase):
    def test_pending_reports_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = make_lane(Path(tmp))
            sha = lane_commit(root, "S1")
            ledger_story(orch, "S1", lane_sha=sha,
                         pre_deploy={"marked_at": "t", "signed_at": "t"})
            ledger_story(orch, "S2",
                         pre_deploy={"marked_at": "t"})
            proc, data = run_pl(root, orch, "pending")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["signed_awaiting_push"], ["S1"])
            self.assertEqual(data["marked_unsigned"], ["S2"])
            self.assertEqual(data["unpushed_commits"], 1)

    def test_run_pushes_newest_signed_and_stamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = make_lane(Path(tmp))
            sha1 = lane_commit(root, "S1")
            sha2 = lane_commit(root, "S2")
            ledger_story(orch, "S1", lane_sha=sha1,
                         pre_deploy={"signed_at": "t"})
            ledger_story(orch, "S2", lane_sha=sha2,
                         pre_deploy={"signed_at": "t"})
            proc, data = run_pl(root, orch, "run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["status"], "pushed")
            # newest signed sha is the push target — ONE push, ONE build
            self.assertEqual(data["target"], sha2)
            self.assertEqual(
                git(root, "rev-parse", "origin/preview").stdout.strip(),
                sha2)
            ledger = read_ledger(orch)
            self.assertEqual(ledger["stories"]["S1"]["pushed"]["sha"], sha1)
            self.assertEqual(ledger["stories"]["S2"]["pushed"]["sha"], sha2)

    def test_unsigned_commits_ride_along_but_report(self):
        """An unsigned story landed BEFORE a signed one is physically
        carried by the push — carried_unsigned names it, it gets stamped,
        and an unsigned story landed AFTER stays staged."""
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = make_lane(Path(tmp))
            sha_u = lane_commit(root, "SU")     # unsigned, earlier
            sha_s = lane_commit(root, "SS")     # signed, later
            sha_v = lane_commit(root, "SV")     # unsigned, newest
            ledger_story(orch, "SU", lane_sha=sha_u,
                         pre_deploy={"marked_at": "t"})
            ledger_story(orch, "SS", lane_sha=sha_s,
                         pre_deploy={"signed_at": "t"})
            ledger_story(orch, "SV", lane_sha=sha_v,
                         pre_deploy={"marked_at": "t"})
            proc, data = run_pl(root, orch, "run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["target"], sha_s)
            self.assertEqual(data["carried_unsigned"], ["SU"])
            self.assertEqual(data["staged_behind_target"], ["SV"])
            self.assertEqual(
                git(root, "rev-parse", "origin/preview").stdout.strip(),
                sha_s)
            ledger = read_ledger(orch)
            self.assertIn("pushed", ledger["stories"]["SU"])   # carried
            self.assertNotIn("pushed", ledger["stories"]["SV"]) # staged

    def test_run_refuses_unsigned_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = make_lane(Path(tmp))
            sha = lane_commit(root, "S1")
            ledger_story(orch, "S1", lane_sha=sha,
                         pre_deploy={"marked_at": "t"})
            proc, data = run_pl(root, orch, "run")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "nothing-to-push")
            # nothing reached origin
            self.assertNotEqual(
                git(root, "rev-parse", "origin/preview").stdout.strip(),
                sha)

    def test_run_refuses_non_ff(self):
        """origin ahead of the signed target → refuse, never force."""
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = make_lane(Path(tmp))
            sha = lane_commit(root, "S1")
            ledger_story(orch, "S1", lane_sha=sha,
                         pre_deploy={"signed_at": "t"})
            # someone else pushed a commit origin-side
            other = Path(tmp) / "other"
            git(Path(tmp), "clone", str(Path(tmp) / "remote.git"),
                str(other))
            git(other, "checkout", "-b", "preview", "origin/preview")
            (other / "x.txt").write_text("x")
            git(other, "add", ".")
            git(other, "-c", "user.email=t@t", "-c", "user.name=t",
                "commit", "-m", "external")
            git(other, "push", "origin", "preview")
            proc, data = run_pl(root, orch, "run")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(data["status"], "refused")
            self.assertTrue(any("non-fast-forward" in e
                                for e in data["errors"]))

    def test_dry_run_plans_without_touching(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = make_lane(Path(tmp))
            sha = lane_commit(root, "S1")
            ledger_story(orch, "S1", lane_sha=sha,
                         pre_deploy={"signed_at": "t"})
            proc, data = run_pl(root, orch, "run", "--dry-run")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "dry-run")
            self.assertEqual(data["target"], sha)
            self.assertNotIn("pushed", read_ledger(orch)["stories"]["S1"])
            self.assertNotEqual(
                git(root, "rev-parse", "origin/preview").stdout.strip(),
                sha)

    def test_signed_sha_not_on_lane_refuses(self):
        """A signed lane_sha that isn't on cdo-lane (and isn't already on
        origin) is a lane-integrity finding — refuse rather than push a
        dangling commit."""
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = make_lane(Path(tmp))
            # a commit that exists in the object store but sits on no lane —
            # detached work that never landed
            git(root, "checkout", "--detach", "HEAD")
            (root / "d.txt").write_text("dangling")
            git(root, "add", "d.txt")
            git(root, "-c", "user.email=t@t", "-c", "user.name=t",
                "commit", "-m", "dangling")
            sha = git(root, "rev-parse", "HEAD").stdout.strip()
            git(root, "checkout", "preview")
            ledger_story(orch, "S1", lane_sha=sha,
                         pre_deploy={"signed_at": "t"})
            proc, data = run_pl(root, orch, "run")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(data["status"], "refused")
            self.assertTrue(any("not on" in e for e in data["errors"]))

    def test_signed_work_already_on_origin_heals(self):
        """Signed items whose sha is already on origin (legacy pushes)
        stamp pushed without a network push — reconciliation, not refusal."""
        with tempfile.TemporaryDirectory() as tmp:
            root, orch = make_lane(Path(tmp))
            sha = git(root, "rev-parse", "HEAD").stdout.strip()
            ledger_story(orch, "S1", lane_sha=sha,
                         pre_deploy={"signed_at": "t"})
            proc, data = run_pl(root, orch, "run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["status"], "healed")
            self.assertEqual(data["healed"], ["S1"])
            self.assertIn("pushed", read_ledger(orch)["stories"]["S1"])


if __name__ == "__main__":
    unittest.main()
